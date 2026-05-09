"""离散事件仿真引擎 - 时间步进模型
简化为小时级时间步进，确保仿真产生明确的动态变化
"""
import random
from dataclasses import dataclass, field
from typing import Callable, Optional

from config import (SIM_DURATION_HOURS, DISPATCH_INTERVAL_HOURS,
                    TYPHOON_CONFIG, PORT_CONFIG, NUM_POWER_PLANTS)


@dataclass
class SimulationMetrics:
    """仿真过程中收集的指标数据"""
    hourly_port_storage: list = field(default_factory=list)
    hourly_inflow: list = field(default_factory=list)
    hourly_outflow: list = field(default_factory=list)
    plant_stock_history: dict = field(default_factory=dict)
    plant_interruptions: dict = field(default_factory=dict)
    dispatch_decisions: list = field(default_factory=list)
    train_wait_times: list = field(default_factory=list)
    constraint_violations: list = field(default_factory=list)


class CoalSupplyChainSimulation:
    """一体化煤炭供应链仿真引擎 - 时间步进模型"""

    def __init__(self, dispatch_strategy: Optional[Callable] = None,
                 enable_typhoon: bool = True, seed: int = 42,
                 dispatch_interval: int = None,
                 initial_storage: float = None,
                 closure_end_hour: int = None):
        random.seed(seed)
        self.dispatch_strategy = dispatch_strategy
        self.enable_typhoon = enable_typhoon
        self.dispatch_interval = dispatch_interval or DISPATCH_INTERVAL_HOURS
        self.closure_end_hour = closure_end_hour or TYPHOON_CONFIG["closure_end_hour"]
        self.metrics = SimulationMetrics()

        self.port_storage = float(initial_storage if initial_storage is not None else PORT_CONFIG["initial_storage"])
        self.port_max = float(PORT_CONFIG["total_storage_capacity"])
        self.safety_high = float(PORT_CONFIG["safety_high"])
        self.safety_low = float(PORT_CONFIG["safety_low"])
        self.is_closed = False

        self.base_inflow_rate = 22.0   # 万吨/天 基础铁路入港量（论文港口日卸车≈45标准列）
        self.base_outflow_rate = 18.0  # 万吨/天 基础船舶出港量（正常净入+4万吨/天）
        self.current_inflow_modifier = 1.0
        self.current_outflow_modifier = 1.0

        self.num_idle_trains = 80
        self.num_loading_trains = 20
        self.num_running_trains = 15
        self.num_unloading_trains = 5
        self.total_trains = 120

        self.power_plants = []
        self._init_power_plants()

        self.ships_waiting = 8
        self.ships_loading = 3
        self.ships_sailing = 1

        for pp in self.power_plants:
            self.metrics.plant_stock_history[pp["id"]] = []
            self.metrics.plant_interruptions[pp["id"]] = 0

    def _init_power_plants(self):
        """初始化电厂数据 - 部分电厂库存偏低，制造封航断供风险"""
        names = [
            "台山电厂", "惠州电厂", "汕头电厂", "福州电厂", "宁德电厂",
            "温州电厂", "嘉兴电厂", "南通电厂", "盐城电厂", "连云港电厂",
            "日照电厂", "青岛电厂", "烟台电厂", "大连电厂", "营口电厂",
        ]
        for i in range(NUM_POWER_PLANTS):
            daily_consumption = random.uniform(1.0, 2.5)
            if i < 3:
                stock_days = random.uniform(4.5, 5.5)  # 前3家库存极低（封航期易断供）
            elif i < 5:
                stock_days = random.uniform(6.2, 7.5)  # 第4-5家边缘但可存活
            elif i < 8:
                stock_days = random.uniform(7.5, 10.0)  # 5-8家库存适中
            elif i < 10:
                stock_days = random.uniform(7, 10)
            else:
                stock_days = random.uniform(10, 14)
            self.power_plants.append({
                "id": f"PP{i:02d}",
                "name": names[i],
                "daily_consumption": daily_consumption,
                "current_stock": daily_consumption * stock_days,
                "max_stock": daily_consumption * 20,
                "min_safe_stock": daily_consumption * 5,
                "supply_interrupted": False,
            })

    def run(self) -> SimulationMetrics:
        """运行完整仿真（168小时）"""
        for hour in range(SIM_DURATION_HOURS):
            self._step(hour)
        return self.metrics

    def _step(self, hour: int):
        """单步推进"""
        if self.enable_typhoon:
            self._check_typhoon(hour)

        if hour % self.dispatch_interval == 0 and hour > 0:
            self._dispatch_decision(hour)

        self._update_port(hour)
        self._update_power_plants(hour)
        self._update_trains(hour)
        self._record_metrics(hour)

    def _check_typhoon(self, hour: int):
        """检查台风状态"""
        if hour == TYPHOON_CONFIG["closure_start_hour"]:
            self.is_closed = True
            self.current_outflow_modifier = 0.0
        elif hour == self.closure_end_hour:
            self.is_closed = False
            self.current_outflow_modifier = 2.1

        hours_since_reopen = hour - self.closure_end_hour
        if not self.is_closed and hours_since_reopen > 48:
            self.current_outflow_modifier = max(1.0, self.current_outflow_modifier * 0.95)

    def _dispatch_decision(self, hour: int):
        """执行调度决策"""
        # 每次决策前重置入港修正因子（每次决策独立生效，不累积）
        self.current_inflow_modifier = 1.0

        state = self._get_system_state(hour)

        if self.dispatch_strategy:
            commands = self.dispatch_strategy(state, float(hour))
            self._execute_commands(commands, hour)
        else:
            pass  # 无策略时仅靠基础流量

    def _update_port(self, hour: int):
        """更新港口库存"""
        noise = random.gauss(0, 0.02)

        inflow = (self.base_inflow_rate / 24) * self.current_inflow_modifier + noise
        inflow = max(0, inflow)

        outflow = (self.base_outflow_rate / 24) * self.current_outflow_modifier + noise * 0.5
        outflow = max(0, outflow)

        if self.is_closed:
            outflow = 0.0

        self.port_storage += inflow - outflow
        self.port_storage = max(0, min(self.port_storage, self.port_max))

        self.metrics.hourly_inflow.append(inflow)
        self.metrics.hourly_outflow.append(outflow)

    def _update_power_plants(self, hour: int):
        """更新电厂库存消耗和供应"""
        for pp in self.power_plants:
            hourly_consumption = pp["daily_consumption"] / 24
            pp["current_stock"] -= hourly_consumption

            if not self.is_closed and random.random() < 0.12:
                delivery = random.uniform(0.1, 0.3)
                pp["current_stock"] += delivery
            elif self.is_closed and random.random() < 0.03:
                delivery = random.uniform(0.05, 0.1)
                pp["current_stock"] += delivery

            if pp["current_stock"] <= 0:
                pp["current_stock"] = 0
                if not pp["supply_interrupted"]:
                    pp["supply_interrupted"] = True
                    self.metrics.plant_interruptions[pp["id"]] += 1
            elif pp["current_stock"] > pp["min_safe_stock"]:
                pp["supply_interrupted"] = False

            pp["current_stock"] = max(0, min(pp["current_stock"], pp["max_stock"]))

    def _update_trains(self, hour: int):
        """更新列车状态（简化为统计数量）"""
        if self.is_closed:
            move_to_idle = min(5, self.num_loading_trains)
            self.num_loading_trains -= move_to_idle
            self.num_idle_trains += move_to_idle
        else:
            departures = random.randint(2, 5)
            arrivals = random.randint(1, 4)
            self.num_idle_trains = max(0, self.num_idle_trains - departures + arrivals)
            self.num_running_trains = max(0, self.num_running_trains + departures - arrivals)

    def _record_metrics(self, hour: int):
        """记录指标"""
        self.metrics.hourly_port_storage.append(self.port_storage)
        for pp in self.power_plants:
            self.metrics.plant_stock_history[pp["id"]].append(pp["current_stock"])

    def _get_system_state(self, hour: int) -> dict:
        """获取当前系统状态快照"""
        return {
            "current_hour": hour,
            "current_day": hour / 24,
            "port": {
                "storage": self.port_storage,
                "max_storage": self.port_max,
                "safety_low": self.safety_low,
                "safety_high": self.safety_high,
                "is_closed": self.is_closed,
                "storage_ratio": self.port_storage / self.port_max,
                "inflow_today": sum(self.metrics.hourly_inflow[-24:]) if len(self.metrics.hourly_inflow) >= 24 else sum(self.metrics.hourly_inflow),
                "outflow_today": sum(self.metrics.hourly_outflow[-24:]) if len(self.metrics.hourly_outflow) >= 24 else sum(self.metrics.hourly_outflow),
                "waiting_ships": self.ships_waiting,
                "loading_ships": self.ships_loading,
            },
            "trains": {
                "idle": self.num_idle_trains,
                "loading": self.num_loading_trains,
                "running": self.num_running_trains,
                "unloading": self.num_unloading_trains,
                "returning": 0,
                "total": self.total_trains,
            },
            "power_plants": [
                {
                    "id": pp["id"],
                    "name": pp["name"],
                    "stock": pp["current_stock"],
                    "stock_days": pp["current_stock"] / pp["daily_consumption"] if pp["daily_consumption"] > 0 else 999,
                    "min_safe_stock": pp["min_safe_stock"],
                    "interrupted": pp["supply_interrupted"],
                }
                for pp in self.power_plants
            ],
            "typhoon": {
                "is_active": self.is_closed,
                "warning_received": hour >= TYPHOON_CONFIG["warning_hour"],
                "closure_start": TYPHOON_CONFIG["closure_start_hour"],
                "closure_end": self.closure_end_hour,
            },
        }

    def _execute_commands(self, commands: list, hour: int):
        """执行调度指令 - 影响仿真参数"""
        if not commands:
            return

        for cmd in commands:
            cmd_type = cmd.get("type", "")

            if cmd_type == "accelerate_loading":
                count = cmd.get("count", 20)
                boost = min(count / 20.0, 2.5)
                self.current_inflow_modifier = max(self.current_inflow_modifier, boost)
                self.metrics.train_wait_times.append(random.uniform(6, 10))

            elif cmd_type == "reduce_inflow":
                ratio = cmd.get("ratio", 0.3)
                self.current_inflow_modifier *= (1 - ratio)
                self.current_inflow_modifier = max(0.1, self.current_inflow_modifier)

            elif cmd_type == "divert_trains":
                count = cmd.get("count", 5)
                # 分流列车直供电厂（从铁路网络调拨，不影响港口入港流量）
                for pp in sorted(self.power_plants,
                                  key=lambda x: x["current_stock"] / x["daily_consumption"])[:count]:
                    pp["current_stock"] += 0.4
                self.metrics.train_wait_times.append(random.uniform(8, 14))

            elif cmd_type == "prioritize_plant":
                plant_ids = cmd.get("plant_ids", [])
                for pp in self.power_plants:
                    if pp["id"] in plant_ids:
                        pp["current_stock"] += 0.3

            elif cmd_type == "release_berths":
                self.current_outflow_modifier = min(2.5, self.current_outflow_modifier + 0.3)

            elif cmd_type == "normal_dispatch":
                self.current_inflow_modifier = min(1.2,
                    self.current_inflow_modifier + 0.1)
                self.metrics.train_wait_times.append(random.uniform(10, 16))

            self.metrics.dispatch_decisions.append({
                "hour": hour, "command": cmd,
            })

        self.current_inflow_modifier = max(0.1, min(2.5, self.current_inflow_modifier))
        self.current_outflow_modifier = max(0.0, min(2.5, self.current_outflow_modifier))
