"""封航中阶段Prompt - 精准保供策略 (论文图4.7)"""

STAGE2_PROMPT_TEMPLATE = """# 当前阶段：封航期（精准保供+库存控制）

## 态势信息
- 当前时间：第{current_day:.1f}天 (第{current_hour}小时)
- 港口已封航！所有装船作业中断
- 封航已持续{hours_since_closure}小时，预计还剩{hours_until_open}小时

## 港口状态（重点关注！）
- 当前库存：{port_storage:.1f}万吨（安全上限{safety_high}万吨）
- ⚠️ 封航期间出港为零，库存只增不减！
- 如果继续以当前入流速率，{hours_to_overflow}小时后将超过安全上限

## 列车状态
- 空闲列车：{idle_trains}列
- 在途（向港口）：{running_trains}列
- 装车中：{loading_trains}列

## 电厂状态（重点关注断供风险）
{plant_status}

## 任务要求
封航中阶段的双重目标：
1. 【控制港口库存】大幅减少入港流量，防止库存突破安全上限（280万吨）
2. 【保障电厂供应】将部分在途列车分流至铁路直供电厂，确保不发生断供

具体措施：
- 将装车计划削减50%以上
- 识别库存最低的电厂，通过铁路直供方式紧急补给
- 优化在途列车目的地，将部分列车改道直供电厂

请调用optimize_split_route工具，模式选择supply_assurance。
"""


def format_stage2_prompt(state: dict) -> str:
    """格式化封航中阶段prompt"""
    from config import TYPHOON_CONFIG

    hours_since_closure = state["current_hour"] - TYPHOON_CONFIG["closure_start_hour"]
    hours_until_open = max(0, TYPHOON_CONFIG["closure_end_hour"] - state["current_hour"])

    avg_inflow_rate = 3.0 / 24  # 万吨/小时
    remaining_capacity = state["port"]["safety_high"] - state["port"]["storage"]
    hours_to_overflow = remaining_capacity / avg_inflow_rate if avg_inflow_rate > 0 else 999

    plant_lines = []
    urgent_count = 0
    for pp in sorted(state["power_plants"], key=lambda x: x["stock_days"]):
        if pp["stock_days"] < 5:
            status = "🔴 即将断供！"
            urgent_count += 1
        elif pp["stock_days"] < 8:
            status = "🟡 库存偏低"
        else:
            status = "🟢 正常"
        plant_lines.append(
            f"  - {pp['name']}(ID:{pp['id']}): 库存可用{pp['stock_days']:.1f}天 [{status}]"
        )

    return STAGE2_PROMPT_TEMPLATE.format(
        current_day=state["current_hour"] / 24,
        current_hour=int(state["current_hour"]),
        hours_since_closure=int(hours_since_closure),
        hours_until_open=int(hours_until_open),
        port_storage=state["port"]["storage"],
        safety_high=state["port"]["safety_high"],
        hours_to_overflow=int(hours_to_overflow),
        idle_trains=state["trains"]["idle"],
        running_trains=state["trains"]["running"],
        loading_trains=state["trains"]["loading"],
        plant_status="\n".join(plant_lines),
    )
