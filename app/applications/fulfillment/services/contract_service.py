"""
电子合同服务：集成第三方电子合同平台（e签宝/法大大）
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
from urllib.parse import urlsplit

import requests
from flask import current_app

from app import db
from app.models import Enterprise, Transaction
from app.services.collaboration_service import generate_collaboration_code


class EContractConfigurationError(RuntimeError):
    pass


class EContractService:
    """
    电子合同服务类
    集成第三方电子合同平台（e签宝/法大大）
    """
    
    def __init__(self, provider: str = 'disabled', api_key: str = '', api_secret: str = '', base_url: str = '', allow_mock: bool = False):
        """
        初始化电子合同服务
        
        Args:
            provider: 服务提供商 ('esign' for e签宝, 'fadada' for 法大大)
            api_key: API密钥
            api_secret: API密钥
        """
        self.provider = provider
        self.api_key = api_key
        self.api_secret = api_secret
        self.allow_mock = allow_mock
        
        # 配置API端点
        if base_url:
            self.base_url = base_url.rstrip('/')
        elif provider == 'esign':
            self.base_url = 'https://openapi.esign.cn'
        elif provider == 'fadada':
            self.base_url = 'https://api.fadada.com'
        elif provider == 'mock' and allow_mock:
            self.base_url = 'http://127.0.0.1:5050/mock/api/econtract'
        else:
            self.base_url = ''

    def _require_configured(self) -> None:
        if self.provider == 'mock' and self.allow_mock and self.base_url:
            return
        if self.provider not in {'esign', 'fadada', 'custom'} or not self.base_url or not self.api_key:
            raise EContractConfigurationError('电子合同供应商未配置，禁止使用模拟合同或模拟签署结果')
        self._validate_base_url()

    def _validate_base_url(self) -> None:
        """Validate the provider origin before any credentialed request.

        Provider URLs are deployment configuration, but treating them as
        trusted input would allow an accidental HTTP endpoint or URL userinfo
        to exfiltrate the API key.  Production requires HTTPS; development
        may use an internal HTTP test endpoint, but malformed URLs and
        embedded credentials are never accepted.
        """
        parsed = urlsplit(str(self.base_url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise EContractConfigurationError("电子合同供应商 URL 配置无效")
        if parsed.username or parsed.password:
            raise EContractConfigurationError("电子合同供应商 URL 不得包含凭据")
        if parsed.query or parsed.fragment:
            raise EContractConfigurationError("电子合同供应商 URL 不得包含查询参数或片段")
        try:
            environment = str(current_app.config.get("APP_ENV") or os.getenv("APP_ENV") or "development").lower()
        except RuntimeError:
            environment = str(os.getenv("APP_ENV") or "development").lower()
        if environment == "production" and parsed.scheme != "https":
            raise EContractConfigurationError("生产环境电子合同供应商 URL 必须使用 HTTPS")
    
    def generate_contract(
        self,
        buyer_id: int,
        seller_id: int,
        product_name: str,
        terms: Dict
    ) -> str:
        """
        生成电子合同
        
        Args:
            buyer_id: 买方企业ID
            seller_id: 卖方企业ID
            product_name: 产品名称
            terms: 合同条款字典，包含：
                - quantity: 数量
                - unit: 单位
                - price: 单价
                - total_amount: 总金额
                - delivery_time: 交货时间
                - quality_requirements: 质量要求
                - payment_terms: 付款方式
        
        Returns:
            contract_id: 合同ID
        """
        buyer = Enterprise.query.get(buyer_id)
        seller = Enterprise.query.get(seller_id)
        
        if not buyer or not seller:
            raise ValueError('买方或卖方企业不存在')
        self._require_configured()
        
        # 构建合同内容
        request_id = hashlib.sha256(
            json.dumps(
                {
                    'operation': 'contract_create',
                    'buyer_id': buyer_id,
                    'seller_id': seller_id,
                    'product_name': product_name,
                    'terms': terms,
                },
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            ).encode('utf-8')
        ).hexdigest()
        contract_data = {
            'request_id': request_id,
            'buyer': {
                'id': buyer_id,
                'name': buyer.name,
                'contact': buyer.contact or '',
                'phone': buyer.phone or '',
            },
            'seller': {
                'id': seller_id,
                'name': seller.name,
                'contact': seller.contact or '',
                'phone': seller.phone or '',
            },
            'product_name': product_name,
            'terms': terms,
            'created_at': datetime.utcnow().isoformat(),
        }
        
        # 调用第三方API生成合同
        response = self._call_api('/contract/create', contract_data)
        contract_id = response.get('contract_id')
        if not contract_id:
            raise ValueError('合同生成失败：未返回合同ID')
        return str(contract_id)
    
    def sign_contract(
        self,
        contract_id: str,
        enterprise_id: int,
        signature_data: Dict
    ) -> bool:
        """
        企业签署合同
        
        Args:
            contract_id: 合同ID
            enterprise_id: 签署企业ID
            signature_data: 签名数据，包含：
                - signature_type: 签名类型 ('digital', 'handwritten')
                - signature_image: 签名图片（base64编码）
                - timestamp: 签署时间戳
        
        Returns:
            success: 是否签署成功
        """
        enterprise = Enterprise.query.get(enterprise_id)
        if not enterprise:
            raise ValueError('企业不存在')
        self._require_configured()
        
        # 构建签署请求
        request_id = hashlib.sha256(
            json.dumps(
                {
                    'operation': 'contract_sign',
                    'contract_id': contract_id,
                    'enterprise_id': enterprise_id,
                    'signature': signature_data,
                },
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            ).encode('utf-8')
        ).hexdigest()
        sign_data = {
            'request_id': request_id,
            'contract_id': contract_id,
            'signer': {
                'id': enterprise_id,
                'name': enterprise.name,
            },
            'signature': signature_data,
            'signed_at': datetime.utcnow().isoformat(),
        }
        
        response = self._call_api('/contract/sign', sign_data)
        return response.get('success') is True
    
    def check_contract_status(self, contract_id: str) -> str:
        """
        检查合同状态
        
        Args:
            contract_id: 合同ID
        
        Returns:
            status: 合同状态 ('pending', 'signed', 'fulfilled', 'expired')
        """
        self._require_configured()
        response = self._call_api('/contract/status', {'contract_id': contract_id})
        status = response.get('status')
        if status not in {'pending', 'signed', 'fulfilled', 'expired', 'failed'}:
            raise ValueError('电子合同供应商返回了未知状态')
        return status
    
    def generate_collaboration_code(self, contract_id: str) -> str:
        """
        合同签署完成后生成撮合码
        
        Args:
            contract_id: 合同ID
        
        Returns:
            code: 撮合码
        """
        # 从合同ID中提取买卖方信息
        # 注意：实际应用中应从数据库查询合同详情
        self._require_configured()
        response = self._call_api('/contract/details', {'contract_id': contract_id})
        buyer_id = response.get('buyer_id')
        seller_id = response.get('seller_id')
        product_name = response.get('product_name', '')
        amount_range = response.get('amount_range', '')
        if not buyer_id or not seller_id:
            raise ValueError('合同详情缺少买卖方信息')
        
        # 生成撮合码
        collab_code = Transaction.find_by_contract_id(contract_id)
        if collab_code is None:
            collab_code = generate_collaboration_code(
                buyer_id=buyer_id,
                seller_id=seller_id,
                product_name=product_name,
                contract_id=contract_id,
                amount_range=amount_range,
            )
        else:
            if collab_code.buyer_id != int(buyer_id) or collab_code.seller_id != int(seller_id):
                raise ValueError('电子合同供应商返回的签约方与本地授权记录不一致')
            if not collab_code.match_code:
                collab_code.match_code = Transaction.generate_match_code(
                    collab_code.buyer_id,
                    collab_code.seller_id,
                    contract_id,
                )
            info = dict(collab_code.invoice_info or {})
            info['amount_range'] = amount_range or info.get('amount_range')
            collab_code.invoice_info = info
            collab_code.fulfillment_status = 'pending'
            db.session.commit()
        
        return collab_code.match_code
    
    def download_contract(self, contract_id: str) -> bytes:
        """
        下载合同PDF
        
        Args:
            contract_id: 合同ID
        
        Returns:
            pdf_content: PDF文件内容（字节）
        """
        self._require_configured()
        response = self._call_api('/contract/download', {'contract_id': contract_id})
        if 'download_url' in response:
            download_url = str(response['download_url'])
            if urlsplit(download_url).scheme != 'https' or urlsplit(download_url).netloc != urlsplit(self.base_url).netloc:
                raise ValueError('合同下载地址不在已配置供应商域名内')
            pdf_response = requests.get(download_url, timeout=15)
            pdf_response.raise_for_status()
            return pdf_response.content
        if 'content' in response:
            import base64
            return base64.b64decode(response['content'], validate=True)
        raise ValueError('合同下载失败：未返回有效内容')
    
    def _call_api(self, endpoint: str, data: Dict) -> Dict:
        """
        调用第三方API
        
        Args:
            endpoint: API端点
            data: 请求数据
        
        Returns:
            response: API响应
        """
        self._require_configured()
        url = f"{self.base_url}{endpoint}"
        payload = dict(data or {})
        request_id = str(payload.pop('request_id', '') or '').strip()
        
        # 构建请求头
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key,
        }
        if request_id:
            headers['Idempotency-Key'] = request_id[:128]
        
        # 添加签名（如果需要）
        if self.api_secret:
            timestamp = str(int(datetime.utcnow().timestamp()))
            sign_string = f"{endpoint}{timestamp}{json.dumps(payload, sort_keys=True)}{self.api_secret}"
            signature = hashlib.sha256(sign_string.encode()).hexdigest()
            headers['X-Timestamp'] = timestamp
            headers['X-Signature'] = signature
        
        # 发送请求
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        return response.json()
    
    def _generate_local_contract_id(self, buyer_id: int, seller_id: int) -> str:
        """
        生成本地合同ID（当第三方API不可用时）
        
        格式: CT-{buyer_id}-{seller_id}-{timestamp}
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        return f"CT-{buyer_id}-{seller_id}-{timestamp}"
    
    def _generate_mock_pdf(self, contract_id: str) -> bytes:
        """
        生成模拟PDF内容（用于测试）
        """
        # 简单的PDF头部和内容
        pdf_content = f"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Contract ID: {contract_id}) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000317 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
410
%%EOF
"""
        return pdf_content.encode('utf-8')


# 全局实例（可根据配置初始化）
_econtract_service: Optional[EContractService] = None


def get_econtract_service() -> EContractService:
    """获取电子合同服务实例"""
    global _econtract_service
    from flask import current_app
    provider = str(current_app.config.get('ECONTRACT_PROVIDER') or os.getenv('ECONTRACT_PROVIDER') or 'disabled').strip().lower()
    api_key = str(current_app.config.get('ECONTRACT_API_KEY') or os.getenv('ECONTRACT_API_KEY') or '')
    api_secret = str(current_app.config.get('ECONTRACT_API_SECRET') or os.getenv('ECONTRACT_API_SECRET') or '')
    base_url = str(current_app.config.get('ECONTRACT_BASE_URL') or os.getenv('ECONTRACT_BASE_URL') or '')
    allow_mock = bool(current_app.testing and current_app.config.get('ENABLE_MOCK_API'))
    signature = (provider, api_key, api_secret, base_url, allow_mock)
    if _econtract_service is None or getattr(_econtract_service, '_config_signature', None) != signature:
        _econtract_service = EContractService(provider=provider, api_key=api_key, api_secret=api_secret, base_url=base_url, allow_mock=allow_mock)
        _econtract_service._config_signature = signature
    return _econtract_service
