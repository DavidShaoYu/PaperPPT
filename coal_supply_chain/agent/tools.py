"""Function Calling工具定义 - 论文4.5节Tool-use接口"""

DISPATCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "optimize_split_route",
            "description": "优化重车分流路径。根据当前港口库存压力和电厂需求缺口，计算最优的列车分流方案，最小化供需偏差。",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["pre_closure_defense", "supply_assurance", "recovery"],
                        "description": "优化模式：pre_closure_defense(封航前主动防御)、supply_assurance(封航中保供)、recovery(恢复期)"
                    },
                    "target_port_storage": {
                        "type": "number",
                        "description": "目标港口库存水平(万吨)"
                    },
                    "priority_plants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "优先保障的电厂ID列表（最多5个，超出将被截断）"
                    }
                },
                "required": ["mode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "optimize_berth_schedule",
            "description": "优化泊位装船排队顺序。考虑船舶吨位、目的地电厂紧急程度和泊位兼容性，重新排列装船优先级。",
            "parameters": {
                "type": "object",
                "properties": {
                    "priority_destinations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "优先装船的目的地列表"
                    },
                    "max_queue_time_hours": {
                        "type": "number",
                        "description": "最大允许排队等待时间(小时)"
                    }
                },
                "required": ["priority_destinations"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "predict_stock_trend",
            "description": "预测未来N小时的港口和电厂库存变化趋势。基于当前入流/出流速率和计划数据进行线性外推。",
            "parameters": {
                "type": "object",
                "properties": {
                    "hours_ahead": {
                        "type": "integer",
                        "description": "预测未来多少小时"
                    },
                    "target": {
                        "type": "string",
                        "enum": ["port", "plants", "all"],
                        "description": "预测目标"
                    }
                },
                "required": ["hours_ahead", "target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_dispatch_plan",
            "description": "生成完整的调度计划。根据当前阶段和系统状态，输出具体的调度指令序列。",
            "parameters": {
                "type": "object",
                "properties": {
                    "stage": {
                        "type": "string",
                        "enum": ["pre_closure", "during_closure", "recovery"],
                        "description": "当前阶段"
                    },
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "params": {"type": "object"}
                            }
                        },
                        "description": "调度动作序列"
                    }
                },
                "required": ["stage", "actions"]
            }
        }
    }
]


def execute_tool(tool_name: str, arguments: dict, system_state: dict) -> dict:
    """执行工具调用并返回结果"""
    if tool_name == "optimize_split_route":
        return _execute_split_route(arguments, system_state)
    elif tool_name == "optimize_berth_schedule":
        return _execute_berth_schedule(arguments, system_state)
    elif tool_name == "predict_stock_trend":
        return _execute_stock_prediction(arguments, system_state)
    elif tool_name == "generate_dispatch_plan":
        return _execute_dispatch_plan(arguments, system_state)
    return {"error": f"Unknown tool: {tool_name}"}


def _execute_split_route(args: dict, state: dict) -> dict:
    """执行分流路径优化"""
    mode = args.get("mode", "pre_closure_defense")
    port_storage = state["port"]["storage"]
    idle_trains = state["trains"]["idle"]

    if mode == "pre_closure_defense":
        commands = []
        safety_high = state["port"].get("safety_high", 280)
        headroom = safety_high - port_storage
        if headroom < 10:
            reduce_ratio = 0.25
        elif headroom < 30:
            reduce_ratio = 0.15
        elif headroom < 50:
            reduce_ratio = 0.08
        else:
            reduce_ratio = 0.03
        commands.append({
            "type": "reduce_inflow",
            "ratio": reduce_ratio,
            "reason": f"封航前主动减流(余量{headroom:.0f}万吨)：暂停部分新增发车计划"
        })
        urgent = [pp for pp in state["power_plants"] if pp["stock_days"] < 10]
        if urgent:
            divert_count = min(8, idle_trains, state["trains"]["running"])
            if divert_count > 0:
                commands.append({
                    "type": "divert_trains",
                    "count": min(divert_count, state["trains"]["running"] // 2),
                    "reason": "预判封航后低库存电厂，提前铁路直供"
                })
            commands.append({
                "type": "prioritize_plant",
                "plant_ids": [pp["id"] for pp in urgent[:5]],
                "reason": "预判封航后低库存电厂，提前保障"
            })
        return {"commands": commands, "status": "success"}

    elif mode == "supply_assurance":
        commands = []
        safety_high = state["port"].get("safety_high", 280)
        if port_storage > safety_high - 15:
            commands.append({
                "type": "reduce_inflow",
                "ratio": 0.20,
                "reason": f"封航中港口库存{port_storage:.0f}接近上限，大幅减流"
            })
        urgent = [pp for pp in state["power_plants"] if pp["stock_days"] < 6]
        running = state["trains"]["running"]
        if urgent:
            divert_count = min(10, running // 2)
            if divert_count > 0:
                commands.append({
                    "type": "divert_trains",
                    "count": divert_count,
                    "reason": "封航中将在途列车分流直供紧急电厂"
                })
            commands.append({
                "type": "prioritize_plant",
                "plant_ids": [pp["id"] for pp in urgent[:5]],
                "reason": "封航中优先保障紧急电厂"
            })
        else:
            divert_count = min(5, running // 2)
            if divert_count > 0:
                commands.append({
                    "type": "divert_trains",
                    "count": divert_count,
                    "reason": "封航中分流部分列车直供电厂"
                })
        return {"commands": commands, "status": "success"}

    elif mode == "recovery":
        commands = []
        if not state["port"]["is_closed"]:
            commands.append({
                "type": "release_berths",
                "reason": "恢复期释放泊位加速出港"
            })
        urgent = [pp for pp in state["power_plants"] if pp["stock_days"] < 7]
        if urgent:
            divert_count = min(5, idle_trains, state["trains"]["running"] // 2)
            if divert_count > 0:
                commands.append({
                    "type": "divert_trains",
                    "count": divert_count,
                    "reason": "恢复期分流列车补给电厂"
                })
            commands.append({
                "type": "prioritize_plant",
                "plant_ids": [pp["id"] for pp in urgent[:5]],
                "reason": "恢复期继续保障低库存电厂"
            })
        return {"commands": commands, "status": "success"}

    return {"commands": [], "status": "unknown_mode"}


def _execute_berth_schedule(args: dict, state: dict) -> dict:
    """执行泊位调度优化 - 返回泊位释放指令"""
    priority_dest = args.get("priority_destinations", [])
    commands = []
    if not state["port"]["is_closed"]:
        commands.append({
            "type": "release_berths",
            "reason": f"泊位优化：优先装载发往{priority_dest[:3]}的船舶"
        })
    return {
        "commands": commands,
        "schedule": [
            {"berth": f"BT{i:02d}", "priority": "high" if i <= 5 else "normal"}
            for i in range(1, 18)
        ],
        "priority_destinations": priority_dest,
        "status": "success"
    }


def _execute_stock_prediction(args: dict, state: dict) -> dict:
    """执行库存趋势预测"""
    hours = args.get("hours_ahead", 24)
    port_storage = state["port"]["storage"]
    is_closed = state["port"]["is_closed"]

    avg_inflow = 3.0   # 万吨/天
    avg_outflow = 2.8 if not is_closed else 0.0

    predictions = []
    current = port_storage
    for h in range(1, hours + 1):
        daily_net = (avg_inflow - avg_outflow) / 24
        current += daily_net
        if h % 6 == 0:
            predictions.append({"hour": h, "port_storage": round(current, 1)})

    plant_alerts = []
    for pp in state["power_plants"]:
        days_left = pp["stock_days"]
        if days_left < hours / 24 + 3:
            plant_alerts.append({
                "id": pp["id"],
                "name": pp["name"],
                "days_until_critical": round(days_left - 3, 1),
            })

    return {
        "port_trend": predictions,
        "plant_alerts": plant_alerts,
        "will_exceed_safety": current > state["port"]["safety_high"],
        "status": "success"
    }


def _execute_dispatch_plan(args: dict, state: dict) -> dict:
    """执行调度计划生成
    如果actions中的type是工具名，则委派给对应工具执行
    """
    stage = args.get("stage", "pre_closure")
    actions = args.get("actions", [])

    tool_names = {"optimize_split_route", "optimize_berth_schedule",
                  "predict_stock_trend", "generate_dispatch_plan"}

    from simulation.constraints import VALID_COMMAND_TYPES

    commands = []
    for action in actions:
        cmd_type = action.get("type", "normal_dispatch")
        params = action.get("params", {})

        if cmd_type in tool_names:
            result = execute_tool(cmd_type, params, state)
            if "commands" in result:
                commands.extend(result["commands"])
        elif cmd_type in VALID_COMMAND_TYPES:
            cmd = {"type": cmd_type, **params}
            if cmd_type == "prioritize_plant" and "plant_ids" in cmd:
                cmd["plant_ids"] = cmd["plant_ids"][:5]
            commands.append(cmd)

    if not commands:
        result = _execute_split_route({"mode": stage}, state)
        commands = result.get("commands", [])

    return {"commands": commands, "status": "success"}
