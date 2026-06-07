"""
定时任务调度器
使用APScheduler实现定时任务：
- 每日凌晨0点重置报价计数
- 每日凌晨2点批量重新计算所有企业信用分
"""
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

# 配置日志
logger = logging.getLogger(__name__)

# 全局调度器实例
scheduler = None


def init_scheduler(app):
    """
    初始化并启动调度器
    在Flask应用启动时调用
    """
    global scheduler
    
    if scheduler is not None:
        logger.warning("调度器已经初始化，跳过重复初始化")
        return scheduler
    
    # 创建后台调度器
    scheduler = BackgroundScheduler(
        timezone='Asia/Shanghai',
        daemon=True,
        job_defaults={
            'coalesce': True,  # 合并错过的任务
            'max_instances': 1,  # 同一任务最多同时运行1个实例
            'misfire_grace_time': 300,  # 错过任务的宽限时间（秒）
        }
    )
    
    # 添加任务执行监听器
    scheduler.add_listener(_job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    
    # 注册定时任务
    _register_jobs(app)
    
    # 启动调度器
    scheduler.start()
    logger.info("定时任务调度器已启动")
    
    return scheduler


def _register_jobs(app):
    """注册所有定时任务"""
    
    # 任务1: 每日凌晨0点重置报价计数
    scheduler.add_job(
        func=_reset_daily_quote_counts_job,
        trigger=CronTrigger(hour=0, minute=0),
        id='reset_daily_quote_counts',
        name='重置每日报价计数',
        replace_existing=True,
        args=[app]
    )
    logger.info("已注册任务: 每日00:00重置报价计数")
    
    # 任务2: 每日凌晨2点批量重新计算所有企业信用分
    scheduler.add_job(
        func=_batch_recalculate_credit_scores_job,
        trigger=CronTrigger(hour=2, minute=0),
        id='batch_recalculate_credit_scores',
        name='批量重算信用分',
        replace_existing=True,
        args=[app]
    )
    logger.info("已注册任务: 每日02:00批量重算信用分")

    # 任务3: 每小时执行预警检查
    scheduler.add_job(
        func=_run_alert_checks_job,
        trigger=CronTrigger(minute=0),  # 每小时整点执行
        id='run_alert_checks',
        name='每小时预警检查',
        replace_existing=True,
        args=[app]
    )
    logger.info("已注册任务: 每小时执行预警检查")

    # 任务4: 每日凌晨6点执行预警自动升级检查
    scheduler.add_job(
        func=_auto_escalate_alerts_job,
        trigger=CronTrigger(hour=6, minute=0),
        id='auto_escalate_alerts',
        name='预警自动升级检查',
        replace_existing=True,
        args=[app]
    )
    logger.info("已注册任务: 每日06:00预警自动升级检查")

    # 任务5: 每周一凌晨3点自动生成招商清单
    scheduler.add_job(
        func=_generate_recruitment_list_job,
        trigger=CronTrigger(day_of_week='mon', hour=3, minute=0),
        id='generate_recruitment_list',
        name='每周招商清单生成',
        replace_existing=True,
        args=[app]
    )
    logger.info("已注册任务: 每周一03:00自动生成招商清单")

    # 任务6: 每日上午9点检查逾期招商任务并发送提醒
    scheduler.add_job(
        func=_notify_overdue_recruitment_tasks_job,
        trigger=CronTrigger(hour=9, minute=0),
        id='notify_overdue_recruitment_tasks',
        name='招商任务逾期提醒',
        replace_existing=True,
        args=[app]
    )
    logger.info("已注册任务: 每日09:00招商任务逾期提醒")

    # 任务7: 每日凌晨3点批量更新所有产品价格指数
    scheduler.add_job(
        func=_update_price_indices_job,
        trigger=CronTrigger(hour=3, minute=0),
        id='update_price_indices',
        name='批量更新价格指数',
        replace_existing=True,
        args=[app]
    )
    logger.info("已注册任务: 每日03:00批量更新价格指数")

    # 任务8: 每小时同步订单数据并更新产能利用率
    scheduler.add_job(
        func=_sync_capacity_utilization_job,
        trigger=CronTrigger(minute=30),  # 每小时30分执行
        id='sync_capacity_utilization',
        name='同步产能利用率',
        replace_existing=True,
        args=[app]
    )
    logger.info("已注册任务: 每小时:30同步产能利用率")

    # 任务9: 每日凌晨1点处理过期质量标签
    scheduler.add_job(
        func=_expire_quality_labels_job,
        trigger=CronTrigger(hour=1, minute=0),
        id='expire_quality_labels',
        name='处理过期质量标签',
        replace_existing=True,
        args=[app]
    )
    logger.info("已注册任务: 每日01:00处理过期质量标签")

    # 任务10: 每月1日凌晨4点自动同步已授权的数据
    scheduler.add_job(
        func=_sync_authorized_data_job,
        trigger=CronTrigger(day=1, hour=4, minute=0),
        id='sync_authorized_data',
        name='同步已授权数据',
        replace_existing=True,
        args=[app]
    )
    logger.info("已注册任务: 每月1日04:00同步已授权数据")

    # 任务11: 每小时检测外部接口可用性
    scheduler.add_job(
        func=_check_external_interfaces_job,
        trigger=CronTrigger(minute=45),  # 每小时45分执行
        id='check_external_interfaces',
        name='外部接口可用性检测',
        replace_existing=True,
        args=[app]
    )
    logger.info("已注册任务: 每小时:45外部接口可用性检测")

    # 任务12: 每日凌晨4点清理超过90天的消息
    scheduler.add_job(
        func=_cleanup_old_messages_job,
        trigger=CronTrigger(hour=4, minute=0),
        id='cleanup_old_messages',
        name='清理旧消息',
        replace_existing=True,
        args=[app]
    )
    logger.info("已注册任务: 每日04:00清理超过90天的消息")



def _reset_daily_quote_counts_job(app):
    """
    定时任务: 重置每日报价计数
    每日凌晨0点执行
    """
    start_time = datetime.now()
    logger.info(f"[定时任务] 开始执行: 重置每日报价计数 - {start_time}")
    
    try:
        with app.app_context():
            from app.services.credit_engine import reset_daily_quote_counts
            reset_daily_quote_counts()
            
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"[定时任务] 完成: 重置每日报价计数 - 耗时{duration:.2f}秒")
        
    except Exception as e:
        logger.error(f"[定时任务] 失败: 重置每日报价计数 - {str(e)}", exc_info=True)
        raise


def _batch_recalculate_credit_scores_job(app):
    """
    定时任务: 批量重新计算所有企业信用分
    每日凌晨2点执行
    """
    start_time = datetime.now()
    logger.info(f"[定时任务] 开始执行: 批量重算信用分 - {start_time}")
    
    try:
        with app.app_context():
            from app.services.credit_engine import batch_recalculate_all
            updated_count = batch_recalculate_all()
            
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"[定时任务] 完成: 批量重算信用分 - "
            f"更新{updated_count}家企业，耗时{duration:.2f}秒"
        )
        
    except Exception as e:
        logger.error(f"[定时任务] 失败: 批量重算信用分 - {str(e)}", exc_info=True)
        raise


def _job_listener(event):
    """
    任务执行监听器
    记录任务执行结果
    """
    if event.exception:
        logger.error(
            f"[定时任务] 任务执行失败: {event.job_id} - {event.exception}",
            exc_info=True
        )
    else:
        logger.info(f"[定时任务] 任务执行成功: {event.job_id}")


def shutdown_scheduler():
    """
    关闭调度器
    在应用关闭时调用
    """
    global scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("定时任务调度器已关闭")
        scheduler = None


def get_scheduler():
    """获取调度器实例"""
    return scheduler


def get_job_status():
    """
    获取所有任务的状态
    返回任务列表及下次执行时间
    """
    if scheduler is None:
        return []
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger),
        })
    return jobs


def _run_alert_checks_job(app):
    """
    定时任务: 每小时执行预警检查
    需求: 32.8
    """
    start_time = datetime.now()
    logger.info(f"[定时任务] 开始执行: 预警检查 - {start_time}")

    try:
        with app.app_context():
            from app.services.alert_engine import run_all_checks
            alerts = run_all_checks()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"[定时任务] 完成: 预警检查 - "
            f"生成{len(alerts)}条预警，耗时{duration:.2f}秒"
        )

    except Exception as e:
        logger.error(f"[定时任务] 失败: 预警检查 - {str(e)}", exc_info=True)
        raise


def _auto_escalate_alerts_job(app):
    """
    定时任务: 预警自动升级（黄色超3天未处理 → 红色）
    需求: 33.6
    """
    start_time = datetime.now()
    logger.info(f"[定时任务] 开始执行: 预警自动升级 - {start_time}")

    try:
        with app.app_context():
            from app.services.alert_notifier import auto_escalate_alerts
            count = auto_escalate_alerts()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"[定时任务] 完成: 预警自动升级 - "
            f"升级{count}条预警，耗时{duration:.2f}秒"
        )

    except Exception as e:
        logger.error(f"[定时任务] 失败: 预警自动升级 - {str(e)}", exc_info=True)
        raise


def _generate_recruitment_list_job(app):
    """
    定时任务: 每周自动生成招商清单并推送给招商部门。
    需求: 71.1, 71.2, 71.3, 71.4, 71.5, 71.6, 71.7
    """
    start_time = datetime.now()
    logger.info(f"[定时任务] 开始执行: 每周招商清单生成 - {start_time}")

    try:
        with app.app_context():
            from app.services.recruitment_service import generate_recruitment_list
            from app.services.alert_notifier import send_message
            from app.models import Enterprise

            result = generate_recruitment_list()
            total_gaps = result.get('total_gaps', 0)

            # 推送给所有 admin 用户（招商部门）
            admins = Enterprise.query.filter_by(role='admin').all()
            for admin in admins:
                send_message(
                    recipient_id=admin.id,
                    message_type='system',
                    title=f'本周招商清单已生成（{total_gaps}个缺口）',
                    content=(
                        f'系统已完成本周产业链缺口分析，共发现{total_gaps}个供应链缺口，'
                        f'请前往招商任务管理页面查看详情并跟进。'
                    ),
                    link_url='/recruitment/gaps',
                    priority='normal',
                )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"[定时任务] 完成: 每周招商清单生成 - "
            f"发现{total_gaps}个缺口，耗时{duration:.2f}秒"
        )

    except Exception as e:
        logger.error(f"[定时任务] 失败: 每周招商清单生成 - {str(e)}", exc_info=True)
        raise


def _notify_overdue_recruitment_tasks_job(app):
    """
    定时任务: 检查逾期招商任务并发送提醒。
    需求: 38.8, 71.6
    """
    start_time = datetime.now()
    logger.info(f"[定时任务] 开始执行: 招商任务逾期提醒 - {start_time}")

    try:
        with app.app_context():
            from app.services.recruitment_service import notify_overdue_tasks
            count = notify_overdue_tasks()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"[定时任务] 完成: 招商任务逾期提醒 - "
            f"提醒{count}个逾期任务，耗时{duration:.2f}秒"
        )

    except Exception as e:
        logger.error(f"[定时任务] 失败: 招商任务逾期提醒 - {str(e)}", exc_info=True)
        raise


def _update_price_indices_job(app):
    """
    定时任务: 每日批量更新所有产品价格指数。
    需求: 16.6
    """
    start_time = datetime.now()
    logger.info(f"[定时任务] 开始执行: 批量更新价格指数 - {start_time}")

    try:
        with app.app_context():
            from app.services.quote_pool import quote_pool_manager
            count = quote_pool_manager.batch_update_all_price_indices()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"[定时任务] 完成: 批量更新价格指数 - "
            f"更新{count}个产品，耗时{duration:.2f}秒"
        )

    except Exception as e:
        logger.error(f"[定时任务] 失败: 批量更新价格指数 - {str(e)}", exc_info=True)
        raise


def _sync_capacity_utilization_job(app):
    """
    定时任务: 每小时同步SaaS订单数据并更新产能利用率。
    需求: 17.6, 20.3, 20.4, 20.5, 20.8
    """
    start_time = datetime.now()
    logger.info(f"[定时任务] 开始执行: 同步产能利用率 - {start_time}")

    try:
        with app.app_context():
            from app.services.order_service import OrderService
            
            # 使用OrderService同步产能数据
            updated_count = OrderService.sync_capacity_data()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"[定时任务] 完成: 同步产能利用率 - "
            f"更新{updated_count}家企业，耗时{duration:.2f}秒"
        )

    except Exception as e:
        logger.error(f"[定时任务] 失败: 同步产能利用率 - {str(e)}", exc_info=True)
        raise


def _expire_quality_labels_job(app):
    """
    定时任务: 每日凌晨1点处理过期质量标签，自动将过期标签状态更新为 expired 并通知企业。
    需求: 18.6, 18.7
    """
    start_time = datetime.now()
    logger.info(f"[定时任务] 开始执行: 处理过期质量标签 - {start_time}")

    try:
        with app.app_context():
            from app.services.quality_label_service import expire_all_overdue_labels
            count = expire_all_overdue_labels()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"[定时任务] 完成: 处理过期质量标签 - "
            f"处理{count}条过期标签，耗时{duration:.2f}秒"
        )

    except Exception as e:
        logger.error(f"[定时任务] 失败: 处理过期质量标签 - {str(e)}", exc_info=True)
        raise


def _sync_authorized_data_job(app):
    """
    定时任务: 每月自动同步已授权的数据（用电量、开票数据）
    需求: 19.6
    """
    start_time = datetime.now()
    logger.info(f"[定时任务] 开始执行: 同步已授权数据 - {start_time}")

    try:
        with app.app_context():
            from app.services.data_authorization_service import DataAuthorizationService
            service = DataAuthorizationService()
            result = service.sync_all_authorized_data()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"[定时任务] 完成: 同步已授权数据 - "
            f"总计{result['total']}条，成功{result['success']}条，失败{result['failed']}条，"
            f"耗时{duration:.2f}秒"
        )

    except Exception as e:
        logger.error(f"[定时任务] 失败: 同步已授权数据 - {str(e)}", exc_info=True)
        raise


def _check_external_interfaces_job(app):
    """
    定时任务: 每小时检测外部接口可用性
    需求: 60.6, 60.7, 60.8
    """
    start_time = datetime.now()
    logger.info(f"[定时任务] 开始执行: 外部接口可用性检测 - {start_time}")

    try:
        with app.app_context():
            from app.services.external_data_service import interface_manager
            results = interface_manager.check_all_interfaces()

        ok_count = sum(1 for r in results if r.get('status') == 'ok')
        err_count = len(results) - ok_count
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"[定时任务] 完成: 外部接口可用性检测 - "
            f"正常{ok_count}个，异常{err_count}个，耗时{duration:.2f}秒"
        )

    except Exception as e:
        logger.error(f"[定时任务] 失败: 外部接口可用性检测 - {str(e)}", exc_info=True)
        raise


def _cleanup_old_messages_job(app):
    """
    定时任务: 每日清理超过90天的消息
    需求: 25.8
    """
    start_time = datetime.now()
    logger.info(f"[定时任务] 开始执行: 清理旧消息 - {start_time}")

    try:
        with app.app_context():
            from app.services.message_service import MessageService
            count = MessageService.cleanup_old_messages(days=90)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            f"[定时任务] 完成: 清理旧消息 - "
            f"删除{count}条消息，耗时{duration:.2f}秒"
        )

    except Exception as e:
        logger.error(f"[定时任务] 失败: 清理旧消息 - {str(e)}", exc_info=True)
        raise

