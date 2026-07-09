# 关联规则挖掘算法课程网站

第 3 组课程网站，包含 Apriori、FP-Growth、Eclat、AIS、H-Mine 五种关联规则挖掘算法的介绍、数据湖资产展示、在线运行、五算法对比和结果分析。

## 主要功能

- 数据湖资产展示与预览。
- Apriori、FP-Growth、Eclat、AIS、H-Mine 五种算法在线运行。
- 可视化教学页展示五种算法关键步骤。
- 结果页展示频繁项集、关联规则、support、confidence、lift。
- 算法对比仪表盘：同一数据湖资产和参数下比较五种算法。
- 参数网格扫描：同一算法下扫描多组 `support × confidence`，观察规则数量、耗时和 lift 变化。
- 后端实验档案：每次运行自动保存到服务器 `data/results/`，可从历史中心重新打开。
- 商品推荐模拟器：根据已选购物篮商品推荐可能一起购买的商品。
- 实验历史中心：保存、导出、复制和重新运行浏览器本地实验记录。
- 小组成员页：通过 `config/team.toml` 配置成员、分工和项目进度。

## 数据湖

项目内置多个真实购物篮/交易数据湖资产，统一转换为 `transaction_id,items` 格式：

- UCI Online Retail - France
- UCI Online Retail - Germany
- UCI Online Retail - EIRE
- UCI Online Retail - United Kingdom
- Groceries Dataset
- Bread Basket Bakery Dataset
- Market Basket Grocery Dataset

内置 CSV 已经放在本地仓库中：

| 文件 | 交易数 | 说明 |
| --- | ---: | --- |
| `data/datasets/uci_online_retail_france.csv` | 312 | UCI Online Retail France |
| `data/datasets/uci_online_retail_germany.csv` | 323 | UCI Online Retail Germany |
| `data/datasets/uci_online_retail_eire.csv` | 234 | UCI Online Retail EIRE |
| `data/datasets/uci_online_retail_united_kingdom.csv` | 500 | UCI Online Retail United Kingdom |
| `data/datasets/groceries.csv` | 7,676 | Groceries Dataset |
| `data/datasets/bread_basket.csv` | 5,517 | Bread Basket Bakery Dataset |
| `data/datasets/market_basket_grocery.csv` | 5,747 | Market Basket Grocery Dataset |

`data/transactions.csv` 是兼容早期课程要求的默认数据文件，当前内容与 UCI France 数据湖一致，共 312 条交易。运行时 Flask 会优先读取 `data/datasets/` 下的对应 CSV，缺失时才回退到 `data/transactions.csv`。

主要来源：

- https://archive.ics.uci.edu/dataset/352/online+retail
- https://github.com/stedy/Machine-Learning-with-R-datasets/blob/master/groceries.csv
- https://github.com/prasertcbs/basic-dataset/blob/master/BreadBasket_DMS.csv
- https://github.com/HwaiTengTeoh/Market-Basket-Analysis/blob/master/Market_Basket_Data.csv

本项目本地已下载原始 `Online Retail.xlsx` 压缩包并转换出可运行 CSV。上传到 GitHub 时只需要提交可直接运行的转换后真实数据集，原始压缩包和 `data/raw/` 是本地缓存，不进入源码仓库：

- 从原始 541,909 行交易中筛选多个国家的正向订单。
- 过滤取消订单、非正数量、邮费、人工费用和折扣记录。
- 按发票号聚合为购物篮交易。
- 保留高频真实商品描述，形成适合课堂实验的多个购物篮子集。

运行页还支持选择新的数据湖资产：

- 选择内置数据湖资产。
- 上传 CSV 文件。
- 填写服务器本机 CSV 路径。
- 支持 `transaction_id,items` 购物篮格式。
- 支持 `InvoiceNo,Description,Quantity` 这类交易明细格式，系统会自动按交易号聚合。
- 勾选跨数据湖资产对比。
- 勾选参数网格扫描。
- 在结果页搜索、排序、过滤和导出规则 CSV。

运行产生的实验记录会保存到：

```text
data/results/
```

该目录是服务器运行数据，已在 `.gitignore` 中忽略，不会污染源码提交。

## 运行方式

```bash
pip install -r requirements.txt
python app.py
```

浏览器打开：

```text
http://127.0.0.1:5000
```

## 生成课程报告

仓库提供报告生成脚本，会自动启动本地 Flask 服务、运行实验、截图并生成 Word 兼容 `.doc` 报告：

```bash
uv run --with Flask --with playwright python scripts/generate_course_report.py
```

生成结果：

- `大作业_《数据挖掘技术课程设计》实验报告书.doc`
- `report_assets/experiment_summary.json`
- `report_assets/screenshots/`

脚本会覆盖当前报告，并删除旧的 `.original.bak` 备份文件，避免历史报告重复占用空间。`report_assets/` 是本轮报告的截图和摘要素材，需要重新生成报告时可以删除后再运行脚本。

## 小组成员配置

成员信息不写死在 HTML 中，统一放在：

```text
config/team.toml
```

修改 `members`、`modules`、`milestones` 后刷新 `/team` 页面即可看到变化。

## CSV 示例

购物篮格式：

```csv
transaction_id,items
1,"牛奶,面包,黄油"
2,"牛奶,尿布,啤酒,面包"
```

明细格式：

```csv
InvoiceNo,Description,Quantity
536370,RABBIT NIGHT LIGHT,24
536370,RED TOADSTOOL LED NIGHT LIGHT,24
```

## 项目结构

```text
association-rule-website/
├── app.py
├── requirements.txt
├── config/
│   └── team.toml
├── data/
│   ├── transactions.csv
│   └── datasets/
│       ├── bread_basket.csv
│       ├── groceries.csv
│       ├── market_basket_grocery.csv
│       ├── uci_online_retail_eire.csv
│       ├── uci_online_retail_france.csv
│       ├── uci_online_retail_germany.csv
│       └── uci_online_retail_united_kingdom.csv
├── algorithms/
│   ├── __init__.py
│   ├── apriori.py
│   ├── fpgrowth.py
│   ├── eclat.py
│   ├── ais.py
│   └── hmine.py
├── scripts/
│   └── generate_course_report.py
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── algorithms.html
│   ├── compare.html
│   ├── dataset.html
│   ├── experiment.html
│   ├── history.html
│   ├── recommender.html
│   ├── team.html
│   └── result.html
└── static/
    ├── css/
    │   └── style.css
    └── js/
        └── main.js
```
