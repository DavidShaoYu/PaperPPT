"""封航前阶段Prompt - 主动防御策略 (论文图4.6)"""

STAGE1_PROMPT_TEMPLATE = """# 当前阶段：封航前预警期（主动防御）

## 态势信息
- 当前时间：第{current_day:.1f}天 (第{current_hour}小时)
- 台风预警已收到，预计第{closure_start_hour}小时开始封航
- 距封航还有{hours_until_closure}小时

## 港口状态
- 当前库存：{port_storage:.1f}万吨（安全区间[{safety_low}, {safety_high}]万吨）
- 库存占比：{storage_ratio:.1%}
- 今日入港量：{inflow_today:.2f}万吨
- 今日出港量：{outflow_today:.2f}万吨
- 等待装船船舶：{waiting_ships}艘

## 列车状态
- 空闲列车：{idle_trains}列
- 装车中：{loading_trains}列
- 在途：{running_trains}列
- 卸车中：{unloading_trains}列

## 电厂状态
{plant_status}

## 任务要求
封航前阶段的核心目标是"主动泄压+提前蓄力"：
1. 如果港口库存偏高(>250万吨)，需要提前减少入港流量，为封航期间库存累积留出空间
2. 提前识别低库存电厂，在封航前优先为其安排船舶装载
3. 加速在港船舶装载，尽快出港送达电厂
4. 根据预测调整装车计划

请调用optimize_split_route工具，模式选择pre_closure_defense，生成封航前的调度方案。
"""


def format_stage1_prompt(state: dict) -> str:
    """格式化封航前阶段prompt"""
    from config import TYPHOON_CONFIG

    plant_lines = []
    for pp in state["power_plants"]:
        status = "⚠️紧急" if pp["stock_days"] < 6 else "正常"
        plant_lines.append(
            f"  - {pp['name']}(ID:{pp['id']}): 库存{pp['stock']:.1f}万吨, "
            f"可用{pp['stock_days']:.1f}天 [{status}]"
        )

    return STAGE1_PROMPT_TEMPLATE.format(
        current_day=state["current_hour"] / 24,
        current_hour=int(state["current_hour"]),
        closure_start_hour=TYPHOON_CONFIG["closure_start_hour"],
        hours_until_closure=max(0, TYPHOON_CONFIG["closure_start_hour"] - state["current_hour"]),
        port_storage=state["port"]["storage"],
        safety_low=state["port"]["safety_low"],
        safety_high=state["port"]["safety_high"],
        storage_ratio=state["port"]["storage_ratio"],
        inflow_today=state["port"]["inflow_today"],
        outflow_today=state["port"]["outflow_today"],
        waiting_ships=state["port"]["waiting_ships"],
        idle_trains=state["trains"]["idle"],
        loading_trains=state["trains"]["loading"],
        running_trains=state["trains"]["running"],
        unloading_trains=state["trains"]["unloading"],
        plant_status="\n".join(plant_lines),
    )
