"""
项目统一配置模块。

说明：
- 所有路径均基于项目根目录动态计算，不写死绝对路径，方便整体迁移。
- 所有可选值（城市除外，城市从数据中动态读取）集中在此处维护。
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# 路径配置（全部使用相对项目根目录的相对路径）
# ---------------------------------------------------------------------------
# 项目根目录：src 目录的上一级
BASE_DIR = Path(__file__).resolve().parents[1]
# 数据目录
DATA_DIR = BASE_DIR / "data"
# 原始数据目录（解压后的数据集放在这里）
RAW_DATA_DIR = DATA_DIR / "raw_data"
# 预处理后生成的分析表
FLOW_DATA_PATH = DATA_DIR / "tourism_flow.csv"

# ---------------------------------------------------------------------------
# 数据字段常量（预处理后统一字段）
# ---------------------------------------------------------------------------
COL_START_SPOT = "start_spot"      # 起点景点名称
COL_END_SPOT = "end_spot"          # 终点景点名称
COL_WEIGHT = "weight"              # 流动权重（人次）
COL_CITY = "city"                  # 所属城市（同城流动，起点终点城市一致）
COL_SEASON = "season"              # 季节：all / spring / summer / autumn / winter
COL_PARTNER = "partner_type"       # 同行类型：all / alone / family / friend

# 最终分析表的标准列顺序
FLOW_COLUMNS = [
    COL_START_SPOT,
    COL_END_SPOT,
    COL_WEIGHT,
    COL_CITY,
    COL_SEASON,
    COL_PARTNER,
]

# ---------------------------------------------------------------------------
# 可选值列表
# ---------------------------------------------------------------------------
ALL_VALUE = "all"  # “全部”统一用 all 表示，与预处理数据中的填充值保持一致

# 季节可选值（all 表示完整网络 / 不区分季节）
SEASON_OPTIONS = [ALL_VALUE, "spring", "summer", "autumn", "winter"]

# 季节中文名称映射，用于图表展示
SEASON_LABELS = {
    ALL_VALUE: "全部季节",
    "spring": "春季",
    "summer": "夏季",
    "autumn": "秋季",
    "winter": "冬季",
}

# 同行类型可选值（all 表示完整网络 / 不区分同行类型）
PARTNER_OPTIONS = [ALL_VALUE, "alone", "family", "friend"]

# 同行类型中文名称映射，用于图表展示
PARTNER_LABELS = {
    ALL_VALUE: "全部同行类型",
    "alone": "独自出行",
    "family": "家庭出游",
    "friend": "朋友出游",
}

# ---------------------------------------------------------------------------
# 可视化与计算参数
# ---------------------------------------------------------------------------
# 网络图默认展示的节点数量（按景点热度取前 N 个）
DEFAULT_NETWORK_NODES = 40
# 热度榜 / 中心性榜默认展示条数
DEFAULT_TOP_N = 20
# 网络图布局随机种子，保证每次布局稳定可复现
NETWORK_LAYOUT_SEED = 42
# 图表统一中文字体（优先使用系统自带中文字体）
CHINESE_FONT_FAMILY = "Microsoft YaHei, SimHei, PingFang SC, WenQuanYi Micro Hei, Arial, sans-serif"
