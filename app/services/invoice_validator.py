"""
[兼容层] 此文件已迁移至 app/applications/fulfillment/services/invoice_service.py
请使用新的导入路径: from app.applications/fulfillment.services.invoice_service import ...
"""
from app.applications.fulfillment.services import invoice_service as _impl

requests = _impl.requests

InvoiceValidationError = _impl.InvoiceValidationError
TaxAPIError = _impl.TaxAPIError

call_tax_api = _impl.call_tax_api
extract_invoice_info = _impl.extract_invoice_info
store_fulfillment_data = _impl.store_fulfillment_data
get_manual_review_list = _impl.get_manual_review_list
_mock_tax_api_validation = _impl._mock_tax_api_validation


def validate_invoice(invoice_data):
    """兼容旧 patch 路径：允许测试/调用方替换本模块的 call_tax_api。"""
    original = _impl.call_tax_api
    _impl.call_tax_api = call_tax_api
    try:
        return _impl.validate_invoice(invoice_data)
    finally:
        _impl.call_tax_api = original
