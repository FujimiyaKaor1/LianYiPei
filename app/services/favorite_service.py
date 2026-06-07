"""
收藏服务层（Favorite Service）
================================

职责：
1. 添加/移除收藏
2. 获取收藏列表
3. 批量操作（批量询价、批量比较）
4. 收藏时记录匹配信息

关联需求：意向报价、名片交换的前置功能
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from app import db
from app.models import FavoriteSupplier, Enterprise, MatchRecord


class FavoriteService:
    """收藏供应商业务服务"""

    # ── 收藏管理 ────────────────────────────────────────────────────────────

    def add_favorite(
        self,
        collector_id: int,
        supplier_id: int,
        product_name: Optional[str] = None,
        match_score: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> tuple[FavoriteSupplier | None, str]:
        """
        添加收藏。

        返回 (FavoriteSupplier对象, 错误信息)；失败时 FavoriteSupplier 为 None。
        """
        if collector_id == supplier_id:
            return None, "不能收藏自己"

        # 检查供应商是否存在
        supplier = Enterprise.query.get(supplier_id)
        if not supplier:
            return None, "供应商不存在"

        # 检查是否已收藏
        existing = FavoriteSupplier.query.filter_by(
            collector_id=collector_id,
            supplier_id=supplier_id,
        ).first()

        if existing:
            # 更新收藏信息
            if product_name:
                existing.product_name = product_name
            if match_score is not None:
                existing.match_score = match_score
            if notes:
                existing.notes = notes
            db.session.commit()
            return existing, ""

        favorite = FavoriteSupplier(
            collector_id=collector_id,
            supplier_id=supplier_id,
            product_name=product_name,
            match_score=match_score,
            notes=notes,
        )
        db.session.add(favorite)
        db.session.commit()
        return favorite, ""

    def remove_favorite(
        self,
        collector_id: int,
        supplier_id: int,
    ) -> tuple[bool, str]:
        """
        取消收藏。

        返回 (是否成功, 错误信息)。
        """
        favorite = FavoriteSupplier.query.filter_by(
            collector_id=collector_id,
            supplier_id=supplier_id,
        ).first()

        if not favorite:
            return False, "收藏记录不存在"

        db.session.delete(favorite)
        db.session.commit()
        return True, ""

    def is_favorited(
        self,
        collector_id: int,
        supplier_id: int,
    ) -> bool:
        """检查是否已收藏"""
        return FavoriteSupplier.query.filter_by(
            collector_id=collector_id,
            supplier_id=supplier_id,
        ).first() is not None

    def get_favorite_list(
        self,
        collector_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """
        获取收藏列表（含供应商信息）。

        返回格式：
        [{
            "id": int,
            "supplier_id": int,
            "supplier_name": str,
            "supplier_province": str,
            "supplier_city": str,
            "supplier_industry": str,
            "capacity": int,
            "credit_score": float,
            "is_green_factory": bool,
            "match_score": float,
            "product_name": str,
            "notes": str,
            "created_at": str,
        }, ...]
        """
        favorites = (
            FavoriteSupplier.query.filter_by(collector_id=collector_id)
            .order_by(FavoriteSupplier.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        result = []
        for fav in favorites:
            supplier = Enterprise.query.get(fav.supplier_id)
            if not supplier:
                continue

            result.append({
                "id": fav.id,
                "supplier_id": fav.supplier_id,
                "supplier_name": supplier.name,
                "supplier_province": supplier.province or "",
                "supplier_city": supplier.city or "",
                "supplier_industry": supplier.industry_code or "",
                "capacity": supplier.capacity or 0,
                "credit_score": supplier.credit_score or 70.0,
                "is_green_factory": supplier.is_green_factory or False,
                "patent_count": supplier.patent_count or 0,
                "match_score": fav.match_score,
                "product_name": fav.product_name or "",
                "notes": fav.notes or "",
                "created_at": fav.created_at.isoformat() if fav.created_at else None,
            })

        return result

    def get_favorite_count(self, collector_id: int) -> int:
        """获取收藏数量"""
        return FavoriteSupplier.query.filter_by(collector_id=collector_id).count()

    def batch_add_inquiry(
        self,
        collector_id: int,
        supplier_ids: list[int],
        product_name: str,
    ) -> dict:
        """
        批量发起询价。

        返回：
        {
            "success": int,   # 成功数量
            "failed": int,    # 失败数量
            "errors": [str, ...]
        }
        """
        from app.models import MatchRecord, MatchFeedback

        success = 0
        failed = 0
        errors = []

        for supplier_id in supplier_ids:
            try:
                # 创建或获取 MatchRecord
                record = MatchRecord.query.filter_by(
                    buyer_id=collector_id,
                    seller_id=supplier_id,
                    product_name=product_name,
                ).first()

                if not record:
                    record = MatchRecord(
                        buyer_id=collector_id,
                        seller_id=supplier_id,
                        product_name=product_name,
                        status="inquiry_sent",
                    )
                    db.session.add(record)
                    db.session.flush()

                success += 1
            except Exception as e:
                failed += 1
                errors.append(f"supplier_id={supplier_id}: {str(e)}")

        db.session.commit()
        return {
            "success": success,
            "failed": failed,
            "errors": errors,
        }

    def update_notes(
        self,
        collector_id: int,
        supplier_id: int,
        notes: str,
    ) -> tuple[bool, str]:
        """更新收藏备注"""
        favorite = FavoriteSupplier.query.filter_by(
            collector_id=collector_id,
            supplier_id=supplier_id,
        ).first()

        if not favorite:
            return False, "收藏记录不存在"

        favorite.notes = notes
        db.session.commit()
        return True, ""

    def get_supplier_favorited_count(self, supplier_id: int) -> int:
        """获取供应商被收藏次数"""
        return FavoriteSupplier.query.filter_by(supplier_id=supplier_id).count()


# ── 模块级单例 ────────────────────────────────────────────────────────────
favorite_service = FavoriteService()
