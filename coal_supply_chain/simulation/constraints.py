"""物理约束校验模块 - 防止LLM幻觉指令被执行
论文核心：TSimOP硬约束使LLM违规率从11.2%降至0%
"""
from typing import Tuple


DUMPER_COMPATIBILITY = {
    "small": ["C64", "C70"],  # CD1-CD9
    "large": ["C80"],          # CD10-CD13
}

VALID_COMMAND_TYPES = [
    "accelerate_loading",
    "divert_trains",
    "reduce_inflow",
    "prioritize_plant",
    "release_berths",
    "normal_dispatch",
]


def validate_command(command: dict, system_state: dict) -> Tuple[bool, str]:
    """
    验证调度指令是否违反物理约束。
    返回 (是否合法, 原因说明)
    """
    cmd_type = command.get("type", "")

    if cmd_type not in VALID_COMMAND_TYPES:
        return False, f"未知指令类型: {cmd_type}"

    if cmd_type == "accelerate_loading":
        return _check_loading_constraints(command, system_state)
    elif cmd_type == "divert_trains":
        return _check_divert_constraints(command, system_state)
    elif cmd_type == "reduce_inflow":
        return _check_reduce_constraints(command, system_state)
    elif cmd_type == "prioritize_plant":
        return _check_priority_constraints(command, system_state)
    elif cmd_type == "release_berths":
        return _check_berth_constraints(command, system_state)

    return True, "OK"


def _check_loading_constraints(cmd: dict, state: dict) -> Tuple[bool, str]:
    """装车约束校验"""
    count = cmd.get("count", 0)
    idle_trains = state["trains"]["idle"]

    if count > idle_trains:
        return False, f"请求装车{count}列，但仅有{idle_trains}列空闲列车"

    if count > 50:
        return False, f"单次装车指令不得超过50列(请求{count}列)"

    port_storage = state["port"]["storage"]
    port_max = state["port"]["max_storage"]
    if port_storage > port_max * 0.9 and not state["port"]["is_closed"]:
        return False, f"港口库存已达{port_storage:.0f}万吨(容量90%以上)，不应继续大量发运至港口"

    return True, "OK"


def _check_divert_constraints(cmd: dict, state: dict) -> Tuple[bool, str]:
    """分流约束校验"""
    count = cmd.get("count", 0)
    running = state["trains"]["running"]

    if count > running:
        return False, f"请求分流{count}列，但仅有{running}列在途列车"

    if count > running * 0.5:
        return False, f"单次分流比例不得超过在途列车的50%"

    return True, "OK"


def _check_reduce_constraints(cmd: dict, state: dict) -> Tuple[bool, str]:
    """减少入流约束校验"""
    ratio = cmd.get("ratio", 0)

    if ratio > 0.8:
        return False, "减流比例不得超过80%(会导致装车站严重拥堵)"

    if ratio < 0:
        return False, "减流比例不能为负"

    port_storage = state["port"]["storage"]
    if port_storage < state["port"]["safety_low"]:
        return False, f"港口库存已低于安全下限({port_storage:.0f}<{state['port']['safety_low']}万吨)，不应继续减流"

    return True, "OK"


def _check_priority_constraints(cmd: dict, state: dict) -> Tuple[bool, str]:
    """优先保障约束校验"""
    plant_ids = cmd.get("plant_ids", [])
    valid_ids = [pp["id"] for pp in state["power_plants"]]

    for pid in plant_ids:
        if pid not in valid_ids:
            return False, f"电厂ID {pid} 不存在"

    if len(plant_ids) > 5:
        return False, "单次优先保障电厂数不超过5家"

    return True, "OK"


def _check_berth_constraints(cmd: dict, state: dict) -> Tuple[bool, str]:
    """泊位约束校验"""
    if state["port"]["is_closed"]:
        return False, "港口已封航，无法执行泊位操作"

    return True, "OK"


def validate_batch_commands(commands: list, system_state: dict) -> list:
    """
    批量校验指令，过滤非法指令并记录违规。
    返回合法指令列表。
    """
    valid_commands = []
    violations = []

    for cmd in commands:
        is_valid, reason = validate_command(cmd, system_state)
        if is_valid:
            valid_commands.append(cmd)
        else:
            violations.append({
                "command": cmd,
                "reason": reason,
            })

    return valid_commands, violations
