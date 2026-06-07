"""
[兼容层] 此文件已迁移至 app/applications/matching/services/matcher.py
请使用新的导入路径: from app.applications.matching.services.matcher import ...
"""
from app.applications.matching.services.matcher import *

# 为了向后兼容，保持原有导入路径可用
from app.applications.matching.services.matcher import (
    match_suppliers,
    DEFAULT_WEIGHTS,
    GREEN_PRIORITY_WEIGHTS,
    get_capacity_signal,
    estimate_carbon,
)
