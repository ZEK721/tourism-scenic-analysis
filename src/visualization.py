"""
可视化模块
==========
使用 plotly 绘制：
1. 交互式游客流动网络图（悬浮节点 / 连线中点显示权重）；
2. 景点热度横向柱状图；
3. 节点度中心性横向柱状图。

所有图表统一配置中文字体与简洁白色风格，保证中文正常显示。
"""

import networkx as nx
import numpy as np
import plotly.graph_objects as go

try:  # 兼容包导入与脚本直接运行
    from src.analysis import compute_spot_heat
    from src.config import (
        CHINESE_FONT_FAMILY,
        COL_END_SPOT,
        COL_START_SPOT,
        COL_WEIGHT,
        DEFAULT_NETWORK_NODES,
        DEFAULT_TOP_N,
        NETWORK_LAYOUT_SEED,
    )
except ImportError:  # pragma: no cover
    from analysis import compute_spot_heat  # type: ignore
    from config import (  # type: ignore
        CHINESE_FONT_FAMILY,
        COL_END_SPOT,
        COL_START_SPOT,
        COL_WEIGHT,
        DEFAULT_NETWORK_NODES,
        DEFAULT_TOP_N,
        NETWORK_LAYOUT_SEED,
    )


def _apply_base_layout(fig: go.Figure, title: str, height: int) -> go.Figure:
    """统一图表风格：中文字体、白色背景、简洁边距。"""
    fig.update_layout(
        title=dict(text=title, x=0.01, font=dict(size=16)),
        template="plotly_white",
        font=dict(family=CHINESE_FONT_FAMILY, size=12, color="#333333"),
        hoverlabel=dict(font=dict(family=CHINESE_FONT_FAMILY, size=12)),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=10, r=30, t=60, b=40),
        height=height,
    )
    return fig


def build_flow_network_figure(
    df,
    top_n: int = DEFAULT_NETWORK_NODES,
    seed: int = NETWORK_LAYOUT_SEED,
) -> go.Figure | None:
    """
    绘制交互式游客流动网络图。

    参数：
        df:     筛选后的流动数据（需包含 start_spot / end_spot / weight / city）。
        top_n:  按景点热度取前 N 个节点，避免节点过多导致图面拥挤、浏览器卡顿。
        seed:   布局随机种子，保证每次刷新图形位置稳定。

    返回：
        plotly Figure；若数据不足（少于 2 个有效节点或没有连线）则返回 None，
        由上层页面给出友好提示。
    """
    if df is None or len(df) == 0:
        return None

    # 计算景点热度，用于挑选核心节点、决定节点大小与颜色
    heat = compute_spot_heat(df)
    if heat.empty:
        return None

    # 同名景点可能分布在多个城市，网络图中按景点名合并显示
    spot_heat = (
        heat.groupby("spot", as_index=False)
        .agg(
            total_weight=("total_weight", "sum"),
            out_weight=("out_weight", "sum"),
            in_weight=("in_weight", "sum"),
            city=(("city", lambda values: "、".join(sorted(set(values))))),
        )
    )

    top_spots = spot_heat.nlargest(top_n, "total_weight")
    selected_spots = set(top_spots["spot"])
    if len(selected_spots) < 2:
        return None

    # 仅保留两端都在核心节点集合内的边，并按 起点-终点 聚合权重
    edges = df[
        df[COL_START_SPOT].isin(selected_spots) & df[COL_END_SPOT].isin(selected_spots)
    ]
    edges = (
        edges.groupby([COL_START_SPOT, COL_END_SPOT], as_index=False)[COL_WEIGHT]
        .sum()
    )
    if edges.empty:
        return None

    # 构建有向图
    graph = nx.DiGraph()
    for start_spot, end_spot, weight in edges.itertuples(index=False):
        if start_spot == end_spot:
            continue
        graph.add_edge(start_spot, end_spot, weight=float(weight))

    if graph.number_of_nodes() < 2 or graph.number_of_edges() == 0:
        return None

    # spring 布局：按权重让强连接节点更靠近
    node_count = graph.number_of_nodes()
    k = 1.8 / np.sqrt(node_count) if node_count > 1 else 1.0
    positions = nx.spring_layout(graph, seed=seed, k=k, iterations=100, weight="weight")

    nodes = list(graph.nodes())
    coordinates = np.array([positions[node] for node in nodes], dtype=float)

    # 归一化到大致 [-1, 1] 范围；极端情况（所有点重合）改用圆环布局
    coordinates -= coordinates.mean(axis=0)
    span = float(np.ptp(coordinates, axis=0).max()) if len(coordinates) > 1 else 0.0
    if span <= 1e-9:
        angles = np.linspace(0, 2 * np.pi, len(nodes), endpoint=False)
        coordinates = np.column_stack([np.cos(angles), np.sin(angles)])
    else:
        coordinates = coordinates / span * 2

    position_map = {node: coordinates[index] for index, node in enumerate(nodes)}
    spot_info = top_spots.set_index("spot")

    # --------------------------- 绘制边 ---------------------------
    line_x: list[float | None] = []
    line_y: list[float | None] = []
    mid_x: list[float] = []
    mid_y: list[float] = []
    edge_text: list[str] = []

    for start_spot, end_spot, data in graph.edges(data=True):
        x0, y0 = position_map[start_spot]
        x1, y1 = position_map[end_spot]
        line_x.extend([x0, x1, None])
        line_y.extend([y0, y1, None])
        # 连线中点放置小圆点，便于鼠标悬浮查看流向与权重
        mid_x.append((x0 + x1) / 2)
        mid_y.append((y0 + y1) / 2)
        edge_text.append(
            f"{start_spot} → {end_spot}<br>流动权重：{int(data.get('weight', 0)):,}"
        )

    fig = go.Figure()

    # 连线本体（不参与悬浮，避免与中点提示重复）
    fig.add_trace(
        go.Scatter(
            x=line_x,
            y=line_y,
            mode="lines",
            line=dict(color="rgba(120, 130, 160, 0.45)", width=1.2),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # 连线中点：悬浮显示「起点 → 终点」和权重
    fig.add_trace(
        go.Scatter(
            x=mid_x,
            y=mid_y,
            mode="markers",
            marker=dict(size=6, color="rgba(90, 100, 130, 0.55)"),
            text=edge_text,
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )
    )

    # --------------------------- 绘制节点 ---------------------------
    node_heat = np.array([float(spot_info.loc[node, "total_weight"]) for node in nodes])
    max_heat = float(node_heat.max()) if node_heat.size else 1.0
    if max_heat <= 0:
        max_heat = 1.0
    node_sizes = 14 + 34 * np.sqrt(node_heat / max_heat)

    customdata = [
        [
            str(spot_info.loc[node, "city"]),
            int(spot_info.loc[node, "out_weight"]),
            int(spot_info.loc[node, "in_weight"]),
            int(spot_info.loc[node, "total_weight"]),
        ]
        for node in nodes
    ]

    fig.add_trace(
        go.Scatter(
            x=coordinates[:, 0],
            y=coordinates[:, 1],
            mode="markers+text",
            text=nodes,
            textposition="top center",
            textfont=dict(size=9, color="#444444"),
            marker=dict(
                size=node_sizes,
                color=node_heat,
                colorscale="YlOrRd",
                showscale=True,
                colorbar=dict(title="热度", thickness=12, len=0.65, x=1.0),
                line=dict(color="white", width=1.5),
            ),
            customdata=customdata,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "城市：%{customdata[0]}<br>"
                "总热度：%{customdata[3]:,}<br>"
                "流出流量：%{customdata[1]:,}<br>"
                "流入流量：%{customdata[2]:,}"
                "<extra></extra>"
            ),
            showlegend=False,
        )
    )

    _apply_base_layout(fig, f"游客流动网络图（热度前 {len(nodes)} 个景点）", 680)
    fig.update_layout(
        hovermode="closest",
        dragmode="pan",
        showlegend=False,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    fig.update_xaxes(visible=False, fixedrange=False)
    fig.update_yaxes(visible=False, fixedrange=False, scaleanchor="x", scaleratio=1)
    return fig


def build_heat_bar_figure(heat_df, top_n: int = DEFAULT_TOP_N) -> go.Figure | None:
    """绘制景点热度排名横向柱状图（展示热度前 top_n 的景点）。"""
    if heat_df is None or heat_df.empty:
        return None

    data = heat_df.nlargest(top_n, "total_weight").sort_values("total_weight")
    customdata = data[["city", "out_weight", "in_weight"]].to_numpy()

    fig = go.Figure(
        go.Bar(
            x=data["total_weight"],
            y=data["spot"],
            orientation="h",
            marker=dict(
                color=data["total_weight"],
                colorscale="YlOrRd",
                showscale=False,
                line=dict(color="rgba(0,0,0,0.15)", width=0.5),
            ),
            text=[f"{value:,}" for value in data["total_weight"]],
            textposition="outside",
            cliponaxis=False,
            customdata=customdata,
            hovertemplate=(
                "景点：%{y}<br>"
                "城市：%{customdata[0]}<br>"
                "总热度：%{x:,}<br>"
                "流出流量：%{customdata[1]:,}<br>"
                "流入流量：%{customdata[2]:,}"
                "<extra></extra>"
            ),
        )
    )

    height = max(420, 26 * len(data) + 120)
    _apply_base_layout(fig, f"景点热度排名 TOP {len(data)}", height)
    fig.update_layout(
        bargap=0.3,
        margin=dict(l=10, r=70, t=60, b=40),
    )
    fig.update_xaxes(title_text="总热度（流入 + 流出流量）", gridcolor="#eeeeee")
    fig.update_yaxes(title_text="", automargin=True)
    return fig


def build_centrality_bar_figure(centrality_df, top_n: int = DEFAULT_TOP_N) -> go.Figure | None:
    """绘制节点度中心性排名横向柱状图（展示中心性前 top_n 的景点）。"""
    if centrality_df is None or centrality_df.empty:
        return None

    data = centrality_df.nlargest(top_n, "centrality").sort_values("centrality")
    customdata = data[["city", "degree"]].to_numpy()

    fig = go.Figure(
        go.Bar(
            x=data["centrality"],
            y=data["spot"],
            orientation="h",
            marker=dict(
                color=data["centrality"],
                colorscale="Blues",
                showscale=False,
                line=dict(color="rgba(0,0,0,0.15)", width=0.5),
            ),
            text=[f"{value:.4f}" for value in data["centrality"]],
            textposition="outside",
            cliponaxis=False,
            customdata=customdata,
            hovertemplate=(
                "景点：%{y}<br>"
                "城市：%{customdata[0]}<br>"
                "度中心性：%{x:.4f}<br>"
                "度数（入度+出度）：%{customdata[1]}"
                "<extra></extra>"
            ),
        )
    )

    height = max(420, 26 * len(data) + 120)
    _apply_base_layout(fig, f"节点度中心性排名 TOP {len(data)}", height)
    fig.update_layout(
        bargap=0.3,
        margin=dict(l=10, r=90, t=60, b=40),
    )
    fig.update_xaxes(title_text="度中心性", gridcolor="#eeeeee")
    fig.update_yaxes(title_text="", automargin=True)
    return fig
