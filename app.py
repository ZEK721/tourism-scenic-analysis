"""
Streamlit 主程序入口
====================
运行方式（在项目根目录执行）：
    streamlit run app.py
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# 保证从任意工作目录启动时都能正确导入 src 包
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis import compute_degree_centrality, compute_spot_heat  # noqa: E402
from src.config import (  # noqa: E402
    ALL_VALUE,
    DEFAULT_NETWORK_NODES,
    DEFAULT_TOP_N,
    PARTNER_LABELS,
    PARTNER_OPTIONS,
    SEASON_LABELS,
    SEASON_OPTIONS,
)
from src.data_loader import (  # noqa: E402
    DataLoadError,
    get_available_cities,
    load_flow_data,
)
from src.visualization import (  # noqa: E402
    build_centrality_bar_figure,
    build_flow_network_figure,
    build_heat_bar_figure,
)

# ---------------------------------------------------------------------------
# 页面基础配置
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="游客流动网络分析平台",
    page_icon="🧭",
    layout="wide",
)

# ---------------------------------------------------------------------------
# 带缓存的数据读取函数（避免每次交互都重新读取 CSV）
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def cached_city_options() -> list[str]:
    """缓存城市列表。"""
    return get_available_cities()


@st.cache_data(show_spinner="正在加载游客流动数据...")
def cached_flow_data(cities: tuple[str, ...], season: str, partner_type: str) -> pd.DataFrame:
    """缓存筛选结果；参数需可哈希，所以城市列表以元组传入。"""
    return load_flow_data(list(cities), season, partner_type)


# ---------------------------------------------------------------------------
# 表格展示辅助函数
# ---------------------------------------------------------------------------
def flow_preview(df: pd.DataFrame, limit: int = 200) -> pd.DataFrame:
    """将原始字段转为中文表头，便于阅读。"""
    view = df.head(limit).copy()
    view["season"] = view["season"].map(lambda value: SEASON_LABELS.get(value, value))
    view["partner_type"] = view["partner_type"].map(
        lambda value: PARTNER_LABELS.get(value, value)
    )
    view = view.rename(columns={
        "start_spot": "起点景点",
        "end_spot": "终点景点",
        "weight": "流动权重",
        "city": "城市",
        "season": "季节",
        "partner_type": "同行类型",
    })
    return view[["城市", "起点景点", "终点景点", "流动权重", "季节", "同行类型"]]


def heat_table(heat_df: pd.DataFrame, limit: int = 200) -> pd.DataFrame:
    """景点热度表转为中文表头。"""
    return heat_df.head(limit).rename(columns={
        "rank": "排名",
        "spot": "景点",
        "city": "城市",
        "out_weight": "流出流量",
        "in_weight": "流入流量",
        "total_weight": "总热度",
    })


def centrality_table(centrality_df: pd.DataFrame, limit: int = 200) -> pd.DataFrame:
    """节点中心性表转为中文表头。"""
    return centrality_df.head(limit).rename(columns={
        "rank": "排名",
        "spot": "景点",
        "city": "城市",
        "degree": "度数（入度+出度）",
        "centrality": "度中心性",
    })


# ---------------------------------------------------------------------------
# 页面标题与数据加载
# ---------------------------------------------------------------------------
st.title("🧭 游客流动网络分析平台")
st.caption(
    "基于北大游客流动网络数据集（China tourist mobility networks），"
    "分析同城景点之间的游客转移关系、景点热度与节点中心性。"
)

try:
    city_options = cached_city_options()
except DataLoadError as exc:
    st.error(str(exc))
    st.stop()

# ---------------------------------------------------------------------------
# 侧边栏筛选组件
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("筛选条件")

    selected_cities = st.multiselect(
        "城市（可多选）",
        options=city_options,
        default=[],
        help="不选择表示全部城市；支持输入关键词搜索。",
    )
    st.caption(f"共 {len(city_options)} 个城市可选，不选表示全部城市。")

    season = st.selectbox(
        "季节",
        options=SEASON_OPTIONS,
        index=0,
        format_func=lambda value: f"{value}（{SEASON_LABELS.get(value, value)}）",
    )

    partner_type = st.selectbox(
        "同行类型",
        options=PARTNER_OPTIONS,
        index=0,
        format_func=lambda value: f"{value}（{PARTNER_LABELS.get(value, value)}）",
    )

    st.divider()
    st.caption(
        "说明：原始数据按季节、同行类型分别统计，两者不支持交叉筛选；"
        "若同时选择具体值，将优先按季节筛选。"
    )

# ---------------------------------------------------------------------------
# 按筛选条件取数
# ---------------------------------------------------------------------------
try:
    df = cached_flow_data(tuple(selected_cities), season, partner_type)
except DataLoadError as exc:
    st.error(str(exc))
    st.stop()

# 展示数据加载提示（如空结果、无法交叉筛选等）
notice = df.attrs.get("notice") if hasattr(df, "attrs") else None
if notice:
    st.info(notice)

city_text = "、".join(selected_cities) if selected_cities else "全部城市"
st.markdown(
    f"**当前筛选：** 城市：{city_text} ｜ 季节：{SEASON_LABELS.get(season, season)} ｜ "
    f"同行类型：{PARTNER_LABELS.get(partner_type, partner_type)}"
)

# 预先计算分析结果（各 Tab 共用，避免重复计算）
heat_df = compute_spot_heat(df)
centrality_df = compute_degree_centrality(df)

# ---------------------------------------------------------------------------
# Tab 布局
# ---------------------------------------------------------------------------
tab_overview, tab_network, tab_heat, tab_centrality = st.tabs([
    "📋 数据概览",
    "🕸️ 游客流动网络图",
    "🔥 景点热度排名",
    "📐 节点中心性分析",
])

# ============================ Tab1：数据概览 ============================
with tab_overview:
    st.subheader("数据概览")

    col_records, col_spots = st.columns(2)
    total_records = len(df)
    spot_count = (
        pd.concat([df["start_spot"], df["end_spot"]]).nunique() if not df.empty else 0
    )
    col_records.metric("总流动记录数", f"{total_records:,}")
    col_spots.metric("涉及景点数量", f"{spot_count:,}")

    if df.empty:
        st.warning("当前筛选条件下没有数据，请调整侧边栏筛选条件。")
    else:
        st.markdown("#### 数据预览")
        st.caption(f"仅展示前 {min(200, total_records)} 条记录，共 {total_records:,} 条。")
        st.dataframe(
            flow_preview(df),
            width="stretch",
            hide_index=True,
            height=420,
        )

# ========================= Tab2：游客流动网络图 =========================
with tab_network:
    st.subheader("游客流动网络图")
    st.caption(
        f"节点为景点，连线为同城景点间的游客转移（方向由起点指向终点）；"
        f"为保证可读性，默认展示热度前 {DEFAULT_NETWORK_NODES} 个景点。"
        "鼠标悬浮节点或连线中点可查看城市、流动权重等信息。"
    )

    # 数据过少时给出提示，避免绘图报错
    valid_spot_count = (
        pd.concat([df["start_spot"], df["end_spot"]]).nunique() if not df.empty else 0
    )
    if df.empty or valid_spot_count < 2:
        st.warning(
            "筛选后数据过少（有效景点不足 2 个），无法绘制游客流动网络图。"
            "请放宽城市、季节或同行类型筛选条件。"
        )
    else:
        network_fig = build_flow_network_figure(df, top_n=DEFAULT_NETWORK_NODES)
        if network_fig is None:
            st.warning(
                "筛选后没有可用的景点间流动关系，无法绘制网络图。"
                "请尝试增加城市范围或切换季节 / 同行类型。"
            )
        else:
            st.plotly_chart(network_fig, width="stretch")
            st.caption(
                f"参与绘图的流动记录：{len(df):,} 条；"
                "节点大小与颜色深浅表示景点热度，悬浮连线中点可查看方向与权重。"
            )

# ========================= Tab3：景点热度排名 ==========================
with tab_heat:
    st.subheader("景点热度排名")
    st.caption("热度 = 该景点作为起点的流出流量 + 作为终点的流入流量。")

    if heat_df.empty:
        st.warning("当前筛选条件下没有可统计的景点热度数据，请调整筛选条件。")
    else:
        heat_fig = build_heat_bar_figure(heat_df, top_n=DEFAULT_TOP_N)
        if heat_fig is not None:
            st.plotly_chart(heat_fig, width="stretch")

        st.markdown("#### 热度排名表")
        st.caption(f"共 {len(heat_df):,} 个景点，最多展示前 200 条。")
        st.dataframe(
            heat_table(heat_df),
            width="stretch",
            hide_index=True,
            height=420,
            column_config={
                "排名": st.column_config.NumberColumn(width="small"),
                "总热度": st.column_config.NumberColumn(format="%d"),
                "流入流量": st.column_config.NumberColumn(format="%d"),
                "流出流量": st.column_config.NumberColumn(format="%d"),
            },
        )

# ======================== Tab4：节点中心性分析 =========================
with tab_centrality:
    st.subheader("节点中心性分析")
    st.caption(
        "基于 networkx 构建有向图，度中心性 =（入度 + 出度）/（节点总数 - 1），"
        "数值越高说明该景点与其他景点的连接越广泛。"
    )

    if centrality_df.empty:
        st.warning("当前筛选条件下没有可计算中心性的节点，请调整筛选条件。")
    else:
        st.markdown("#### 中心性排名表")
        st.caption(f"共 {len(centrality_df):,} 个节点，最多展示前 200 条。")
        st.dataframe(
            centrality_table(centrality_df),
            width="stretch",
            hide_index=True,
            height=420,
            column_config={
                "排名": st.column_config.NumberColumn(width="small"),
                "度数（入度+出度）": st.column_config.NumberColumn(format="%d"),
                "度中心性": st.column_config.NumberColumn(format="%.4f"),
            },
        )

        centrality_fig = build_centrality_bar_figure(centrality_df, top_n=DEFAULT_TOP_N)
        if centrality_fig is not None:
            st.plotly_chart(centrality_fig, width="stretch")

# ---------------------------------------------------------------------------
# 页脚
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "数据来源：Zheng, Y., Wang, J., Zhang, Y. et al. "
    "A dataset of tourist mobility networks across China derived from online travel blogs. "
    "Sci Data 13, 443 (2026). 数据托管于 Figshare，CC BY 4.0 协议。"
)
