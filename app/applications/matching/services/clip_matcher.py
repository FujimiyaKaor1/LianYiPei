"""
多模态 CLIP - 图文匹配
企业宣传图与产品关联：通过 CLIP 将产品图片与产品描述/类别进行匹配
"""
import os


def clip_available() -> bool:
    """检查 CLIP 是否可用"""
    try:
        import clip
        import torch
        return True
    except ImportError:
        return False


def encode_image(image_path: str) -> list | None:
    """
    使用 CLIP 编码图片，返回特征向量
    需要: pip install ftfy regex pillow torch open_clip_torch 或 pip install git+https://github.com/openai/CLIP.git
    """
    if not os.path.exists(image_path):
        return None
    try:
        import torch
        import open_clip
        model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')
        tokenizer = open_clip.get_tokenizer('ViT-B-32')
        from PIL import Image
        img = preprocess(Image.open(image_path).convert('RGB')).unsqueeze(0)
        with torch.no_grad():
            feats = model.encode_image(img)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats[0].cpu().tolist()
    except ImportError:
        try:
            import clip
            import torch
            from PIL import Image
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, preprocess = clip.load("ViT-B/32", device=device)
            img = preprocess(Image.open(image_path).convert('RGB')).unsqueeze(0).to(device)
            with torch.no_grad():
                feats = model.encode_image(img)
                feats = feats / feats.norm(dim=-1, keepdim=True)
            return feats[0].cpu().tolist()
        except ImportError:
            return None


def encode_text(text: str) -> list | None:
    """使用 CLIP 编码文本"""
    try:
        import torch
        import open_clip
        model, _, _ = open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')
        tokenizer = open_clip.get_tokenizer('ViT-B-32')
        tokens = tokenizer([text])
        with torch.no_grad():
            feats = model.encode_text(tokens)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats[0].cpu().tolist()
    except ImportError:
        try:
            import clip
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, _ = clip.load("ViT-B/32", device=device)
            tokens = clip.tokenize([text]).to(device)
            with torch.no_grad():
                feats = model.encode_text(tokens)
                feats = feats / feats.norm(dim=-1, keepdim=True)
            return feats[0].cpu().tolist()
        except ImportError:
            return None


def match_image_to_products(image_path: str, product_texts: list[str], top_k=5) -> list[tuple[str, float]]:
    """
    将企业宣传图与产品描述匹配，返回相似度最高的 top_k 产品
    product_texts: [(product_name, "描述"), ...] 或 [product_name, ...]
    """
    img_feat = encode_image(image_path)
    if img_feat is None:
        return []
    
    try:
        import torch
        img_t = torch.tensor([img_feat])
        best = []
        for pt in product_texts:
            text = pt if isinstance(pt, str) else f"{pt[0]} {pt[1]}"
            txt_feat = encode_text(text)
            if txt_feat is None:
                continue
            txt_t = torch.tensor([txt_feat])
            sim = (img_t @ txt_t.T).item()
            best.append((text[:50], round(sim, 4)))
        best.sort(key=lambda x: x[1], reverse=True)
        return best[:top_k]
    except Exception:
        return []
