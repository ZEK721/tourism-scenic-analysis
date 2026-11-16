"""
分析模块
========
1. 景点热度：某景点作为起点（流出）与终点（流入）的流量之和；
2. 节点中心性：基于 networkx 构建有向图，计算每个节点的度中心性。
所有函数对空数据均返回带标准列的空表，避免上游缺数据时崩溃。
"""

import networkx as nx
import pandas as pd

try:  # 兼容包导入与脚本直接运行
    from src.config import (
        COL_CITY,
        COL_END_SPOT,
        COL_START_SPOT,
        COL_WEIGHT,
    )
except ImportError:  # pragma: no cover
    from config import (  # type: ignore
        COL_CITY,
        COL_END_SPOT,
        COL_START_SPOT,
        COL_WEIGHT,
    )

# 分析结果列定义
HEAT_COLUMNS = ["rank", "spot", "city", "out_weight", "in_weight", "total_weight"]
CENTRALITY_COLUMNS = ["rank", "spot", "city", "degree", "centrality"]


def compute_spot_heat(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算景点热度排名。

    热度 = 该景点作为起点的流出流量 + 作为终点的流入流量。
    返回列：
        rank          排名（按总热度降序，从 1 开始）
        spot          景点名称
        city          所属城市
        out_weight    流出流量（作为起点）
        in_weight     流入流量（作为终点）
        total_weight  总热度
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=HEAT_COLUMNS)

    # 作为起点：按景点 + 城市统计流出流量
    out_df = (
        df.groupby([COL_START_SPOT, COL_CITY], as_index=False)[COL_WEIGHT]
        .sum()
        .rename(columns={COL_START_SPOT: "spot", COL_CITY: "city", COL_WEIGHT: "out_weight"})
    )
    # 作为终点：按景点 + 城市统计流入流量
    in_df = (
        df.groupby([COL_END_SPOT, COL_CITY], as_index=False)[COL_WEIGHT]
        .sum()
        .rename(columns={COL_END_SPOT: "spot", COL_CITY: "city", COL_WEIGHT: "in_weight"})
    )

    heat = out_df.merge(in_df, on=["spot", "city"], how="outer")
    heat[["out_weight", "in_weight"]] = (
        heat[["out_weight", "in_weight"]].fillna(0).astype(int)
    )
    heat["total_weight"] = heat["out_weight"] + heat["in_weight"]

    # 按总热度降序排名；同一景点同名不同城时分别统计
    heat = (
        heat.sort_values(["total_weight", "spot"], ascending=[False, True])
        .reset_index(drop=True)
    )
    heat.insert(0, "rank", range(1, len(heat) + 1))
    return heat[HEAT_COLUMNS]


def compute_degree_centrality(df: pd.DataFrame) -> pd.DataFrame:
    """
    构建有向图并计算每个节点的度中心性。

    度中心性采用 networkx.degree_centrality：
        对 DiGraph，度中心性 = (入度 + 出度) / (N - 1)
    返回列：
        rank        排名（按中心性降序）
        spot        景点名称
        city        所属城市
        degree      度数（入度 + 出度）
        centrality  度中心性（0 ~ 1）
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=CENTRALITY_COLUMNS)

    # 构建有向图：边权重保留在 weight 属性中，便于后续扩展
    graph = nx.DiGraph()
    city_lookup: dict[str, str] = {}

    for row in df[[COL_START_SPOT, COL_END_SPOT, COL_CITY, COL_WEIGHT]].itertuples(index=False):
        start_spot, end_spot, city, weight = row
        if str(start_spot) == str(end_spot):
            # 自环不影响度中心性，直接跳过，避免图中出现无意义自环
            city_lookup.setdefault(str(start_spot), str(city))
            continue
        graph.add_edge(start_spot, end_spot, weight=float(weight))
        city_lookup.setdefault(str(start_spot), str(city))
        city_lookup.setdefault(str(end_spot), str(city))

    if graph.number_of_nodes() == 0:
        return pd.DataFrame(columns=CENTRALITY_COLUMNS)

    centrality_map = nx.degree_centrality(graph)
    degree_map = dict(graph.degree())

    result = pd.DataFrame({
        "spot": list(centrality_map.keys()),
        "degree": [int(degree_map[spot]) for spot in centrality_map],
        "centrality": [float(value) for value in centrality_map.values()],
    })
    result["city"] = result["spot"].map(lambda spot: city_lookup.get(spot, ""))

    result = (
        result.sort_values(["centrality", "degree", "spot"], ascending=[False, False, True])
        .reset_index(drop=True)
    )
    result.insert(0, "rank", range(1, len(result) + 1))
    return result[CENTRALITY_COLUMNS]
