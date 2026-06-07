"""预留：将匹配闭环奖励同步给推荐模型 / RL 训练管线。"""


def update_rl_signal(match_feedback_id: int, reward: float = 1.0, **kwargs) -> None:
    """当意向签约等正向闭环发生时调用；后续可接入真实 RL / 重排模型更新。"""
    _ = (match_feedback_id, reward, kwargs)
