# 数据集说明

本项目使用数据集：

> Zheng, Y., Wang, J., Zhang, Y. et al. A dataset of tourist mobility networks across China derived from online travel blogs. *Sci Data* 13, 443 (2026).

数据托管于 Figshare，采用 CC BY 4.0 协议。

## 目录约定

`data/raw_data/` 存放解压后的原版数据集，包含三个子文件夹：

```text
raw_data/
├── 01_Full Network/            # 完整游客流动网络（边表 + 节点表）
├── 02_By_Travel_Partners/      # 按同行类型分组的边表（独自 / 家庭 / 朋友）
└── 03_By_Departure_Season/     # 按出发季节分组的边表（春 / 夏 / 秋 / 冬）
```

> 说明：数据集压缩包中的文件夹也可能命名为 `01_Full_Network`（下划线），
> 预处理脚本会按 `01 / 02 / 03` 编号自动识别，两种命名都可正常运行。

## 原始字段

- 节点表（Nodes）：`ID`、`Name_ZH`、`Name_EN`、`City_ZH`、`City_EN`、`Latitude_GCJ02`、`Longitude_GCJ02`
- 边表（Edges）：`Source`、`Target`、`Weight`

## 生成分析表

运行预处理脚本后，会自动生成用于分析的 `data/tourism_flow.csv`：

```bash
python src/build_dataset.py
```

该表仅保留**起点与终点属于同一城市**的同城景点流动记录，字段为：
`start_spot`、`end_spot`、`weight`、`city`、`season`、`partner_type`。
