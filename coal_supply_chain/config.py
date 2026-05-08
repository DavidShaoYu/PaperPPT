"""全局配置参数 - 基于论文实际数据的简化版本"""

# 仿真时间配置
SIM_DURATION_DAYS = 7
SIM_DURATION_HOURS = SIM_DURATION_DAYS * 24  # 168小时
TIME_STEP = 1  # 小时

# 铁路网络规模（简化）
NUM_LOADING_STATIONS = 10
NUM_INTERMEDIATE_STATIONS = 15
NUM_TRAINS = 120
TRAIN_TYPES = ["C64", "C70", "C80"]
TRAIN_CAPACITY = {"C64": 64 * 58, "C70": 70 * 60, "C80": 80 * 66}  # 吨

# 港口参数（论文表3.3-3.5）
PORT_CONFIG = {
    "num_dumpers": 13,
    "dumper_rate_small": 4800,   # CD1-CD9 吨/小时
    "dumper_rate_large": 8000,   # CD10-CD13 吨/小时
    "total_storage_capacity": 464,  # 万吨
    "safety_low": 140,           # 万吨
    "safety_high": 280,          # 万吨
    "initial_storage": 210,      # 万吨（初始库存，论文表5.2第1天）
    "num_berths": 17,
    "loading_rate": 4050,        # 吨/小时（实际装船效率）
}

# 船舶参数
NUM_SHIPS = 12
SHIP_CAPACITIES = [50000, 70000, 100000, 150000]  # 吨
SHIPPING_TIME_HOURS = {"近海": 24, "中程": 48, "远程": 72}

# 电厂参数
NUM_POWER_PLANTS = 15
POWER_PLANT_CONFIG = {
    "daily_consumption_range": (0.5, 2.0),  # 万吨/天
    "stock_days_range": (7, 15),            # 可用天数
    "min_safe_days": 5,                     # 最低安全天数
}

# 封航场景参数
TYPHOON_CONFIG = {
    "warning_hour": 8,         # 第1天第8小时收到预警（提前48小时预警）
    "closure_start_hour": 48,  # 第3天开始封航
    "closure_end_hour": 120,   # 第5天结束封航(3天封航)
    "closure_duration_days": 3,
}

# LLM配置
LLM_CONFIG = {
    "provider": "custom",
    "model": "minimax-2.7",
    "api_key_env": "LLM_API_KEY",
    "base_url": "http://106.37.198.2:9696/v1",
    "temperature": 0.3,
    "max_tokens": 2000,
}

# 调度决策间隔
DISPATCH_INTERVAL_HOURS = 4  # 每4小时做一次调度决策
