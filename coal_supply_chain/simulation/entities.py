"""供应链核心实体定义"""
from dataclasses import dataclass, field
from typing import Optional
import random


@dataclass
class Train:
    id: str
    train_type: str       # C64/C70/C80
    capacity: int         # 总载重(吨)
    status: str = "idle"  # idle/loading/running/unloading/returning
    position: str = ""
    destination: str = ""
    coal_type: str = ""
    load_amount: float = 0.0
    travel_remaining: float = 0.0  # 剩余行驶时间(小时)


@dataclass
class LoadingStation:
    id: str
    name: str
    line: str             # 所属线路
    coal_types: list = field(default_factory=list)
    compatible_trains: list = field(default_factory=list)  # 可装车型
    loading_rate: float = 0.0   # 吨/小时
    queue: list = field(default_factory=list)
    daily_capacity: float = 0.0  # 日装车能力(万吨)
    current_stock: float = 0.0   # 当前煤矿库存(万吨)


@dataclass
class RailwaySection:
    id: str
    from_station: str
    to_station: str
    distance_km: float
    travel_time_hours: float
    max_capacity: int = 10       # 最大同时通过列车数
    current_trains: int = 0
    has_maintenance_window: bool = False
    maintenance_start: int = 0   # 天窗开始时刻
    maintenance_duration: int = 4  # 天窗时长(小时)


@dataclass
class Dumper:
    id: str
    dumper_type: str       # small(CD1-9) / large(CD10-13)
    rate: float            # 吨/小时
    compatible_types: list = field(default_factory=list)
    status: str = "idle"   # idle/working/maintenance


@dataclass
class Berth:
    id: str
    loading_rate: float    # 吨/小时
    max_ship_size: float   # 最大可靠泊吨位
    status: str = "idle"   # idle/occupied
    current_ship: Optional[str] = None
    remaining_time: float = 0.0


@dataclass
class Ship:
    id: str
    capacity: float        # 载重(吨)
    destination: str       # 目的电厂/区域
    status: str = "waiting"  # waiting/loading/sailing/arrived
    load_amount: float = 0.0
    travel_time: float = 0.0
    remaining_time: float = 0.0


@dataclass
class PowerPlant:
    id: str
    name: str
    plant_type: str        # 直供/水运
    daily_consumption: float  # 日耗煤量(万吨)
    current_stock: float      # 当前库存(万吨)
    max_stock: float          # 最大库存(万吨)
    min_safe_stock: float     # 最低安全库存(万吨)
    supply_method: str = "ship"  # ship/rail
    supply_interrupted: bool = False
    days_without_supply: int = 0


@dataclass
class PortState:
    total_storage: float = 200.0   # 当前总库存(万吨)
    max_storage: float = 464.0
    safety_low: float = 140.0
    safety_high: float = 280.0
    is_closed: bool = False
    inflow_today: float = 0.0      # 今日入港量
    outflow_today: float = 0.0     # 今日出港量
    dumpers: list = field(default_factory=list)
    berths: list = field(default_factory=list)
    ship_queue: list = field(default_factory=list)


def create_default_entities():
    """创建默认仿真实体集"""
    from config import (NUM_TRAINS, NUM_SHIPS, NUM_POWER_PLANTS,
                        TRAIN_CAPACITY, PORT_CONFIG, POWER_PLANT_CONFIG)

    trains = []
    for i in range(NUM_TRAINS):
        t_type = random.choice(["C64", "C70", "C80"])
        trains.append(Train(
            id=f"T{i:03d}",
            train_type=t_type,
            capacity=TRAIN_CAPACITY[t_type],
        ))

    loading_stations = []
    station_configs = [
        ("LS01", "大柳塔", "包西线", ["动力煤"], ["C70", "C80"], 6000),
        ("LS02", "上湾", "包西线", ["动力煤"], ["C80"], 8000),
        ("LS03", "尔林兔", "包西线", ["动力煤", "混煤"], ["C70", "C80"], 5000),
        ("LS04", "巴图塔", "大准线", ["动力煤"], ["C64", "C70"], 4500),
        ("LS05", "点岱沟", "大准线", ["块煤"], ["C64", "C70"], 4000),
        ("LS06", "塔然高勒", "朔黄线", ["动力煤"], ["C80"], 7000),
        ("LS07", "神池南", "朔黄线", ["动力煤", "混煤"], ["C70", "C80"], 5500),
        ("LS08", "朔州西", "朔黄线", ["混煤"], ["C70"], 4800),
        ("LS09", "准格尔", "准池线", ["动力煤"], ["C80"], 6500),
        ("LS10", "红进塔", "包西线", ["动力煤"], ["C70", "C80"], 5200),
    ]
    for sid, name, line, coals, compat, rate in station_configs:
        loading_stations.append(LoadingStation(
            id=sid, name=name, line=line,
            coal_types=coals, compatible_trains=compat,
            loading_rate=rate, daily_capacity=rate * 20 / 10000,
            current_stock=random.uniform(5, 20),
        ))

    dumpers = []
    for i in range(1, 14):
        if i <= 9:
            dumpers.append(Dumper(
                id=f"CD{i:02d}", dumper_type="small",
                rate=4800, compatible_types=["C64", "C70"],
            ))
        else:
            dumpers.append(Dumper(
                id=f"CD{i:02d}", dumper_type="large",
                rate=8000, compatible_types=["C80"],
            ))

    berths = []
    for i in range(1, 18):
        berths.append(Berth(
            id=f"BT{i:02d}",
            loading_rate=4050,
            max_ship_size=150000 if i <= 5 else 70000,
        ))

    ships = []
    destinations = ["华东电厂群", "华南电厂群", "东南沿海"]
    for i in range(NUM_SHIPS):
        cap = random.choice([50000, 70000, 100000, 150000])
        ships.append(Ship(
            id=f"S{i:02d}",
            capacity=cap,
            destination=random.choice(destinations),
            travel_time=random.choice([24, 36, 48, 72]),
        ))

    power_plants = []
    plant_names = [
        "台山电厂", "惠州电厂", "汕头电厂", "福州电厂", "宁德电厂",
        "温州电厂", "嘉兴电厂", "南通电厂", "盐城电厂", "连云港电厂",
        "日照电厂", "青岛电厂", "烟台电厂", "大连电厂", "营口电厂",
    ]
    for i in range(NUM_POWER_PLANTS):
        daily = random.uniform(
            POWER_PLANT_CONFIG["daily_consumption_range"][0],
            POWER_PLANT_CONFIG["daily_consumption_range"][1],
        )
        stock_days = random.uniform(
            POWER_PLANT_CONFIG["stock_days_range"][0],
            POWER_PLANT_CONFIG["stock_days_range"][1],
        )
        power_plants.append(PowerPlant(
            id=f"PP{i:02d}",
            name=plant_names[i],
            plant_type="水运" if i < 10 else "直供",
            daily_consumption=daily,
            current_stock=daily * stock_days,
            max_stock=daily * 20,
            min_safe_stock=daily * POWER_PLANT_CONFIG["min_safe_days"],
            supply_method="ship" if i < 10 else "rail",
        ))

    port = PortState(
        total_storage=PORT_CONFIG["initial_storage"],
        max_storage=PORT_CONFIG["total_storage_capacity"],
        safety_low=PORT_CONFIG["safety_low"],
        safety_high=PORT_CONFIG["safety_high"],
        dumpers=dumpers,
        berths=berths,
    )

    return {
        "trains": trains,
        "loading_stations": loading_stations,
        "port": port,
        "ships": ships,
        "power_plants": power_plants,
    }
