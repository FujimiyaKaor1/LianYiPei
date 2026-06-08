import argparse
from typing import List, Optional


def _build_text(p) -> str:
    parts = []
    if getattr(p, "name", None):
        parts.append(p.name)
    # 目前 Product 模型未提供 description 字段，这里用 category / industry_code 作为补充语义信息
    if getattr(p, "category", None):
        parts.append(str(p.category))
    if getattr(p, "industry_code", None):
        parts.append(str(p.industry_code))
    return " ".join([x for x in parts if x]).strip()


def _to_list(vec) -> List[float]:
    try:
        return vec.tolist()
    except Exception:
        return [float(x) for x in vec]


def main():
    parser = argparse.ArgumentParser(description="Update Product.embedding using Sentence-Transformers.")
    parser.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--limit", type=int, default=0, help="0 means no limit")
    parser.add_argument("--only-missing", action="store_true", help="Only update products without embedding")
    args = parser.parse_args()

    from app import create_app, db
    from app.models import Product

    app = create_app()

    try:
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        raise SystemExit(
            "Missing dependency: sentence-transformers. Install it in your venv, e.g. `pip install sentence-transformers`.\n"
            f"Original error: {e}"
        )

    model = SentenceTransformer(args.model)

    with app.app_context():
        q = Product.query
        if args.only_missing:
            q = q.filter(Product.embedding.is_(None))

        if args.limit and args.limit > 0:
            products = q.limit(args.limit).all()
        else:
            products = q.all()

        if not products:
            print("No products to update.")
            return

        updated = 0
        texts: List[str] = []
        batch: List[Product] = []

        def flush_batch():
            nonlocal updated, texts, batch
            if not batch:
                return
            vecs = model.encode(texts, batch_size=args.batch_size, normalize_embeddings=False)
            for p, v in zip(batch, vecs):
                p.embedding = _to_list(v)
            db.session.commit()
            updated += len(batch)
            texts = []
            batch = []

        for p in products:
            text = _build_text(p)
            if not text:
                continue
            texts.append(text)
            batch.append(p)
            if len(batch) >= args.batch_size:
                flush_batch()

        flush_batch()
        print(f"Updated embeddings for {updated} products.")


if __name__ == "__main__":
    main()

