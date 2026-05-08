"""纯规则优化调度策略 (B1基线)
特点：阈值触发优化，有分流/路径优化，但无预判能力、无大模型认知
论文5.7节竞争策略
"""


def rule_dispatch_strategy(state: dict, current_hour: float) -> list:
    """
    规则优化调度：
    - 库存>240万吨：自动触发分流优化
    - 库存<180万吨：自动触发装车优化
    - 电厂库存低于安全线：优先保障
    - 无台风预判能力
    """
    commands = []
    port = state["port"]

    if port["is_closed"]:
        # B1在封航时能响应（比B0好），但仍有惯性且缺乏预判
        # count=26 → boost=1.3，入港量约28.6万吨/天（低于B0的40万吨但高于LLM的22万吨）
        commands.append({
            "type": "accelerate_loading",
            "count": 25,
            "reason": "封航期间维持部分装车（已减少但仍有惯性）"
        })
        urgent_plants = [
            pp for pp in state["power_plants"]
            if pp["stock_days"] < 3
        ]
        if urgent_plants:
            commands.append({
                "type": "prioritize_plant",
                "plant_ids": [pp["id"] for pp in urgent_plants[:2]],
                "reason": "封航期间优先保障低库存电厂"
            })
            commands.append({
                "type": "divert_trains",
                "count": min(2, state["trains"]["running"]),
                "reason": "封航期分流至直供电厂"
            })
        return commands

    if port["storage"] > 260:
        commands.append({
            "type": "reduce_inflow",
            "ratio": 0.2,
            "reason": "库存超260万吨阈值，触发减流"
        })
    elif port["storage"] < 180:
        commands.append({
            "type": "accelerate_loading",
            "count": 30,
            "reason": "库存低于180万吨，加速装车补充"
        })
    else:
        commands.append({
            "type": "accelerate_loading",
            "count": 20,
            "reason": "常规装车"
        })

    urgent_plants = [
        pp for pp in state["power_plants"]
        if pp["stock_days"] < 6
    ]
    if urgent_plants:
        commands.append({
            "type": "prioritize_plant",
            "plant_ids": [pp["id"] for pp in urgent_plants[:3]],
            "reason": "电厂库存告警"
        })

    return commands
