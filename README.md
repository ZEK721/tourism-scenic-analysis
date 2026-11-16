# tourism-mismatch-detector

基于北大游客流动网络数据集（*A dataset of tourist mobility networks across China derived from online travel blogs*）构建的 **Streamlit 可视化分析平台**，聚焦同城景点之间的游客转移关系：

- 🕸️ 交互式游客流动网络图（悬浮查看流向与权重）
- 🔥 景点热度排名（流入 + 流出流量）
- 📐 节点中心性分析（有向图度中心性）
- 🎛️ 支持按城市、季节、同行类型多条件筛选

---

## 一、项目结构

```text
tourism-mismatch-detector/
├── data/
│   ├── raw_data/            # 解压后的原版数据集（01 / 02 / 03 三个文件夹）
│   ├── tourism_flow.csv     # 预处理脚本自动生成的分析表
│   └── readme-data.md       # 数据集来源与字段说明
├── src/
│   ├── __init__.py
│   ├── build_dataset.py     # 一键预处理：合并原始数据 -> tourism_flow.csv
│   ├── data_loader.py       # 数据读取与筛选
│   ├── analysis.py          # 热度统计、度中心性计算
│   ├── visualization.py     # 网络图与柱状图绘制
│   └── config.py            # 路径、字段、可选值、绘图参数
├── app.py                   # Streamlit 主程序
├── requirements.txt
└── README.md
```

---

## 二、环境安装

要求：Python 3.10 及以上版本。

```bash
# 1. 进入项目目录
cd tourism-mismatch-detector

# 2.（可选）创建并激活虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
```

依赖包：`streamlit`、`pandas`、`networkx`、`plotly`、`numpy`。

---

## 三、数据准备

1. 下载并解压数据集（Figshare，CC BY 4.0）。
2. 将解压后的三个文件夹放入 `data/raw_data/`：

   ```text
   data/raw_data/
   ├── 01_Full Network/
   ├── 02_By_Travel_Partners/
   └── 03_By_Departure_Season/
   ```

   > 文件夹也可命名为 `01_Full_Network`，脚本按 `01 / 02 / 03` 编号自动识别。

3. 运行预处理脚本，生成 `data/tourism_flow.csv`：

   ```bash
   python src/build_dataset.py
   ```

   脚本会打印节点表、各组边表读取情况、同城过滤与去重合并结果。
   输出字段：`start_spot`、`end_spot`、`weight`、`city`、`season`、`partner_type`。

   原始数据字段与需求文档的对应关系（脚本已自动兼容）：

   | 需求文档字段 | 原始数据列 |
   | --- | --- |
   | `origin_id` | `Source` |
   | `dest_id` | `Target` |
   | `count` | `Weight` |
   | `spot_id` | `ID` |
   | `spot_name` | `Name_ZH` |
   | `city` | `City_ZH` |

---

## 四、启动看板

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`，若未自动打开请手动访问。

> 建议在项目根目录执行上述命令，确保相对路径 `data/tourism_flow.csv` 能正确找到。

---

## 五、页面功能

| 区域 | 内容 |
| --- | --- |
| 侧边栏 | 城市多选（不选 = 全部）、季节下拉、同行类型下拉 |
| Tab1 数据概览 | 总流动记录数、涉及景点数量、数据预览表格 |
| Tab2 游客流动网络图 | 交互式网络图，节点大小/颜色代表热度，悬浮节点或连线中点查看城市、流量、权重 |
| Tab3 景点热度排名 | 热度 TOP 20 柱状图 + 完整排名表（前 200 条） |
| Tab4 节点中心性分析 | 度中心性排名表 + TOP 20 柱状图 |

筛选后数据不足时，网络图会给出提示而不是报错。

### 筛选逻辑说明

原始数据分为三类：完整网络、按同行类型分组、按季节分组。

- 两个下拉框都选 `all`：使用完整网络数据，**不会**与子分组重复计数；
- 只选季节（如 `spring`）：使用对应季节数据；
- 只选同行类型（如 `family`）：使用对应同行类型数据；
- 同时选择具体季节和具体同行类型：原始数据不存在交叉分组，此时**优先按季节筛选**，页面会给出提示。

---

## 六、常见问题

**Q：提示找不到 `data/tourism_flow.csv`？**
先确认 `data/raw_data/` 中已放入原始数据，再运行 `python src/build_dataset.py`。

**Q：运行预处理脚本时提示缺少列？**
脚本兼容 `Source/Target/Weight` 与 `origin_id/dest_id/count` 两种列名；若仍报错，请确认
三个子文件夹内的 CSV 文件未被改动或重命名。

**Q：图表中文显示为方框？**
图表使用 Plotly 渲染，字体优先调用系统 `Microsoft YaHei / SimHei / PingFang SC`。
Linux 服务器若无中文字体，可安装 `fonts-wqy-zenhei` 或 `fonts-noto-cjk` 后刷新页面。

**Q：城市很多，网络图很乱？**
网络图默认仅展示热度前 40 个景点（可在 `src/config.py` 的 `DEFAULT_NETWORK_NODES` 中调整），
建议在侧边栏选择具体城市查看。

---

## 七、数据引用

Zheng, Y., Wang, J., Zhang, Y. et al. A dataset of tourist mobility networks across China derived from online travel blogs. *Sci Data* 13, 443 (2026).

数据托管于 Figshare，CC BY 4.0 协议。详细说明见 `data/readme-data.md`。
