# 定时任务调度器使用指南

## 概述

链易配平台使用 APScheduler 实现定时任务调度，主要用于信用分计算引擎的自动化任务。

## 已实现的定时任务

### 1. 重置每日报价计数
- **任务ID**: `reset_daily_quote_counts`
- **执行时间**: 每日凌晨 00:00
- **功能**: 重置所有企业的每日报价计数，确保报价限制正确生效
- **实现**: `app.services.credit_engine.reset_daily_quote_counts()`

### 2. 批量重算信用分
- **任务ID**: `batch_recalculate_credit_scores`
- **执行时间**: 每日凌晨 02:00
- **功能**: 批量重新计算所有企业的信用分，确保信用分反映最新状态
- **实现**: `app.services.credit_engine.batch_recalculate_all()`

## 架构设计

### 调度器初始化

调度器在 Flask 应用启动时自动初始化：

```python
# app/__init__.py
from app.services.scheduler import init_scheduler

def create_app(config_class=Config):
    app = Flask(__name__)
    # ... 其他初始化代码
    
    # 初始化定时任务调度器
    init_scheduler(app)
    
    return app
```

### 调度器配置

调度器使用以下配置：

- **时区**: Asia/Shanghai (东八区)
- **运行模式**: 后台守护进程
- **任务合并**: 启用（错过的任务会被合并执行）
- **最大实例数**: 1（同一任务最多同时运行1个实例）
- **错过任务宽限时间**: 300秒

### 任务执行日志

所有任务执行都会记录日志：

- 任务开始时间
- 任务执行结果（成功/失败）
- 任务执行耗时
- 更新的记录数量（如适用）
- 错误信息（如失败）

日志示例：
```
[定时任务] 开始执行: 重置每日报价计数 - 2024-01-15 00:00:00
[定时任务] 完成: 重置每日报价计数 - 耗时0.23秒

[定时任务] 开始执行: 批量重算信用分 - 2024-01-15 02:00:00
[定时任务] 完成: 批量重算信用分 - 更新156家企业，耗时12.45秒
```

## 管理接口

### 查看调度器状态

**接口**: `GET /admin/api/scheduler/status`

**权限**: 需要管理员权限

**响应示例**:
```json
{
  "running": true,
  "message": "调度器运行中",
  "jobs": [
    {
      "id": "reset_daily_quote_counts",
      "name": "重置每日报价计数",
      "next_run_time": "2024-01-15T00:00:00",
      "trigger": "cron[hour='0', minute='0']"
    },
    {
      "id": "batch_recalculate_credit_scores",
      "name": "批量重算信用分",
      "next_run_time": "2024-01-15T02:00:00",
      "trigger": "cron[hour='2', minute='0']"
    }
  ]
}
```

### 手动触发任务

**接口**: `POST /admin/api/scheduler/trigger/<job_id>`

**权限**: 需要管理员权限

**用途**: 用于测试或紧急情况下手动执行任务

**示例**:
```bash
curl -X POST http://localhost:5000/admin/api/scheduler/trigger/reset_daily_quote_counts \
  -H "Content-Type: application/json"
```

**响应**:
```json
{
  "success": true,
  "message": "任务 reset_daily_quote_counts 已加入执行队列"
}
```

## 测试

运行测试脚本验证调度器：

```bash
python test_scheduler.py
```

测试内容：
- 调度器是否正确初始化
- 所有必需任务是否已注册
- 任务配置是否正确

## 添加新任务

如需添加新的定时任务，在 `app/services/scheduler.py` 中：

1. 实现任务函数：
```python
def _my_new_job(app):
    """新任务的实现"""
    start_time = datetime.now()
    logger.info(f"[定时任务] 开始执行: 我的新任务 - {start_time}")
    
    try:
        with app.app_context():
            # 任务逻辑
            pass
            
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"[定时任务] 完成: 我的新任务 - 耗时{duration:.2f}秒")
        
    except Exception as e:
        logger.error(f"[定时任务] 失败: 我的新任务 - {str(e)}", exc_info=True)
        raise
```

2. 在 `_register_jobs()` 中注册任务：
```python
def _register_jobs(app):
    # ... 现有任务
    
    # 新任务
    scheduler.add_job(
        func=_my_new_job,
        trigger=CronTrigger(hour=3, minute=0),  # 每日凌晨3点
        id='my_new_job',
        name='我的新任务',
        replace_existing=True,
        args=[app]
    )
    logger.info("已注册任务: 每日03:00执行我的新任务")
```

## 注意事项

1. **时区**: 所有时间使用 Asia/Shanghai 时区
2. **应用上下文**: 任务函数必须在 Flask 应用上下文中执行数据库操作
3. **错误处理**: 任务函数应捕获并记录异常，避免影响调度器运行
4. **性能**: 长时间运行的任务应考虑分批处理，避免阻塞
5. **幂等性**: 任务应设计为幂等的，以应对重复执行的情况

## 故障排查

### 调度器未启动

检查应用日志中是否有调度器初始化信息：
```
定时任务调度器已启动
已注册任务: 每日00:00重置报价计数
已注册任务: 每日02:00批量重算信用分
```

### 任务未执行

1. 检查调度器状态接口
2. 查看应用日志中的任务执行记录
3. 验证任务的 `next_run_time` 是否正确

### 任务执行失败

查看日志中的错误信息：
```
[定时任务] 失败: 批量重算信用分 - <错误信息>
```

常见问题：
- 数据库连接问题
- 应用上下文未正确设置
- 业务逻辑错误

## 相关文件

- `app/services/scheduler.py` - 调度器实现
- `app/services/credit_engine.py` - 信用分计算引擎（包含任务函数）
- `app/routes/admin_panel.py` - 管理接口
- `test_scheduler.py` - 测试脚本
