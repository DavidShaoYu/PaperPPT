"""传统人工调度策略 (B0基线)
特点：FIFO先进先出，被动响应，无预判，无跨环节协同
论文5.4节对比基准
"""


def manual_dispatch_strategy(state: dict, current_hour: float) -> list:
    """
    传统调度：固定规则、被动响应、无预判
    论文核心缺陷：
    - 封航期间仍按原计划发车（铁路惯性大，无法快速停止）
    - 仅在库存真正超限后才被动减流
    - 不主动保障电厂，等断供才处理
    - 恢复期反应滞后，不加速恢复
    """
    commands = []
    port = state["port"]

    if port["is_closed"]:
        # 传统模式：封航后仍有惯性入港（已发出的列车无法立即停止）
        # 铁路惯性大：提前安排的列车全部涌入港口
        # count=36 → boost=1.8，使封航期日入港量达~40万吨（论文表5.2）
        commands.append({
            "type": "accelerate_loading",
            "count": 37,
            "reason": "封航但已有在途列车，惯性入港不可避免"
        })
        return commands

    # 只有库存真正超过上限才被动响应（严重滞后）
    if port["storage"] > port["safety_high"] + 40:
        commands.append({
            "type": "reduce_inflow",
            "ratio": 0.15,
            "reason": "库存严重超限，被动减流"
        })
    else:
        # 固定节奏装车，完全不管台风预警
        # count=20 → boost=1.0，维持基准入港量（论文正常期净入+4万吨/天）
        commands.append({
            "type": "accelerate_loading",
            "count": 20,
            "reason": "按计划装车，维持固定节奏"
        })

    return commands
