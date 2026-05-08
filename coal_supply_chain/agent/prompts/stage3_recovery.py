"""恢复阶段Prompt - 港口恢复+缺口补给 (论文图4.8)"""

STAGE3_PROMPT_TEMPLATE = """# 当前阶段：恢复期（港口恢复+加速补给）

## 态势信息
- 当前时间：第{current_day:.1f}天 (第{current_hour}小时)
- 封航已结束！港口恢复正常作业
- 恢复已{hours_since_open}小时

## 港口状态
- 当前库存：{port_storage:.1f}万吨
- 等待装船船舶：{waiting_ships}艘（积压）
- 泊位状态：{available_berths}/{total_berths}个可用

## 列车状态
- 空闲列车：{idle_trains}列
- 在途：{running_trains}列

## 电厂状态（关注恢复供应）
{plant_status}

## 任务要求
恢复期的核心目标是"快速消化积压+补充电厂缺口"：
1. 优先为封航期间受影响最大的电厂安排船舶装载
2. 释放所有泊位，加速装船出港
3. 恢复正常装车节奏，重新补充港口库存
4. 注意不要在恢复期反弹过度导致库存暴跌

请调用optimize_split_route工具，模式选择recovery。
"""


def format_stage3_prompt(state: dict) -> str:
    """格式化恢复阶段prompt"""
    from config import TYPHOON_CONFIG

    hours_since_open = state["current_hour"] - TYPHOON_CONFIG["closure_end_hour"]
    available_berths = 17 - state["port"]["loading_ships"]

    plant_lines = []
    for pp in sorted(state["power_plants"], key=lambda x: x["stock_days"]):
        if pp["stock_days"] < 5:
            status = "🔴 急需补给"
        elif pp["stock_days"] < 8:
            status = "🟡 需要关注"
        else:
            status = "🟢 正常"
        plant_lines.append(
            f"  - {pp['name']}(ID:{pp['id']}): 可用{pp['stock_days']:.1f}天 [{status}]"
        )

    return STAGE3_PROMPT_TEMPLATE.format(
        current_day=state["current_hour"] / 24,
        current_hour=int(state["current_hour"]),
        hours_since_open=int(hours_since_open),
        port_storage=state["port"]["storage"],
        waiting_ships=state["port"]["waiting_ships"],
        available_berths=available_berths,
        total_berths=17,
        idle_trains=state["trains"]["idle"],
        running_trains=state["trains"]["running"],
        plant_status="\n".join(plant_lines),
    )
