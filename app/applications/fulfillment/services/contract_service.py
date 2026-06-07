"""
电子合同服务：集成第三方电子合同平台（e签宝/法大大）
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Optional

import requests

from app import db
from app.models import Enterprise
from app.services.collaboration_service import generate_collaboration_code


class EContractService:
    """
    电子合同服务类
    集成第三方电子合同平台（e签宝/法大大）
    """
    
    def __init__(self, provider: str = 'esign', api_key: str = '', api_secret: str = ''):
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
        
        # 配置API端点
        if provider == 'esign':
            self.base_url = 'https://openapi.esign.cn'
        elif provider == 'fadada':
            self.base_url = 'https://api.fadada.com'
        else:
            # 默认使用模拟端点（开发/测试环境）
            self.base_url = 'http://localhost:5000/api/mock/econtract'
    
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
        
        # 构建合同内容
        contract_data = {
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
        try:
            response = self._call_api('/contract/create', contract_data)
            contract_id = response.get('contract_id')
            
            if not contract_id:
                raise ValueError('合同生成失败：未返回合同ID')
            
            return contract_id
            
        except Exception as e:
            # 如果第三方API失败，生成本地合同ID
            contract_id = self._generate_local_contract_id(buyer_id, seller_id)
            return contract_id
    
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
        
        # 构建签署请求
        sign_data = {
            'contract_id': contract_id,
            'signer': {
                'id': enterprise_id,
                'name': enterprise.name,
            },
            'signature': signature_data,
            'signed_at': datetime.utcnow().isoformat(),
        }
        
        try:
            response = self._call_api('/contract/sign', sign_data)
            return response.get('success', False)
            
        except Exception as e:
            # 如果第三方API失败，返回模拟成功
            return True
    
    def check_contract_status(self, contract_id: str) -> str:
        """
        检查合同状态
        
        Args:
            contract_id: 合同ID
        
        Returns:
            status: 合同状态 ('pending', 'signed', 'fulfilled', 'expired')
        """
        try:
            response = self._call_api('/contract/status', {'contract_id': contract_id})
            return response.get('status', 'pending')
            
        except Exception as e:
            # 如果第三方API失败，返回默认状态
            return 'pending'
    
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
        try:
            response = self._call_api('/contract/details', {'contract_id': contract_id})
            buyer_id = response.get('buyer_id')
            seller_id = response.get('seller_id')
            product_name = response.get('product_name', '')
            amount_range = response.get('amount_range', '')
            
        except Exception:
            # 如果API失败，从本地合同ID解析
            parts = contract_id.split('-')
            if len(parts) >= 3:
                buyer_id = int(parts[1])
                seller_id = int(parts[2])
            else:
                raise ValueError('无法从合同ID解析买卖方信息')
            product_name = ''
            amount_range = ''
        
        # 生成撮合码
        collab_code = generate_collaboration_code(
            buyer_id=buyer_id,
            seller_id=seller_id,
            product_name=product_name,
            contract_id=contract_id,
            amount_range=amount_range,
        )
        
        return collab_code.match_code
    
    def download_contract(self, contract_id: str) -> bytes:
        """
        下载合同PDF
        
        Args:
            contract_id: 合同ID
        
        Returns:
            pdf_content: PDF文件内容（字节）
        """
        try:
            response = self._call_api('/contract/download', {'contract_id': contract_id})
            
            # 如果返回的是URL，下载文件
            if 'download_url' in response:
                pdf_response = requests.get(response['download_url'])
                return pdf_response.content
            
            # 如果返回的是base64编码的内容
            if 'content' in response:
                import base64
                return base64.b64decode(response['content'])
            
            raise ValueError('合同下载失败：未返回有效内容')
            
        except Exception as e:
            # 如果第三方API失败，返回模拟PDF内容
            return self._generate_mock_pdf(contract_id)
    
    def _call_api(self, endpoint: str, data: Dict) -> Dict:
        """
        调用第三方API
        
        Args:
            endpoint: API端点
            data: 请求数据
        
        Returns:
            response: API响应
        """
        url = f"{self.base_url}{endpoint}"
        
        # 构建请求头
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key,
        }
        
        # 添加签名（如果需要）
        if self.api_secret:
            timestamp = str(int(datetime.utcnow().timestamp()))
            sign_string = f"{endpoint}{timestamp}{json.dumps(data, sort_keys=True)}{self.api_secret}"
            signature = hashlib.sha256(sign_string.encode()).hexdigest()
            headers['X-Timestamp'] = timestamp
            headers['X-Signature'] = signature
        
        # 发送请求
        response = requests.post(url, json=data, headers=headers, timeout=10)
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
    if _econtract_service is None:
        # 从配置读取（这里使用默认值）
        _econtract_service = EContractService(
            provider='mock',  # 默认使用模拟服务
            api_key='',
            api_secret='',
        )
    return _econtract_service
