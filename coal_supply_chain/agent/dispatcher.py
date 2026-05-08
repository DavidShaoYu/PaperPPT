"""调度Agent主逻辑 - 决策阶梯化 (论文4.4节核心)
实现"态势感知→逻辑判断→工具调用→约束验证→指令下发"的工程化闭环
"""
import json
from typing import Optional

from config import TYPHOON_CONFIG
from agent.llm_client import LLMClient, MockLLMClient
from agent.tools import DISPATCH_TOOLS, execute_tool
from agent.prompts.system_prompt import SYSTEM_PROMPT
from agent.prompts.stage1_pre import format_stage1_prompt
from agent.prompts.stage2_during import format_stage2_prompt
from agent.prompts.stage3_recovery import format_stage3_prompt
from simulation.constraints import validate_batch_commands


class DispatcherAgent:
    """大模型驱动的智能调度Agent"""

    def __init__(self, use_real_llm: bool = False, provider: str = "custom"):
        if use_real_llm:
            self.llm = LLMClient(provider=provider)
        else:
            self.llm = MockLLMClient()

        self.decision_log = []
        self.total_violations = 0
        self.total_decisions = 0

    def dispatch(self, state: dict, current_hour: float) -> list:
        """
        主调度入口 - 决策阶梯化
        根据当前阶段选择对应Prompt和策略
        """
        self.total_decisions += 1
        stage = self._determine_stage(state, current_hour)
        prompt = self._build_prompt(stage, state)

        if isinstance(self.llm, MockLLMClient):
            commands = self._mock_decision(stage, state)
        else:
            commands = self._llm_decision(prompt, state)

        valid_commands, violations = validate_batch_commands(commands, state)
        self.total_violations += len(violations)

        self.decision_log.append({
            "hour": current_hour,
            "stage": stage,
            "commands_generated": len(commands),
            "commands_valid": len(valid_commands),
            "violations": violations,
        })

        return valid_commands

    def _determine_stage(self, state: dict, current_hour: float) -> str:
        """判断当前所处阶段"""
        typhoon = state["typhoon"]

        if typhoon["is_active"]:
            return "during_closure"
        elif typhoon["warning_received"] and current_hour < TYPHOON_CONFIG["closure_start_hour"]:
            return "pre_closure"
        elif current_hour >= TYPHOON_CONFIG["closure_end_hour"]:
            return "recovery"
        else:
            return "normal"

    def _build_prompt(self, stage: str, state: dict) -> str:
        """构建对应阶段的结构化Prompt"""
        if stage == "pre_closure":
            return format_stage1_prompt(state)
        elif stage == "during_closure":
            return format_stage2_prompt(state)
        elif stage == "recovery":
            return format_stage3_prompt(state)
        else:
            return "当前为正常运营阶段，请执行常规调度。"

    def _llm_decision(self, prompt: str, state: dict) -> list:
        """通过真实LLM生成决策"""
        stage = self._determine_stage(state, state["current_hour"])
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            response = self.llm.chat_with_tools(messages, DISPATCH_TOOLS)
        except Exception as e:
            print(f"    [LLM调用异常: {e}，使用备用策略]")
            return self._mock_decision(stage, state)

        commands = []
        if response["tool_calls"]:
            for tc in response["tool_calls"]:
                print(f"    [LLM Tool Call] {tc['name']}({tc['arguments']})")
                result = execute_tool(tc["name"], tc["arguments"], state)
                if "commands" in result:
                    commands.extend(result["commands"])
        else:
            print(f"    [LLM未调用工具，使用备用策略] 回复: {(response.get('content') or '')[:80]}")
            return self._mock_decision(stage, state)

        if not commands:
            print(f"    [工具未返回有效指令，使用备用策略]")
            return self._mock_decision(stage, state)

        return commands

    def _mock_decision(self, stage: str, state: dict) -> list:
        """模拟LLM决策（用于无API Key时的演示）"""
        result = execute_tool(
            "optimize_split_route",
            {"mode": self._stage_to_mode(stage)},
            state
        )
        return result.get("commands", [{"type": "normal_dispatch"}])

    def _stage_to_mode(self, stage: str) -> str:
        mapping = {
            "pre_closure": "pre_closure_defense",
            "during_closure": "supply_assurance",
            "recovery": "recovery",
            "normal": "recovery",
        }
        return mapping.get(stage, "recovery")

    def get_violation_rate(self) -> float:
        """获取约束违规率"""
        if self.total_decisions == 0:
            return 0.0
        return self.total_violations / max(1, self.total_decisions * 3)


def llm_dispatch_strategy(state: dict, current_hour: float) -> list:
    """供仿真引擎调用的函数式接口"""
    if not hasattr(llm_dispatch_strategy, '_agent'):
        llm_dispatch_strategy._agent = DispatcherAgent(use_real_llm=False)
    return llm_dispatch_strategy._agent.dispatch(state, current_hour)


def create_llm_strategy(use_real_llm: bool = False,
                        provider: str = "custom") -> callable:
    """创建LLM调度策略函数"""
    agent = DispatcherAgent(use_real_llm=use_real_llm, provider=provider)

    def strategy(state: dict, current_hour: float) -> list:
        return agent.dispatch(state, current_hour)

    strategy._agent = agent
    return strategy
