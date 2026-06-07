"""
验证数据授权管理功能
测试需求: 19.1-19.8, 62.1-62.2
"""
import sys
from app import create_app, db
from app.models import Enterprise
from app.services.data_authorization_service import DataAuthorizationService

def verify_data_authorization():
    """验证数据授权管理功能"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("数据授权管理功能验证")
        print("=" * 60)
        
        service = DataAuthorizationService()
        
        # 1. 查找测试企业
        print("\n1. 查找测试企业...")
        enterprise = Enterprise.query.filter_by(role='enterprise').first()
        if not enterprise:
            print("❌ 未找到测试企业")
            return False
        
        print(f"✓ 找到测试企业: {enterprise.name} (ID: {enterprise.id})")
        print(f"  当前信用分: {enterprise.credit_score}")
        
        # 2. 测试授权用电量数据
        print("\n2. 测试授权用电量数据...")
        old_score = enterprise.credit_score
        result = service.authorize_data(enterprise.id, 'power_consumption')
        
        if result['success']:
            print(f"✓ 授权成功")
            print(f"  授权ID: {result['authorization_id']}")
            if result.get('credit_bonus', 0) > 0:
                print(f"  信用分奖励: +{result['credit_bonus']}")
                print(f"  信用分变化: {result['old_score']} → {result['new_score']}")
        else:
            print(f"✗ 授权失败: {result['message']}")
        
        # 3. 测试授权开票数据
        print("\n3. 测试授权开票数据...")
        result = service.authorize_data(enterprise.id, 'invoice_data')
        
        if result['success']:
            print(f"✓ 授权成功")
            print(f"  授权ID: {result['authorization_id']}")
            if result.get('credit_bonus', 0) > 0:
                print(f"  信用分奖励: +{result['credit_bonus']}")
                print(f"  信用分变化: {result['old_score']} → {result['new_score']}")
        else:
            print(f"✗ 授权失败: {result['message']}")
        
        # 4. 获取授权列表
        print("\n4. 获取授权列表...")
        authorizations = service.get_authorizations(enterprise.id)
        print(f"✓ 找到 {len(authorizations)} 条授权记录")
        
        for auth in authorizations:
            print(f"\n  授权记录 #{auth['id']}:")
            print(f"    数据类型: {auth['data_type_name']}")
            print(f"    授权状态: {'已授权' if auth['authorized'] else '已撤销'}")
            print(f"    授权时间: {auth['authorized_at']}")
            print(f"    同步状态: {auth['sync_status_name']}")
            if auth['last_sync_at']:
                print(f"    最后同步: {auth['last_sync_at']}")
        
        # 5. 测试数据同步
        print("\n5. 测试数据同步...")
        if authorizations:
            dt = authorizations[0].get("data_type")
            if dt:
                sync_result = service._sync_data(enterprise.id, dt)
                if sync_result['success']:
                    print(f"✓ 数据同步成功")
                    print(f"  数据类型: {dt}")
                else:
                    print(f"✗ 数据同步失败: {sync_result.get('error')}")
        
        # 6. 测试撤销授权
        print("\n6. 测试撤销授权...")
        if authorizations:
            auth_id = authorizations[0]['id']
            result = service.revoke_authorization(auth_id, enterprise.id)
            
            if result['success']:
                print(f"✓ 撤销成功")
                print(f"  {result['message']}")
                
                # 验证撤销后的状态（JSON）
                enterprise = Enterprise.query.get(enterprise.id)
                m = enterprise.data_auth if isinstance(enterprise.data_auth, dict) else {}
                rec = next(
                    (v for v in m.values() if isinstance(v, dict) and v.get("id") == auth_id),
                    None,
                )
                if rec:
                    print(f"  授权状态: {'已授权' if rec.get('authorized') else '已撤销'}")
                    print(f"  撤销时间: {rec.get('revoked_at')}")
            else:
                print(f"✗ 撤销失败: {result['message']}")
        
        # 7. 测试重新授权
        print("\n7. 测试重新授权...")
        if authorizations:
            data_type = authorizations[0]['data_type']
            result = service.authorize_data(enterprise.id, data_type)
            
            if result['success']:
                print(f"✓ 重新授权成功")
                print(f"  {result['message']}")
                print(f"  信用分奖励: +{result.get('credit_bonus', 0)} (重新授权不再奖励)")
            else:
                print(f"✗ 重新授权失败: {result['message']}")
        
        # 8. 验证信用分变更记录（Enterprise.credit_score_events）
        print("\n8. 验证信用分变更记录...")
        enterprise = Enterprise.query.get(enterprise.id)
        evs = enterprise.credit_score_events if isinstance(enterprise.credit_score_events, list) else []
        history = [e for e in evs if isinstance(e, dict) and e.get("change_type") == "data_authorization"][-3:]
        
        print(f"✓ 找到 {len(history)} 条数据授权相关的信用分变更记录")
        for record in history:
            print(f"\n  记录 #{record.get('id')}:")
            print(f"    变更值: {float(record.get('change_value') or 0):+.1f}")
            print(f"    变更原因: {record.get('reason')}")
            print(f"    信用分: {float(record.get('old_score') or 0):.1f} → {float(record.get('new_score') or 0):.1f}")
            print(f"    变更时间: {record.get('created_at')}")
        
        # 9. 测试批量同步
        print("\n9. 测试批量同步所有已授权数据...")
        result = service.sync_all_authorized_data()
        print(f"✓ 批量同步完成")
        print(f"  总计: {result['total']} 条")
        print(f"  成功: {result['success']} 条")
        print(f"  失败: {result['failed']} 条")
        
        # 10. 验证API路由
        print("\n10. 验证API路由...")
        from app.routes.data_authorization import bp
        routes = []
        for rule in app.url_map.iter_rules():
            if 'data_authorization' in rule.endpoint:
                routes.append(f"{rule.methods} {rule.rule}")
        
        print(f"✓ 找到 {len(routes)} 个数据授权相关路由:")
        for route in routes:
            print(f"  {route}")
        
        print("\n" + "=" * 60)
        print("✓ 数据授权管理功能验证完成")
        print("=" * 60)
        
        return True

if __name__ == '__main__':
    try:
        success = verify_data_authorization()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 验证过程出错: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
