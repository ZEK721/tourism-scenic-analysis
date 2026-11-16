"""
数据加载模块
============
负责读取预处理后的 data/tourism_flow.csv，并按城市、季节、同行类型筛选。
所有异常都在此层转换为带有中文提示的 DataLoadError，方便界面层友好展示。
"""

from functools import lru_cache
from pathlib import Path

import pandas as pd

try:  # 兼容 `streamlit run app.py`（从项目根目录导入）与直接运行本文件
    from src.config import (
        ALL_VALUE,
        COL_CITY,
        COL_END_SPOT,
        COL_PARTNER,
        COL_SEASON,
        COL_START_SPOT,
        COL_WEIGHT,
        FLOW_COLUMNS,
        FLOW_DATA_PATH,
        PARTNER_OPTIONS,
        SEASON_OPTIONS,
    )
except ImportError:  # pragma: no cover - 仅用于脚本直接运行场景
    from config import (  # type: ignore
        ALL_VALUE,
        COL_CITY,
        COL_END_SPOT,
        COL_PARTNER,
        COL_SEASON,
        COL_START_SPOT,
        COL_WEIGHT,
        FLOW_COLUMNS,
        FLOW_DATA_PATH,
        PARTNER_OPTIONS,
        SEASON_OPTIONS,
    )


class DataLoadError(Exception):
    """数据加载相关异常：文件缺失、格式错误、字段不全等。"""


def _empty_flow_frame() -> pd.DataFrame:
    """返回带标准列的空表，保证后续分析、绘图不会因缺列报错。"""
    return pd.DataFrame(columns=FLOW_COLUMNS)


@lru_cache(maxsize=4)
def _read_csv_cached(path_str: str, modified_time: float) -> pd.DataFrame:
    """
    按「路径 + 文件修改时间」缓存读取结果。
    修改时间参与缓存键，文件重新生成后会自动重新读取，避免读到旧数据。
    """
    path = Path(path_str)
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        # 兼容用户手动另存为 GBK 的情况
        df = pd.read_csv(path, encoding="gbk")
    except Exception as exc:
        raise DataLoadError(
            f"读取数据文件失败：{path.name}。请确认文件未被其他程序占用，"
            f"或重新运行 python src/build_dataset.py 生成数据。\n错误详情：{exc}"
        ) from exc
    return df


def _load_raw_data() -> pd.DataFrame:
    """读取并校验原始分析表，返回清洗后的完整 DataFrame（带缓存）。"""
    path = FLOW_DATA_PATH
    if not path.exists():
        raise DataLoadError(
            "未找到分析数据文件 data/tourism_flow.csv。\n"
            "请先完成数据准备：\n"
            "1. 将解压后的数据集放入 data/raw_data/（包含 01、02、03 三个文件夹）；\n"
            "2. 在项目根目录运行：python src/build_dataset.py"
        )

    try:
        modified_time = path.stat().st_mtime
    except OSError as exc:
        raise DataLoadError(f"无法访问数据文件：{path}。错误详情：{exc}") from exc

    df = _read_csv_cached(str(path), modified_time).copy()

    # 字段完整性校验
    missing_columns = [col for col in FLOW_COLUMNS if col not in df.columns]
    if missing_columns:
        raise DataLoadError(
            f"数据文件字段不完整，缺少：{', '.join(missing_columns)}。\n"
            "请重新运行 python src/build_dataset.py 生成标准格式数据。"
        )

    if df.empty:
        raise DataLoadError(
            "数据文件为空，没有可分析的数据。\n"
            "请检查 data/raw_data/ 中的原始文件是否完整，并重新运行 python src/build_dataset.py。"
        )

    # 统一类型：文本列转字符串，权重转数值
    df[COL_START_SPOT] = df[COL_START_SPOT].astype(str).str.strip()
    df[COL_END_SPOT] = df[COL_END_SPOT].astype(str).str.strip()
    df[COL_CITY] = df[COL_CITY].astype(str).str.strip()
    df[COL_SEASON] = df[COL_SEASON].astype(str).str.strip()
    df[COL_PARTNER] = df[COL_PARTNER].astype(str).str.strip()
    df[COL_WEIGHT] = pd.to_numeric(df[COL_WEIGHT], errors="coerce")

    # 丢弃关键字段为空的脏数据
    df = df.dropna(subset=[COL_START_SPOT, COL_END_SPOT, COL_CITY, COL_WEIGHT])
    df = df[df[COL_WEIGHT] > 0]
    return df.reset_index(drop=True)


def get_available_cities() -> list[str]:
    """
    获取数据中出现过的全部城市（用于侧边栏多选框）。
    返回值按拼音/字符排序，保证每次展示顺序稳定。
    """
    df = _load_raw_data()
    cities = df[COL_CITY].dropna().unique().tolist()
    return sorted(city for city in cities if city and city.lower() != "nan")


def load_flow_data(
    cities: list[str] | None = None,
    season: str = ALL_VALUE,
    partner_type: str = ALL_VALUE,
) -> pd.DataFrame:
    """
    读取并筛选游客流动数据。

    参数：
        cities:       城市名称列表；传 None 或空列表表示不限制城市。
        season:       all / spring / summer / autumn / winter。
        partner_type: all / alone / family / friend。

    返回：
        筛选后的 DataFrame，列：start_spot, end_spot, weight, city, season, partner_type。
        若筛选结果为空，返回带标准列的空表，并在 df.attrs["notice"] 中附带提示。

    说明：
        原始数据中的「完整网络」行 season=all 且 partner_type=all；
        季节分组行仅 season 有值，同行类型分组行仅 partner_type 有值。
        因此两个维度同时选择具体值时无法交叉过滤，本函数优先按季节筛选并给出提示。
    """
    # 参数校验：传入非法值时给出明确提示，而不是静默返回空表
    if season not in SEASON_OPTIONS:
        raise DataLoadError(f"无效的季节参数：{season}，可选值为 {SEASON_OPTIONS}。")
    if partner_type not in PARTNER_OPTIONS:
        raise DataLoadError(
            f"无效的同行类型参数：{partner_type}，可选值为 {PARTNER_OPTIONS}。"
        )

    df = _load_raw_data()
    notice: str | None = None

    # ---------------------------------------------------------------
    # 按维度筛选：all 表示使用「完整网络」数据，避免与子分组重复计数
    # ---------------------------------------------------------------
    if season != ALL_VALUE and partner_type != ALL_VALUE:
        # 数据集不存在 season 与 partner_type 的交叉分组，只能二选一
        df = df[df[COL_SEASON] == season]
        notice = (
            "原始数据集按季节、同行类型分别统计，不存在交叉分组。"
            f"当前已按季节「{season}」筛选，同行类型「{partner_type}」筛选未生效。"
        )
    elif season != ALL_VALUE:
        df = df[df[COL_SEASON] == season]
    elif partner_type != ALL_VALUE:
        df = df[df[COL_PARTNER] == partner_type]
    else:
        # 两个维度都选 all：使用完整网络数据（season=all 且 partner_type=all）
        df = df[(df[COL_SEASON] == ALL_VALUE) & (df[COL_PARTNER] == ALL_VALUE)]

    # ---------------------------------------------------------------
    # 按城市筛选：空列表视为全部城市
    # ---------------------------------------------------------------
    if cities:
        city_set = {str(city).strip() for city in cities if str(city).strip()}
        if city_set:
            df = df[df[COL_CITY].isin(city_set)]

    result = df.reset_index(drop=True)
    if result.empty and notice is None:
        notice = "当前筛选条件下没有匹配的流动记录，请调整城市、季节或同行类型。"

    # 通过 attrs 把提示信息传给界面层（不污染数据列）
    result.attrs["notice"] = notice
    return result
