"""
一键预处理脚本
================
功能：
1. 读取 data/raw_data 下的节点表（node）作为 ID -> 景点名称 / 城市 的映射表；
2. 读取三类边表（完整网络 / 按同行类型 / 按出发季节）；
3. 只保留“起点与终点属于同一城市”的同城流动记录；
4. 统一字段并纵向合并，清洗空值、合并重复边；
5. 输出 data/tourism_flow.csv（utf-8-sig 编码，方便 Excel 直接打开）。

使用方式（在项目根目录执行）：
    python src/build_dataset.py
"""

import sys
from pathlib import Path

import pandas as pd

# ===========================================================================
# 路径配置：如原始数据换了位置，只需要修改这里的 RAW_DATA_PATH 即可
# ===========================================================================
RAW_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "raw_data"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "tourism_flow.csv"

# 最终输出字段（顺序固定）
FLOW_COLUMNS = ["start_spot", "end_spot", "weight", "city", "season", "partner_type"]

# 边表列名兼容映射：不同版本数据集的列名可能不同，这里做统一适配
# 例如原版数据为 Source / Target / Weight，需求文档中为 origin_id / dest_id / count
EDGE_ALIASES = {
    "origin_id": ["origin_id", "source", "from_id", "from", "start_id", "o"],
    "dest_id": ["dest_id", "target", "to_id", "to", "end_id", "d"],
    "count": ["count", "weight", "value", "flow", "trips"],
}

# 节点表列名兼容映射
NODE_ALIASES = {
    "spot_id": ["spot_id", "id", "node_id", "poi_id"],
    "spot_name": ["spot_name", "name_zh", "name", "label"],
    "city": ["city", "city_zh", "city_name"],
}

# 分组目录前缀与关键词（兼容 "01_Full Network" 与 "01_Full_Network" 两种命名）
GROUP_CONFIG = {
    "full": {"prefix": "01", "keywords": ["full"], "label": "完整网络"},
    "partner": {"prefix": "02", "keywords": ["partner"], "label": "按同行类型"},
    "season": {"prefix": "03", "keywords": ["season"], "label": "按出发季节"},
}

# 文件名关键词 -> 分组标签
PARTNER_KEYWORDS = [
    ("solo", "alone"),
    ("alone", "alone"),
    ("family", "family"),
    ("friend", "friend"),
]
SEASON_KEYWORDS = [
    ("spring", "spring"),
    ("summer", "summer"),
    ("autumn", "autumn"),
    ("fall", "autumn"),
    ("winter", "winter"),
]
# 文件名无法识别时，按排序回退到固定顺序
PARTNER_FALLBACK = ["alone", "family", "friend"]
SEASON_FALLBACK = ["spring", "summer", "autumn", "winter"]


# ---------------------------------------------------------------------------
# 通用工具函数
# ---------------------------------------------------------------------------
def log(message: str) -> None:
    """统一日志输出，避免 Windows 控制台编码问题导致脚本中断。"""
    try:
        print(message)
    except UnicodeEncodeError:
        # 控制台编码不支持部分字符时降级输出，保证脚本不会因日志本身崩溃
        encoding = sys.stdout.encoding or "utf-8"
        print(message.encode(encoding, errors="replace").decode(encoding, errors="replace"))


def warn(message: str) -> None:
    """输出警告日志。"""
    log(f"[警告] {message}")


def read_csv_safely(path: Path) -> pd.DataFrame:
    """读取 CSV，优先 utf-8-sig，失败后回退 GBK，最后抛出明确异常。"""
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
        except Exception as exc:  # 文件损坏、格式错误等
            raise RuntimeError(f"读取文件失败：{path.name}，原因：{exc}") from exc
    raise RuntimeError(f"无法识别文件编码：{path.name}，请确认是否为标准 CSV 文件。")


def normalize_columns(df: pd.DataFrame, aliases: dict) -> pd.DataFrame:
    """把不同命名的列统一成标准列名，找不到必需列时抛出异常。"""
    # 去掉列名首尾空格并转小写，便于匹配
    renamed = {col: str(col).strip().lower().replace(" ", "_") for col in df.columns}
    df = df.rename(columns=renamed)

    mapping = {}
    for standard_name, candidates in aliases.items():
        for candidate in candidates:
            if candidate in df.columns:
                mapping[candidate] = standard_name
                break
        else:
            raise KeyError(f"缺少必需列：{standard_name}（候选列名：{candidates}）")

    return df[list(mapping.keys())].rename(columns=mapping)


def normalize_id_series(series: pd.Series) -> pd.Series:
    """把 ID 列统一成字符串，避免 int / float / str 混用导致映射失败。"""
    def convert(value) -> str:
        if pd.isna(value):
            return ""
        # 数值型 ID 被读成浮点数时去掉多余的 ".0"
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        text = str(value).strip()
        if text.endswith(".0") and text[:-2].isdigit():
            return text[:-2]
        return text

    return series.map(convert)


def find_group_dir(group_key: str) -> Path | None:
    """根据编号前缀 / 关键词定位三个原始数据子文件夹。"""
    if not RAW_DATA_PATH.exists():
        return None

    config = GROUP_CONFIG[group_key]
    sub_dirs = sorted([p for p in RAW_DATA_PATH.iterdir() if p.is_dir()])
    if not sub_dirs:
        return None

    # 优先按编号前缀匹配（01 / 02 / 03）
    for folder in sub_dirs:
        normalized = folder.name.strip().lower().replace(" ", "_")
        if normalized.startswith(config["prefix"]):
            return folder
    # 其次按关键词匹配
    for folder in sub_dirs:
        normalized = folder.name.strip().lower()
        if any(keyword in normalized for keyword in config["keywords"]):
            return folder
    return None


def list_csv_files(folder: Path, keyword: str) -> list[Path]:
    """列出文件夹下文件名包含指定关键词的 CSV（不递归）。"""
    return sorted(
        p for p in folder.glob("*.csv")
        if keyword in p.name.lower() and p.is_file()
    )


# ---------------------------------------------------------------------------
# 第一步：构建节点映射表
# ---------------------------------------------------------------------------
def build_node_map() -> pd.DataFrame:
    """
    读取所有 node 文件并合并为映射表。
    以 01 完整网络的节点表为主，其他分组的节点表用于补充缺失 ID。
    返回列：spot_id / spot_name / city
    """
    frames = []
    # 先读取 01 分组，保证主表优先
    group_dirs = [find_group_dir("full"), find_group_dir("partner"), find_group_dir("season")]
    node_files: list[Path] = []
    for folder in group_dirs:
        if folder is None:
            continue
        node_files.extend(list_csv_files(folder, "node"))

    if not node_files:
        raise FileNotFoundError("未找到任何 node 节点表文件，请检查 data/raw_data 目录。")

    for path in node_files:
        try:
            df = read_csv_safely(path)
            df = normalize_columns(df, NODE_ALIASES)
            df = df.dropna(subset=["spot_id", "spot_name", "city"])
            frames.append(df)
        except Exception as exc:
            warn(f"节点表 {path.name} 读取失败，已跳过。原因：{exc}")

    if not frames:
        raise RuntimeError("所有节点表都读取失败，无法建立景点映射。")

    node_map = pd.concat(frames, ignore_index=True)
    # ID 统一转为字符串，避免 int / str 类型不一致导致映射失败
    node_map["spot_id"] = normalize_id_series(node_map["spot_id"])
    node_map["spot_name"] = node_map["spot_name"].astype(str).str.strip()
    node_map["city"] = node_map["city"].astype(str).str.strip()
    node_map = node_map[(node_map["spot_id"] != "") & (node_map["spot_name"] != "")]
    node_map = node_map.drop_duplicates(subset=["spot_id"], keep="first")

    log(f"[完成] 节点映射表构建完成：{len(node_map)} 个景点，"
        f"{node_map['city'].nunique()} 个城市（来源 {len(node_files)} 个文件）")
    return node_map


# ---------------------------------------------------------------------------
# 第二步：读取并标注各组边表
# ---------------------------------------------------------------------------
def read_edge_group(group_key: str, season: str = "all", partner: str = "all") -> pd.DataFrame:
    """
    读取某一分组的全部边表，并打上 season / partner_type 标签。
    返回标准化后的边表：origin_id / dest_id / count / season / partner_type
    """
    folder = find_group_dir(group_key)
    if folder is None:
        warn(f"未找到「{GROUP_CONFIG[group_key]['label']}」数据文件夹，已跳过该分组。")
        return pd.DataFrame()

    edge_files = list_csv_files(folder, "edge")
    if not edge_files:
        warn(f"「{GROUP_CONFIG[group_key]['label']}」文件夹中没有 edge CSV 文件，已跳过。")
        return pd.DataFrame()

    frames = []
    for index, path in enumerate(edge_files):
        file_name = path.name.lower()
        file_season, file_partner = season, partner

        # 根据文件名识别具体分组标签
        if group_key == "partner":
            for keyword, label in PARTNER_KEYWORDS:
                if keyword in file_name:
                    file_partner = label
                    break
            else:
                # 文件名中无关键词时按排序回退，并给出提示
                fallback = PARTNER_FALLBACK[index] if index < len(PARTNER_FALLBACK) else "all"
                file_partner = fallback
                warn(f"无法从文件名识别同行类型：{path.name}，按顺序标记为 {fallback}")
        elif group_key == "season":
            for keyword, label in SEASON_KEYWORDS:
                if keyword in file_name:
                    file_season = label
                    break
            else:
                fallback = SEASON_FALLBACK[index] if index < len(SEASON_FALLBACK) else "all"
                file_season = fallback
                warn(f"无法从文件名识别季节：{path.name}，按顺序标记为 {fallback}")

        try:
            df = read_csv_safely(path)
            df = normalize_columns(df, EDGE_ALIASES)
            df["count"] = pd.to_numeric(df["count"], errors="coerce")
            df = df.dropna(subset=["origin_id", "dest_id", "count"])
            df = df[df["count"] > 0]
            df["origin_id"] = normalize_id_series(df["origin_id"])
            df["dest_id"] = normalize_id_series(df["dest_id"])
            df = df[(df["origin_id"] != "") & (df["dest_id"] != "")]
            df["season"] = file_season
            df["partner_type"] = file_partner
            frames.append(df)
            log(f"   - 读取 {path.name}：{len(df)} 条边"
                f"（season={file_season}, partner_type={file_partner}）")
        except Exception as exc:
            warn(f"边表 {path.name} 读取失败，已跳过。原因：{exc}")

    if not frames:
        warn(f"「{GROUP_CONFIG[group_key]['label']}」分组没有可用数据。")
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# 第三步：映射景点名称、过滤同城、清洗并输出
# ---------------------------------------------------------------------------
def build_flow_table(node_map: pd.DataFrame) -> pd.DataFrame:
    """将三组边表合并、映射名称、过滤同城流动并清洗去重。"""
    all_edges = []

    # 01 完整网络：season / partner_type 均填充 all
    full_edges = read_edge_group("full", season="all", partner="all")
    if not full_edges.empty:
        all_edges.append(full_edges)

    # 02 按同行类型：season 填充 all
    partner_edges = read_edge_group("partner", season="all")
    if not partner_edges.empty:
        all_edges.append(partner_edges)

    # 03 按出发季节：partner_type 填充 all
    season_edges = read_edge_group("season", partner="all")
    if not season_edges.empty:
        all_edges.append(season_edges)

    if not all_edges:
        raise RuntimeError("三组边表均未读取到数据，请检查 data/raw_data 中的文件是否完整。")

    edges = pd.concat(all_edges, ignore_index=True)
    log(f"\n[合并] 三组边表合并完成，共 {len(edges)} 条原始边记录")

    # 通过映射表把 origin_id / dest_id 转成景点名称和城市
    # 起点、终点分别映射一次，便于判断是否同城
    origin_map = node_map.rename(columns={
        "spot_id": "origin_id", "spot_name": "start_spot", "city": "origin_city",
    })
    dest_map = node_map.rename(columns={
        "spot_id": "dest_id", "spot_name": "end_spot", "city": "dest_city",
    })

    merged = edges.merge(origin_map, on="origin_id", how="left")
    merged = merged.merge(dest_map, on="dest_id", how="left")

    missing_origin = merged["start_spot"].isna().sum()
    missing_dest = merged["end_spot"].isna().sum()
    if missing_origin or missing_dest:
        warn(f"有 {missing_origin} 条边的起点、{missing_dest} 条边的终点未匹配到景点名称，已过滤。")

    # 只保留起点与终点属于同一城市的流动记录
    before = len(merged)
    merged = merged.dropna(subset=["start_spot", "end_spot", "origin_city", "dest_city"])
    same_city = merged["origin_city"] == merged["dest_city"]
    log(f"[同城] 同城过滤：保留 {int(same_city.sum())} / {before} 条同城流动记录，"
        f"过滤跨城记录 {before - int(same_city.sum())} 条")
    merged = merged[same_city].copy()

    # 统一字段
    merged = merged.rename(columns={"count": "weight", "origin_city": "city"})
    merged = merged[FLOW_COLUMNS]

    # 清洗：去空值、去首尾空格、去掉空字符串、权重转整数
    merged = merged.dropna(subset=FLOW_COLUMNS)
    for column in ["start_spot", "end_spot", "city", "season", "partner_type"]:
        merged[column] = merged[column].astype(str).str.strip()
    merged = merged[
        (merged["start_spot"] != "") & (merged["end_spot"] != "")
        & (merged["city"] != "") & (merged["weight"] > 0)
    ]
    merged["weight"] = merged["weight"].astype(float).round().astype(int)

    # 合并重复边：同一 起点-终点-城市-季节-同行类型 只保留一条，权重累加
    before_dedup = len(merged)
    group_keys = ["start_spot", "end_spot", "city", "season", "partner_type"]
    merged = (
        merged.groupby(group_keys, as_index=False)["weight"].sum()
    )[FLOW_COLUMNS]
    log(f"[清洗] 去重合并：{before_dedup} 条 -> {len(merged)} 条（重复边权重已累加）")

    if merged.empty:
        raise RuntimeError("清洗后数据为空，请检查原始数据是否正常。")

    return merged.sort_values(
        ["city", "season", "partner_type", "weight"], ascending=[True, True, True, False]
    ).reset_index(drop=True)


def main() -> int:
    """脚本入口：返回 0 表示成功，非 0 表示失败。"""
    log("=" * 60)
    log("开始预处理北大游客流动网络数据集")
    log(f"原始数据目录：{RAW_DATA_PATH}")
    log(f"输出文件路径：{OUTPUT_PATH}")
    log("=" * 60)

    # 1. 检查原始数据目录
    if not RAW_DATA_PATH.exists():
        log(f"[错误] 未找到原始数据目录：{RAW_DATA_PATH}")
        log("   请将解压后的数据集放入 data/raw_data/ 后重新运行。")
        return 1

    try:
        # 2. 构建节点映射
        node_map = build_node_map()
        # 3. 构建分析表
        flow = build_flow_table(node_map)
    except Exception as exc:
        log(f"[错误] 预处理失败：{exc}")
        return 1

    # 4. 输出 CSV（utf-8-sig 保证 Excel 打开中文不乱码）
    try:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        flow.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    except Exception as exc:
        log(f"[错误] 写出文件失败：{OUTPUT_PATH}，原因：{exc}")
        return 1

    # 5. 打印处理结果概览
    log("\n" + "=" * 60)
    log("[完成] 预处理完成！")
    log(f"输出文件：{OUTPUT_PATH}")
    log(f"总记录数：{len(flow)}")
    log(f"涉及景点数：{pd.concat([flow['start_spot'], flow['end_spot']]).nunique()}")
    log(f"涉及城市数：{flow['city'].nunique()}")
    log(f"总流动权重：{int(flow['weight'].sum())}")
    log("\n分组记录数：")
    log(f"   - season=all & partner_type=all（完整网络）：{len(flow[(flow['season'] == 'all') & (flow['partner_type'] == 'all')])}")
    for season in ["spring", "summer", "autumn", "winter"]:
        log(f"   - season={season}：{len(flow[flow['season'] == season])}")
    for partner in ["alone", "family", "friend"]:
        log(f"   - partner_type={partner}：{len(flow[flow['partner_type'] == partner])}")
    log("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
