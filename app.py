"""Rule Lake Flask 应用主入口。

这个文件负责把“数据湖资产、三种关联规则算法、结果分析、页面模板”
串成一个可运行的网站：
- 读取内置/上传/本机 CSV 数据；
- 调用 Apriori、FP-Growth、Eclat 算法；
- 生成可视化指标、自动分析、推荐结果；
- 提供首页、数据湖、实验、对比、推荐、历史和成员页路由。
"""

import csv
import io
import json
import re
import tomllib
from collections import Counter
from datetime import datetime
from itertools import combinations
from time import perf_counter
from uuid import uuid4
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request

from algorithms import apriori, eclat, fpgrowth


# 项目路径与默认数据湖资产配置。
BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "transactions.csv"
DATASET_DIR = BASE_DIR / "data" / "datasets"
RESULTS_DIR = BASE_DIR / "data" / "results"
TEAM_CONFIG_PATH = BASE_DIR / "config" / "team.toml"
DEFAULT_DATASET_ID = "uci_france"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

# 算法注册表：页面选择算法时通过 key 找到名称、说明和运行函数。
ALGORITHMS = {
    "apriori": {
        "name": "Apriori",
        "runner": apriori.run,
        "tagline": "候选生成 + 支持度剪枝",
        "compare_note": "过程最直观，适合解释候选生成；数据变大时扫描和候选项集会明显增加。",
    },
    "fpgrowth": {
        "name": "FP-Growth",
        "runner": fpgrowth.run,
        "tagline": "频率排序 + FP-Tree 模式增长",
        "compare_note": "通过 FP-Tree 压缩交易并挖掘条件模式基，通常减少候选组合爆炸，但实现更复杂。",
    },
    "eclat": {
        "name": "Eclat",
        "runner": eclat.run,
        "tagline": "垂直数据格式 + TID-set 交集",
        "compare_note": "用 TID-set 交集计算支持度，稀疏数据上很直接；商品很多时集合存储会占用更多内存。",
    },
}

# 默认数据源说明，用于兼容早期课程要求中的 data/transactions.csv。
BUILTIN_DATASET = {
    "label": "内置数据湖资产：UCI Online Retail France 子集",
    "source": "UCI Machine Learning Repository - Online Retail",
    "source_url": "https://archive.ics.uci.edu/dataset/352/online+retail",
    "detail": "从 UCI 原始 541,909 行线上零售交易中抽取 France 正向订单，聚合为购物篮，并保留高频真实商品描述。",
}

# 数据湖资产注册表：每个资产记录来源、路径、展示名称和推荐阈值。
DATASETS = {
    "uci_france": {
        "label": "UCI Online Retail - France",
        "short": "UCI France",
        "path": DATASET_DIR / "uci_online_retail_france.csv",
        "source": "UCI Machine Learning Repository - Online Retail",
        "source_url": "https://archive.ics.uci.edu/dataset/352/online+retail",
        "family": "线上零售",
        "description": "UCI Online Retail 原始交易中 France 正向订单的购物篮子集。",
        "recommended_support": 0.06,
        "recommended_confidence": 0.50,
    },
    "uci_germany": {
        "label": "UCI Online Retail - Germany",
        "short": "UCI Germany",
        "path": DATASET_DIR / "uci_online_retail_germany.csv",
        "source": "UCI Machine Learning Repository - Online Retail",
        "source_url": "https://archive.ics.uci.edu/dataset/352/online+retail",
        "family": "线上零售",
        "description": "UCI Online Retail 原始交易中 Germany 正向订单的购物篮子集。",
        "recommended_support": 0.06,
        "recommended_confidence": 0.50,
    },
    "uci_eire": {
        "label": "UCI Online Retail - EIRE",
        "short": "UCI EIRE",
        "path": DATASET_DIR / "uci_online_retail_eire.csv",
        "source": "UCI Machine Learning Repository - Online Retail",
        "source_url": "https://archive.ics.uci.edu/dataset/352/online+retail",
        "family": "线上零售",
        "description": "UCI Online Retail 原始交易中 EIRE 正向订单的购物篮子集。",
        "recommended_support": 0.06,
        "recommended_confidence": 0.50,
    },
    "uci_uk": {
        "label": "UCI Online Retail - United Kingdom",
        "short": "UCI UK",
        "path": DATASET_DIR / "uci_online_retail_united_kingdom.csv",
        "source": "UCI Machine Learning Repository - Online Retail",
        "source_url": "https://archive.ics.uci.edu/dataset/352/online+retail",
        "family": "线上零售",
        "description": "UCI Online Retail 原始交易中 United Kingdom 正向订单的购物篮子集。",
        "recommended_support": 0.05,
        "recommended_confidence": 0.45,
    },
    "groceries": {
        "label": "Groceries Dataset",
        "short": "Groceries",
        "path": DATASET_DIR / "groceries.csv",
        "source": "arules Groceries / public GitHub mirror",
        "source_url": "https://github.com/stedy/Machine-Learning-with-R-datasets/blob/master/groceries.csv",
        "family": "超市购物篮",
        "description": "经典超市购物篮数据，每一行是一笔真实格式的商品篮交易。",
        "recommended_support": 0.02,
        "recommended_confidence": 0.30,
    },
    "bread_basket": {
        "label": "Bread Basket Bakery Dataset",
        "short": "Bread Basket",
        "path": DATASET_DIR / "bread_basket.csv",
        "source": "BreadBasket_DMS public GitHub mirror",
        "source_url": "https://github.com/prasertcbs/basic-dataset/blob/master/BreadBasket_DMS.csv",
        "family": "面包店交易",
        "description": "面包店交易明细按 Transaction 聚合后的购物篮数据。",
        "recommended_support": 0.03,
        "recommended_confidence": 0.25,
    },
    "market_basket_grocery": {
        "label": "Market Basket Grocery Dataset",
        "short": "Market Basket",
        "path": DATASET_DIR / "market_basket_grocery.csv",
        "source": "Market Basket Analysis public GitHub mirror",
        "source_url": "https://github.com/HwaiTengTeoh/Market-Basket-Analysis/blob/master/Market_Basket_Data.csv",
        "family": "杂货交易",
        "description": "常用于市场篮分析示例的杂货购物篮数据。",
        "recommended_support": 0.02,
        "recommended_confidence": 0.30,
    },
}

# 上传数据自动识别字段时使用的候选字段名。
TRANSACTION_COLUMN_CANDIDATES = [
    "transaction_id",
    "TransactionID",
    "InvoiceNo",
    "invoice_no",
    "invoice",
    "order_id",
    "basket_id",
]
ITEM_COLUMN_CANDIDATES = [
    "items",
    "Description",
    "description",
    "item",
    "product",
    "product_name",
    "StockCode",
]

# 算法教学页展示的核心伪代码片段。
ALGORITHM_CODE_SNIPPETS = {
    "apriori": {
        "name": "Apriori",
        "title": "候选生成与支持度剪枝核心",
        "code": """def apriori(transactions, min_support):
    L1 = find_frequent_single_items(transactions, min_support)
    frequent = list(L1)
    previous = L1
    k = 2

    while previous:
        candidates = join_and_prune(previous, k)
        current = []
        for itemset in candidates:
            support = count_support(itemset, transactions)
            if support >= min_support:
                current.append(itemset)
                frequent.append(itemset)
        previous = current
        k += 1

    return frequent""",
    },
    "fpgrowth": {
        "name": "FP-Growth",
        "title": "FP-Tree 与条件模式基核心",
        "code": """def fp_growth(transactions, min_count):
    header = count_frequent_items(transactions, min_count)
    tree = build_fp_tree(transactions, header)
    patterns = []

    for item in header.ascending_frequency():
        base = collect_prefix_paths(tree, item)
        conditional_tree = build_fp_tree(base, header)
        patterns.extend(mine_conditional_tree(conditional_tree, item))

    return patterns""",
    },
    "eclat": {
        "name": "Eclat",
        "title": "TID-set 交集递归核心",
        "code": """def eclat(prefix, items, min_count):
    for i, (itemset, tidset) in enumerate(items):
        output(prefix | itemset)
        suffix = []
        for next_itemset, next_tidset in items[i + 1:]:
            joined_tidset = tidset & next_tidset
            if len(joined_tidset) >= min_count:
                suffix.append((itemset | next_itemset, joined_tidset))
        eclat(prefix | itemset, suffix, min_count)""",
    },
}

# 小组配置的默认值；如果 config/team.toml 不存在或损坏，页面使用这里兜底。
DEFAULT_TEAM_CONFIG = {
    "group": {
        "name": "第 3 组",
        "project_name": "关联规则挖掘算法课程网站",
        "subtitle": "Apriori / FP-Growth / Eclat",
        "course": "数据挖掘课程项目",
        "description": "基于真实购物篮数据，完成关联规则挖掘算法教学、实验运行、结果分析和报告导出。",
    },
    "members": [
        {
            "name": "张三",
            "student_id": "20240001",
            "role": "组长 / 后端与算法",
            "avatar": "张",
            "contact": "",
            "responsibility": ["Flask 路由设计", "Apriori 算法实现", "实验结果分析"],
        },
        {
            "name": "李四",
            "student_id": "20240002",
            "role": "数据湖与前端",
            "avatar": "李",
            "contact": "",
            "responsibility": ["真实数据湖资产整理", "数据湖页面展示", "前端交互优化"],
        },
        {
            "name": "王五",
            "student_id": "20240003",
            "role": "算法讲解与报告",
            "avatar": "王",
            "contact": "",
            "responsibility": ["FP-Growth / Eclat 讲解", "可视化教学内容", "实验报告整理"],
        },
    ],
    "modules": [
        {"name": "数据湖资产管理", "owner": "全组", "status": "已完成", "description": "内置多个公开购物篮资产，支持上传 CSV 和服务器本机路径。"},
        {"name": "算法运行控制台", "owner": "全组", "status": "已完成", "description": "支持算法选择、阈值设置、三算法对比和支持度扫描。"},
        {"name": "可视化教学舱", "owner": "全组", "status": "已完成", "description": "用动态步骤解释 Apriori、FP-Growth、Eclat 的核心过程。"},
        {"name": "结果分析与导出", "owner": "全组", "status": "已完成", "description": "展示频繁项集、关联规则、lift 分析、CSV 导出和 Markdown 报告。"},
    ],
    "milestones": [
        {"title": "真实数据湖接入", "date": "第 1 阶段", "status": "已完成"},
        {"title": "三种算法可运行", "date": "第 2 阶段", "status": "已完成"},
        {"title": "可视化教学与结果分析", "date": "第 3 阶段", "status": "已完成"},
        {"title": "页面发布与小组展示", "date": "第 4 阶段", "status": "进行中"},
    ],
}


def normalize_item(value):
    """清洗商品名称或字段值，合并多余空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def split_items(value):
    """把购物篮字符串拆成商品列表，兼容逗号、分号、顿号等分隔符。"""
    text = normalize_item(value)
    if not text:
        return []

    separator = ","
    for candidate in ["|", ";", "；", "，", "、"]:
        if candidate in text:
            separator = candidate
            break

    return [normalize_item(item) for item in text.split(separator) if normalize_item(item)]


def unique_items(items):
    """按原始顺序去重，避免同一交易内重复商品影响支持度。"""
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def merge_team_config(config):
    """把 TOML 配置与默认成员配置合并，补齐缺失字段。"""
    merged = {
        "group": {**DEFAULT_TEAM_CONFIG["group"], **config.get("group", {})},
        "members": config.get("members") or DEFAULT_TEAM_CONFIG["members"],
        "modules": config.get("modules") or DEFAULT_TEAM_CONFIG["modules"],
        "milestones": config.get("milestones") or DEFAULT_TEAM_CONFIG["milestones"],
    }

    for member in merged["members"]:
        member.setdefault("avatar", member.get("name", "?")[:1] or "?")
        member.setdefault("role", "成员")
        member.setdefault("student_id", "")
        member.setdefault("contact", "")
        member.setdefault("responsibility", [])

    return merged


def load_team_config():
    """读取 config/team.toml；读取失败时返回默认配置。"""
    if not TEAM_CONFIG_PATH.exists():
        return DEFAULT_TEAM_CONFIG

    try:
        with TEAM_CONFIG_PATH.open("rb") as file:
            return merge_team_config(tomllib.load(file))
    except (tomllib.TOMLDecodeError, OSError):
        return DEFAULT_TEAM_CONFIG


def read_basket_csv(path):
    """读取已经转换好的 transaction_id,items 购物篮 CSV。"""
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            items = split_items(row["items"])
            rows.append(
                {
                    "transaction_id": row["transaction_id"],
                    "items": items,
                    "items_text": "、".join(items),
                }
            )
    return rows


def read_builtin_transactions(dataset_id=DEFAULT_DATASET_ID):
    """读取内置数据湖资产，缺失时回退到课程要求的 transactions.csv。"""
    dataset = DATASETS.get(dataset_id, DATASETS[DEFAULT_DATASET_ID])
    if dataset["path"].exists():
        return read_basket_csv(dataset["path"])
    return read_basket_csv(DATA_PATH)


def basic_dataset_stats(rows):
    """计算轻量级数据资产摘要，用于首页和数据湖资产列表。"""
    counter = Counter()
    for row in rows:
        counter.update(row["items"])
    transaction_count = len(rows)
    item_count = len(counter)
    avg_basket_size = round(sum(len(row["items"]) for row in rows) / transaction_count, 2) if rows else 0
    return {
        "transaction_count": transaction_count,
        "item_count": item_count,
        "avg_basket_size": avg_basket_size,
    }


def dataset_library():
    """构建页面使用的数据湖资产列表，并附带基础统计信息。"""
    library = []
    for dataset_id, meta in DATASETS.items():
        rows = read_builtin_transactions(dataset_id)
        summary = basic_dataset_stats(rows)
        library.append({"id": dataset_id, **meta, **summary})
    return library


def preview_payload(rows, label):
    """把数据预览结果整理成 JSON，供实验页异步校验使用。"""
    stats = dataset_stats(rows)
    return {
        "ok": True,
        "label": label,
        "transaction_count": stats["transaction_count"],
        "item_count": stats["item_count"],
        "avg_basket_size": stats["avg_basket_size"],
        "density": stats["density"],
        "top_items": stats["top_items"][:8],
        "preview_rows": [
            {
                "transaction_id": row["transaction_id"],
                "items_text": row["items_text"],
            }
            for row in rows[:20]
        ],
    }


def find_column(fieldnames, explicit_name, candidates):
    """从 CSV 表头中查找交易字段或商品字段。"""
    normalized = {field.strip().lower(): field for field in fieldnames if field}
    if explicit_name:
        key = explicit_name.strip().lower()
        if key in normalized:
            return normalized[key]
        raise ValueError(f"找不到指定字段：{explicit_name}")

    for candidate in candidates:
        key = candidate.lower()
        if key in normalized:
            return normalized[key]
    return None


def read_transactions_from_csv_text(text, transaction_column="", item_column=""):
    """读取用户上传/本机路径 CSV，并统一转换为购物篮行结构。

    支持两类格式：
    - 已聚合购物篮：transaction_id,items
    - 交易明细：InvoiceNo,Description,Quantity
    """
    reader = csv.DictReader(io.StringIO(text), skipinitialspace=True)
    if not reader.fieldnames:
        raise ValueError("CSV 文件没有表头。")

    fieldnames = [field.strip("\ufeff") if field else field for field in reader.fieldnames]
    reader.fieldnames = fieldnames
    transaction_col = find_column(fieldnames, transaction_column, TRANSACTION_COLUMN_CANDIDATES)
    item_col = find_column(fieldnames, item_column, ITEM_COLUMN_CANDIDATES)

    if not transaction_col or not item_col:
        raise ValueError("无法自动识别交易字段和商品字段，请在表单中填写 transaction/item 字段名。")

    baskets = {}
    basket_format = item_col.lower() == "items"

    for row in reader:
        # 取消订单、空交易号和非正数量记录都不进入实验数据。
        transaction_id = normalize_item(row.get(transaction_col))
        if not transaction_id:
            continue
        if transaction_id.upper().startswith("C"):
            continue

        quantity_text = row.get("Quantity") or row.get("quantity") or "1"
        try:
            quantity = float(quantity_text)
        except ValueError:
            quantity = 1
        if quantity <= 0:
            continue

        if basket_format:
            # items 列可能被 CSV 解析成多个列，这里把溢出列一起合并。
            raw_items = [row.get(item_col, "")]
            if row.get(None):
                raw_items.extend(row[None])
            items = []
            for value in raw_items:
                items.extend(split_items(value))
        else:
            items = [normalize_item(row.get(item_col))]

        if not items:
            continue
        baskets.setdefault(transaction_id, []).extend(items)

    rows = []
    for transaction_id, items in baskets.items():
        # 同一交易内去重后再写入，保证支持度以“交易出现过”为准。
        cleaned_items = unique_items(items)
        if cleaned_items:
            rows.append(
                {
                    "transaction_id": transaction_id,
                    "items": cleaned_items,
                    "items_text": "、".join(cleaned_items),
                }
            )

    if not rows:
        raise ValueError("数据湖资产中没有可用交易记录。")
    return rows


def read_text_file(path):
    """读取本机 CSV 文本，优先 UTF-8，兼容 GBK。"""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="gbk")


def decode_csv_bytes(content):
    """解码上传文件内容，兼容 UTF-8 BOM 和 GBK。"""
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("gbk")


def rows_from_request():
    """根据实验表单选择的数据源返回购物篮行和数据标签。"""
    mode = request.form.get("dataset_mode", "builtin")
    dataset_id = request.form.get("builtin_dataset", DEFAULT_DATASET_ID)
    transaction_column = request.form.get("transaction_column", "").strip()
    item_column = request.form.get("item_column", "").strip()

    if mode == "upload":
        uploaded = request.files.get("dataset_file")
        if not uploaded or not uploaded.filename:
            raise ValueError("请选择要上传的 CSV 文件。")
        text = decode_csv_bytes(uploaded.stream.read())
        rows = read_transactions_from_csv_text(text, transaction_column, item_column)
        return rows, f"上传数据湖资产：{uploaded.filename}"

    if mode == "local_path":
        raw_path = request.form.get("dataset_path", "").strip()
        if not raw_path:
            raise ValueError("请填写本机 CSV 路径。")
        path = Path(raw_path).expanduser()
        if not path.exists() or not path.is_file():
            raise ValueError(f"找不到 CSV 文件：{path}")
        if path.suffix.lower() != ".csv":
            raise ValueError("当前初版自定义数据湖资产支持 CSV 文件。")
        rows = read_transactions_from_csv_text(read_text_file(path), transaction_column, item_column)
        return rows, f"本机数据湖资产：{path}"

    dataset = DATASETS.get(dataset_id, DATASETS[DEFAULT_DATASET_ID])
    return read_builtin_transactions(dataset_id), dataset["label"]


def apply_transaction_limit(rows):
    """按表单中的 max_transactions 限制本次实验交易数量。"""
    try:
        max_transactions = int(request.form.get("max_transactions", "300"))
    except ValueError:
        max_transactions = 300
    max_transactions = min(max(max_transactions, 20), 2000)

    if len(rows) > max_transactions:
        return rows[:max_transactions], f"已使用前 {max_transactions} 条交易进行本次实验。"
    return rows, ""


def transaction_sets(rows):
    """把模板友好的行结构转换成算法需要的 set 交易列表。"""
    return [set(row["items"]) for row in rows]


def dataset_stats(rows):
    """计算数据湖资产画像：高频商品、共现商品、篮子大小分布等。"""
    counter = Counter()
    pair_counter = Counter()
    basket_sizes = Counter()
    for row in rows:
        counter.update(row["items"])
        basket_sizes[len(row["items"])] += 1
        for pair in combinations(sorted(set(row["items"])), 2):
            pair_counter[pair] += 1

    transaction_count = len(rows)
    item_count = len(counter)
    avg_basket_size = round(sum(len(row["items"]) for row in rows) / transaction_count, 2) if rows else 0
    density = round((avg_basket_size / item_count) * 100, 2) if item_count else 0
    max_item_count = max(counter.values(), default=1)
    max_pair_count = max(pair_counter.values(), default=1)
    max_basket_count = max(basket_sizes.values(), default=1)

    return {
        "transaction_count": transaction_count,
        "item_count": item_count,
        "avg_basket_size": avg_basket_size,
        "max_basket_size": max(basket_sizes.keys(), default=0),
        "density": density,
        "top_items": [
            {
                "name": item,
                "count": count,
                "support": count / transaction_count if transaction_count else 0,
                "width": round((count / max_item_count) * 100, 2),
            }
            for item, count in counter.most_common(12)
        ],
        "top_pairs": [
            {
                "items": list(pair),
                "count": count,
                "support": count / transaction_count if transaction_count else 0,
                "width": round((count / max_pair_count) * 100, 2),
            }
            for pair, count in pair_counter.most_common(8)
        ],
        "basket_distribution": [
            {
                "size": size,
                "count": count,
                "width": round((count / max_basket_count) * 100, 2),
            }
            for size, count in sorted(basket_sizes.items())
        ],
    }


def parse_threshold(value, default):
    """解析支持度/置信度阈值，允许用户输入 0.05 或 5。"""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default

    if parsed > 1:
        parsed = parsed / 100

    return min(max(parsed, 0.01), 1.0)


def format_percent(value):
    """把小数格式化成百分比字符串。"""
    return f"{value * 100:.2f}%"


def join_items(items):
    """用中文顿号连接项集，供模板展示。"""
    return "、".join(items)


def build_analysis(frequent_itemsets, rules):
    """根据频繁项集和关联规则生成结果页的自动文字分析。"""
    analysis = []
    pair_itemsets = [row for row in frequent_itemsets if len(row["items"]) >= 2]
    top_pairs = sorted(pair_itemsets, key=lambda row: (-row["support"], len(row["items"]), row["items"]))[:3]
    top_confidence_rules = sorted(rules, key=lambda row: (-row["confidence"], -row["lift"]))[:3]
    lift_rules = [row for row in rules if row["lift"] > 1]

    if top_pairs:
        names = "；".join(
            f"{join_items(row['items'])}（支持度 {format_percent(row['support'])}）"
            for row in top_pairs
        )
        analysis.append(f"从频繁项集看，{names} 经常在同一个购物篮中出现。")
    else:
        analysis.append("当前参数下没有发现二项及以上的频繁项集，可以适当降低最小支持度。")

    if top_confidence_rules:
        rule_text = "；".join(
            f"{join_items(row['antecedent'])} -> {join_items(row['consequent'])}"
            f"（置信度 {format_percent(row['confidence'])}）"
            for row in top_confidence_rules
        )
        analysis.append(f"高置信度规则表示当前件出现时，后件也出现的概率较高。例如：{rule_text}。")
    else:
        analysis.append("当前参数下没有满足最小置信度的关联规则，可以降低最小置信度观察更多候选规则。")

    if lift_rules:
        best = max(lift_rules, key=lambda row: row["lift"])
        analysis.append(
            f"lift 大于 1 说明前件会提升后件出现的可能性。当前最高提升度规则是 "
            f"{join_items(best['antecedent'])} -> {join_items(best['consequent'])}，"
            f"lift={best['lift']:.2f}。"
        )
    else:
        analysis.append("当前结果中没有 lift 大于 1 的规则，说明已筛选规则暂未表现出明显正相关。")

    return analysis


def build_result_visuals(frequent_itemsets, rules):
    """构建结果页图表需要的 Top 项集、Top 规则和分布数据。"""
    top_itemsets = sorted(
        [row for row in frequent_itemsets if len(row["items"]) >= 2],
        key=lambda row: (-row["support"], len(row["items"]), row["items"]),
    )[:10]
    max_itemset_support = max((row["support"] for row in top_itemsets), default=1)

    top_rules = sorted(rules, key=lambda row: (-row["lift"], -row["confidence"], -row["support"]))[:10]
    max_rule_lift = max((row["lift"] for row in top_rules), default=1)

    size_counter = Counter(len(row["items"]) for row in frequent_itemsets)
    max_size_count = max(size_counter.values(), default=1)

    avg_confidence = sum(rule["confidence"] for rule in rules) / len(rules) if rules else 0
    avg_lift = sum(rule["lift"] for rule in rules) / len(rules) if rules else 0

    return {
        "top_itemsets": [
            {
                **row,
                "width": round((row["support"] / max_itemset_support) * 100, 2),
            }
            for row in top_itemsets
        ],
        "top_rules": [
            {
                **row,
                "width": round((row["lift"] / max_rule_lift) * 100, 2),
            }
            for row in top_rules
        ],
        "itemset_size_counts": [
            {
                "size": size,
                "count": count,
                "width": round((count / max_size_count) * 100, 2),
            }
            for size, count in sorted(size_counter.items())
        ],
        "avg_confidence": avg_confidence,
        "avg_lift": avg_lift,
    }


def parse_first_ints(text):
    """从算法日志中提取整数，用于生成运行阶段可视化卡片。"""
    return [int(value) for value in re.findall(r"\d+", text)]


def build_run_stages(algorithm_key, process_logs, frequent_itemsets, rules):
    """把不同算法的过程日志转换成统一的阶段卡片数据。"""
    stages = []

    if algorithm_key == "apriori":
        # Apriori 日志中有每轮 Ck/Lk 数量，可直接转成候选剪枝阶段。
        for log in process_logs:
            if "第 " in log and "候选项集" in log and "频繁项集" in log:
                round_match = re.search(r"第\s*(\d+)\s*轮", log)
                count_match = re.search(r"候选项集\s*(\d+)\s*个.*频繁项集\s*(\d+)\s*个", log)
                if round_match and count_match:
                    stages.append(
                        {
                            "label": f"L{round_match.group(1)}",
                            "title": f"第 {round_match.group(1)} 轮候选剪枝",
                            "primary": int(count_match.group(1)),
                            "secondary": int(count_match.group(2)),
                            "primary_label": "候选项集",
                            "secondary_label": "频繁项集",
                            "width": 100,
                        }
                    )
        if not stages:
            stages.append({"label": "SCAN", "title": "支持度扫描", "primary": len(frequent_itemsets), "secondary": len(rules), "primary_label": "项集", "secondary_label": "规则", "width": 100})

    elif algorithm_key == "fpgrowth":
        # FP-Growth 关注低支持度过滤、FP-Tree 构建和频繁模式挖掘。
        for log in process_logs:
            if "保留" in log and "频繁单项" in log:
                numbers = parse_first_ints(log)
                stages.append({"label": "FILTER", "title": "删除低支持度项", "primary": numbers[-1] if numbers else 0, "secondary": 0, "primary_label": "频繁单项", "secondary_label": "", "width": 72})
            elif "构建 FP-Tree" in log:
                numbers = parse_first_ints(log)
                stages.append({"label": "TREE", "title": "构建 FP-Tree", "primary": numbers[0] if numbers else 0, "secondary": numbers[1] if len(numbers) > 1 else 0, "primary_label": "节点数", "secondary_label": "根分支", "width": 100})
            elif "频繁项集" in log and "得到" in log:
                numbers = parse_first_ints(log)
                stages.append({"label": "MINE", "title": "挖掘频繁模式", "primary": numbers[-1] if numbers else len(frequent_itemsets), "secondary": len(rules), "primary_label": "频繁项集", "secondary_label": "规则", "width": 90})

    else:
        # Eclat 关注垂直格式、频繁单项和递归交集扩展。
        for log in process_logs:
            if "垂直数据格式构建完成" in log:
                numbers = parse_first_ints(log)
                stages.append({"label": "VERTICAL", "title": "构建 TID-set", "primary": numbers[-1] if numbers else 0, "secondary": 0, "primary_label": "商品映射", "secondary_label": "", "width": 75})
            elif "初始频繁单项" in log:
                numbers = parse_first_ints(log)
                stages.append({"label": "L1", "title": "筛选频繁单项", "primary": numbers[-1] if numbers else 0, "secondary": 0, "primary_label": "频繁单项", "secondary_label": "", "width": 82})
            elif "递归扩展完成" in log:
                numbers = parse_first_ints(log)
                stages.append({"label": "RECURSE", "title": "递归交集扩展", "primary": numbers[0] if numbers else 0, "secondary": numbers[-1] if numbers else len(frequent_itemsets), "primary_label": "扩展次数", "secondary_label": "频繁项集", "width": 100})

    max_primary = max((stage["primary"] for stage in stages), default=1)
    for stage in stages:
        # width 用于页面进度条，保留最小宽度避免 0 值视觉上消失。
        stage["width"] = max(12, round((stage["primary"] / max_primary) * 100, 2)) if max_primary else 12
    return stages


def utc_timestamp():
    """生成记录文件使用的时间戳。

    这里使用本机时间并格式化到秒，主要服务于课堂展示和服务器本地排查；
    run_id 仍然由 uuid 生成，因此即使同一秒内多次运行也不会覆盖。
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def compact_rule(rule):
    """把完整关联规则压缩成历史列表可直接展示的轻量结构。"""
    if not rule:
        return None
    return {
        "antecedent": rule["antecedent"],
        "consequent": rule["consequent"],
        "support": rule["support"],
        "confidence": rule["confidence"],
        "lift": rule["lift"],
        "text": f"{join_items(rule['antecedent'])} -> {join_items(rule['consequent'])}",
    }


def summarize_algorithm_runs(run_results):
    """把一次请求内的多算法结果压缩为模板展示需要的摘要列表。

    run_algorithm_with_timing 返回值里包含完整频繁项集和规则；三算法对比卡片
    只需要耗时、项集数、规则数和最高 lift，因此这里剥离大字段，减少保存记录
    和模板渲染的负担。
    """
    return [
        {
            "key": key,
            "name": run["name"],
            "tagline": run["tagline"],
            "elapsed_ms": run["elapsed_ms"],
            "frequent_count": run["frequent_count"],
            "rules_count": run["rules_count"],
            "best_lift": run["best_lift"],
            "best_confidence": run["best_confidence"],
            "avg_confidence": run["avg_confidence"],
            "avg_lift": run["avg_lift"],
            "best_rule": compact_rule(run["best_rule"]),
        }
        for key, run in run_results.items()
    ]


def run_record_path(run_id):
    """根据 run_id 生成实验记录 JSON 路径，并阻止路径穿越。"""
    if not re.fullmatch(r"[0-9a-f]{12}", run_id or ""):
        raise ValueError("实验记录编号格式不正确。")
    return RESULTS_DIR / f"{run_id}.json"


def save_run_record(record):
    """把一次完整实验写入 data/results/run_id.json。"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = run_record_path(record["run_id"])
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_run_record(run_id):
    """读取单个后端实验记录，找不到时返回 None。"""
    try:
        path = run_record_path(run_id)
    except ValueError:
        return None
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def summarize_run_record(record):
    """把完整实验记录转换成历史页展示用的摘要卡片。"""
    best_rule = record.get("best_rule") or {}
    parameters = record.get("parameters", {})
    dataset = record.get("dataset", {})
    result = record.get("result", {})
    return {
        "run_id": record.get("run_id", ""),
        "created_at": record.get("created_at", ""),
        "algorithm_key": record.get("algorithm_key", ""),
        "algorithm_name": record.get("algorithm_name", ""),
        "dataset_label": dataset.get("label", ""),
        "history_dataset_id": dataset.get("history_dataset_id", ""),
        "min_support": parameters.get("min_support", 0),
        "min_confidence": parameters.get("min_confidence", 0),
        "max_transactions": parameters.get("max_transactions", 0),
        "elapsed_ms": record.get("elapsed_ms", 0),
        "frequent_count": len(result.get("frequent_itemsets", [])),
        "rules_count": len(result.get("rules", [])),
        "best_rule_text": best_rule.get("text", "暂无规则"),
        "best_lift": best_rule.get("lift", 0),
    }


def list_run_records(limit=40):
    """按文件更新时间倒序列出后端实验记录摘要。"""
    if not RESULTS_DIR.exists():
        return []

    records = []
    paths = sorted(RESULTS_DIR.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in paths[:limit]:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        records.append(summarize_run_record(record))
    return records


def build_run_record(
    run_id,
    created_at,
    algorithm_key,
    selected_run,
    dataset_label,
    history_dataset_id,
    max_transactions,
    min_support,
    min_confidence,
    stats,
    result,
    process_logs,
    analysis,
    result_visuals,
    run_stages,
    comparison,
    dataset_comparison,
    threshold_sweep,
    parameter_grid,
    grid_analysis,
):
    """组装一次实验的完整后端记录。

    记录中保留完整频繁项集和关联规则，目的是让历史详情页不重新计算也能打开；
    同时保存参数、数据集摘要、过程日志、图表数据和扫描结果，便于后续导出报告。
    """
    best_rule = max(result["rules"], key=lambda rule: (rule["lift"], rule["confidence"], rule["support"]), default=None)
    return {
        "run_id": run_id,
        "created_at": created_at,
        "algorithm_key": algorithm_key,
        "algorithm_name": selected_run["name"],
        "algorithm_tagline": selected_run["tagline"],
        "elapsed_ms": selected_run["elapsed_ms"],
        "best_rule": compact_rule(best_rule),
        "parameters": {
            "min_support": min_support,
            "min_confidence": min_confidence,
            "max_transactions": max_transactions,
        },
        "dataset": {
            "label": dataset_label,
            "history_dataset_id": history_dataset_id,
            "stats": stats,
        },
        "result": {
            "frequent_itemsets": result["frequent_itemsets"],
            "rules": result["rules"],
            "process_logs": process_logs,
            "analysis": analysis,
            "visuals": result_visuals,
            "stages": run_stages,
        },
        "comparison": comparison,
        "dataset_comparison": dataset_comparison,
        "threshold_sweep": threshold_sweep,
        "parameter_grid": parameter_grid,
        "grid_analysis": grid_analysis,
    }


def render_result_from_record(record):
    """把保存过的后端实验记录重新渲染为结果详情页。"""
    parameters = record["parameters"]
    dataset = record["dataset"]
    result = record["result"]
    return render_template(
        "result.html",
        run_id=record["run_id"],
        server_record=True,
        created_at=record["created_at"],
        algorithm_key=record["algorithm_key"],
        algorithm_name=record["algorithm_name"],
        algorithm_tagline=record["algorithm_tagline"],
        elapsed_ms=record["elapsed_ms"],
        min_support=parameters["min_support"],
        min_confidence=parameters["min_confidence"],
        frequent_itemsets=result["frequent_itemsets"],
        rules=result["rules"],
        process_logs=result["process_logs"],
        analysis=result["analysis"],
        stats=dataset["stats"],
        dataset_label=dataset["label"],
        history_dataset_id=dataset.get("history_dataset_id", ""),
        max_transactions=parameters["max_transactions"],
        comparison=record.get("comparison", []),
        result_visuals=result["visuals"],
        run_stages=result["stages"],
        dataset_comparison=record.get("dataset_comparison", []),
        threshold_sweep=record.get("threshold_sweep", []),
        parameter_grid=record.get("parameter_grid", {}),
        grid_analysis=record.get("grid_analysis", []),
    )


def run_dataset_comparison(algorithm_key, min_support, min_confidence, max_transactions):
    """在所有内置数据湖资产上运行同一算法，生成跨资产对比表。"""
    comparison = []
    for dataset_id, meta in DATASETS.items():
        rows = read_builtin_transactions(dataset_id)
        limited_rows = rows[:max_transactions]
        transactions = transaction_sets(limited_rows)
        run = run_algorithm_with_timing(algorithm_key, transactions, min_support, min_confidence)
        comparison.append(
            {
                "dataset_id": dataset_id,
                "label": meta["short"],
                "family": meta["family"],
                "transactions": len(limited_rows),
                "items": basic_dataset_stats(limited_rows)["item_count"],
                "elapsed_ms": run["elapsed_ms"],
                "frequent_count": run["frequent_count"],
                "rules_count": run["rules_count"],
                "best_lift": run["best_lift"],
            }
        )
    return comparison


def run_threshold_sweep(algorithm_key, transactions, min_confidence):
    """固定置信度，扫描多组支持度，观察规则数量变化。

    扫描用于页面交互演示，不追求离线全量穷举；最多取前 120 条交易，
    避免低支持度组合在课堂展示时生成过多规则导致页面等待过久。
    """
    sweep_transactions = transactions[:120]
    sweep_supports = [0.06, 0.08, 0.10, 0.12, 0.15, 0.20]
    rows = []
    for support in sweep_supports:
        run = run_algorithm_with_timing(algorithm_key, sweep_transactions, support, min_confidence)
        rows.append(
            {
                "support": support,
                "sample_size": len(sweep_transactions),
                "elapsed_ms": run["elapsed_ms"],
                "frequent_count": run["frequent_count"],
                "rules_count": run["rules_count"],
                "best_lift": run["best_lift"],
            }
        )
    max_rules = max((row["rules_count"] for row in rows), default=1)
    max_itemsets = max((row["frequent_count"] for row in rows), default=1)
    for row in rows:
        row["rules_width"] = round((row["rules_count"] / max_rules) * 100, 2) if max_rules else 0
        row["itemsets_width"] = round((row["frequent_count"] / max_itemsets) * 100, 2) if max_itemsets else 0
    return rows


def run_parameter_grid(algorithm_key, transactions):
    """执行 support × confidence 二维参数网格实验。

    这个函数是“训练/实验引擎”的核心增强版：它不会只跑用户当前的一组阈值，
    而是在同一数据集和同一算法下扫描多组阈值组合，从而观察：
    - support 越低时频繁项集和规则数量如何变化；
    - confidence 越高时规则筛选有多严格；
    - 哪些参数组合能得到高 lift 规则，哪些组合运行更快。
    """
    grid_transactions = transactions[:120]
    support_values = [0.08, 0.10, 0.12, 0.15]
    confidence_values = [0.40, 0.60, 0.80]
    cells = []

    for support in support_values:
        for confidence in confidence_values:
            run = run_algorithm_with_timing(algorithm_key, grid_transactions, support, confidence)
            cells.append(
                {
                    "support": support,
                    "confidence": confidence,
                    "elapsed_ms": run["elapsed_ms"],
                    "frequent_count": run["frequent_count"],
                    "rules_count": run["rules_count"],
                    "best_lift": run["best_lift"],
                    "best_confidence": run["best_confidence"],
                }
            )

    max_rules = max((cell["rules_count"] for cell in cells), default=1)
    max_elapsed = max((cell["elapsed_ms"] for cell in cells), default=1)
    max_lift = max((cell["best_lift"] for cell in cells), default=1)
    for cell in cells:
        # 三个 width 字段分别服务于页面上的热力块、耗时条和 lift 强度条。
        cell["rules_width"] = round((cell["rules_count"] / max_rules) * 100, 2) if max_rules else 0
        cell["elapsed_width"] = round((cell["elapsed_ms"] / max_elapsed) * 100, 2) if max_elapsed else 0
        cell["lift_width"] = round((cell["best_lift"] / max_lift) * 100, 2) if max_lift else 0

    matrix = [
        {
            "support": support,
            "cells": [cell for cell in cells if cell["support"] == support],
        }
        for support in support_values
    ]

    return {
        "supports": support_values,
        "confidences": confidence_values,
        "sample_size": len(grid_transactions),
        "cells": cells,
        "matrix": matrix,
        "best_by_rules": max(cells, key=lambda cell: cell["rules_count"], default=None),
        "best_by_lift": max(cells, key=lambda cell: cell["best_lift"], default=None),
        "fastest": min(cells, key=lambda cell: cell["elapsed_ms"], default=None),
    }


def build_grid_analysis(parameter_grid):
    """根据二维参数扫描结果生成可直接汇报的分析句子。"""
    if not parameter_grid:
        return []

    analysis = []
    best_by_rules = parameter_grid.get("best_by_rules")
    best_by_lift = parameter_grid.get("best_by_lift")
    fastest = parameter_grid.get("fastest")

    if best_by_rules:
        analysis.append(
            f"规则数量最多的组合是 support={best_by_rules['support']:.2f}、"
            f"confidence={best_by_rules['confidence']:.2f}，得到 {best_by_rules['rules_count']} 条规则，"
            "适合做探索性分析。"
        )
    if best_by_lift:
        analysis.append(
            f"最高 lift 出现在 support={best_by_lift['support']:.2f}、"
            f"confidence={best_by_lift['confidence']:.2f}，lift={best_by_lift['best_lift']:.2f}，"
            "适合挑选强相关规则。"
        )
    if fastest:
        analysis.append(
            f"耗时最低的组合是 support={fastest['support']:.2f}、"
            f"confidence={fastest['confidence']:.2f}，耗时 {fastest['elapsed_ms']:.2f} ms，"
            "通常更适合课堂快速演示。"
        )
    return analysis


def run_algorithm_with_timing(algorithm_key, transactions, min_support, min_confidence):
    """统一调用算法并记录耗时、最佳规则和聚合指标。"""
    selected = ALGORITHMS[algorithm_key]
    started = perf_counter()
    result = selected["runner"](transactions, min_support, min_confidence)
    elapsed_ms = (perf_counter() - started) * 1000
    rules = result["rules"]
    best_rule = max(rules, key=lambda rule: (rule["lift"], rule["confidence"], rule["support"]), default=None)
    best_lift = best_rule["lift"] if best_rule else 0
    best_confidence = max((rule["confidence"] for rule in rules), default=0)
    avg_confidence = sum(rule["confidence"] for rule in rules) / len(rules) if rules else 0
    avg_lift = sum(rule["lift"] for rule in rules) / len(rules) if rules else 0

    return {
        "key": algorithm_key,
        "name": selected["name"],
        "tagline": selected["tagline"],
        "compare_note": selected["compare_note"],
        "elapsed_ms": elapsed_ms,
        "frequent_count": len(result["frequent_itemsets"]),
        "rules_count": len(result["rules"]),
        "best_lift": best_lift,
        "best_confidence": best_confidence,
        "avg_confidence": avg_confidence,
        "avg_lift": avg_lift,
        "best_rule": best_rule,
        "result": result,
    }


def clamp_int(value, default, minimum=20, maximum=2000):
    """解析整数参数并限制在安全范围内。"""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def dataset_item_choices(rows, limit=48):
    """为推荐模拟器生成可点击的高频商品候选项。"""
    counter = Counter()
    for row in rows:
        counter.update(row["items"])
    total = len(rows)
    max_count = max(counter.values(), default=1)
    return [
        {
            "name": name,
            "count": count,
            "support": count / total if total else 0,
            "width": round((count / max_count) * 100, 2),
        }
        for name, count in counter.most_common(limit)
    ]


def build_algorithm_comparison(dataset_id, min_support, min_confidence, max_transactions):
    """同一数据湖资产、同一参数下对比三种算法。"""
    dataset = DATASETS.get(dataset_id, DATASETS[DEFAULT_DATASET_ID])
    rows = read_builtin_transactions(dataset_id)[:max_transactions]
    transactions = transaction_sets(rows)
    runs = [run_algorithm_with_timing(key, transactions, min_support, min_confidence) for key in ALGORITHMS]

    max_elapsed = max((run["elapsed_ms"] for run in runs), default=1)
    max_itemsets = max((run["frequent_count"] for run in runs), default=1)
    max_rules = max((run["rules_count"] for run in runs), default=1)
    max_lift = max((run["best_lift"] for run in runs), default=1)

    for run in runs:
        # width 字段用于对比页的横向条形图。
        run["time_width"] = round((run["elapsed_ms"] / max_elapsed) * 100, 2) if max_elapsed else 0
        run["itemset_width"] = round((run["frequent_count"] / max_itemsets) * 100, 2) if max_itemsets else 0
        run["rule_width"] = round((run["rules_count"] / max_rules) * 100, 2) if max_rules else 0
        run["lift_width"] = round((run["best_lift"] / max_lift) * 100, 2) if max_lift else 0

    fastest = min(runs, key=lambda row: row["elapsed_ms"], default=None)
    richest = max(runs, key=lambda row: row["rules_count"], default=None)
    strongest = max(runs, key=lambda row: row["best_lift"], default=None)
    analysis = []
    if fastest:
        analysis.append(f"{fastest['name']} 在当前参数下耗时最低，适合强调运行效率。")
    if richest:
        analysis.append(f"{richest['name']} 生成的规则数量最多，适合做规则探索。")
    if strongest and strongest["best_rule"]:
        rule = strongest["best_rule"]
        analysis.append(
            f"最高 lift 来自 {strongest['name']}：{join_items(rule['antecedent'])} -> "
            f"{join_items(rule['consequent'])}，lift={rule['lift']:.2f}。"
        )

    return {
        "dataset": dataset,
        "dataset_id": dataset_id,
        "rows": rows,
        "stats": dataset_stats(rows),
        "runs": runs,
        "analysis": analysis,
    }


def selected_items_from_request():
    """读取推荐模拟器中勾选和手动输入的商品。"""
    selected = request.args.getlist("items")
    manual = request.args.get("basket", "")
    selected.extend(split_items(manual))
    return unique_items([normalize_item(item) for item in selected if normalize_item(item)])


def build_recommendations(rules, selected_items):
    """根据当前购物篮和关联规则生成推荐商品列表。

    完整匹配：规则前件完全包含在当前购物篮中；
    相关规则：规则前件与当前购物篮有交集，但不是完整包含。
    """
    selected = set(selected_items)
    strict = []
    related = []

    for rule in rules:
        antecedent = set(rule["antecedent"])
        consequent = [item for item in rule["consequent"] if item not in selected]
        if not consequent:
            continue

        # 推荐分综合 confidence、lift 和 support，便于排序展示。
        record = {
            "antecedent": rule["antecedent"],
            "consequent": consequent,
            "support": rule["support"],
            "confidence": rule["confidence"],
            "lift": rule["lift"],
            "score": round((rule["confidence"] * 0.52 + min(rule["lift"] / 5, 1) * 0.33 + rule["support"] * 0.15) * 100, 2),
            "match_type": "完整匹配",
        }

        if antecedent.issubset(selected):
            strict.append(record)
        elif antecedent & selected:
            record["match_type"] = "相关规则"
            record["score"] = round(record["score"] * 0.72, 2)
            related.append(record)

    merged = {}
    for record in strict + related:
        # 同一个推荐商品可能由多条规则推出，只保留得分最高的依据。
        key = tuple(record["consequent"])
        if key not in merged or record["score"] > merged[key]["score"]:
            merged[key] = record

    recommendations = sorted(
        merged.values(),
        key=lambda row: (-row["score"], -row["confidence"], -row["lift"], row["consequent"]),
    )[:20]
    max_score = max((row["score"] for row in recommendations), default=1)
    for row in recommendations:
        row["width"] = round((row["score"] / max_score) * 100, 2) if max_score else 0
    return recommendations


@app.template_filter("percent")
def percent_filter(value):
    """Jinja 过滤器：小数转百分比。"""
    return format_percent(value)


@app.template_filter("items")
def items_filter(value):
    """Jinja 过滤器：项集列表转中文展示文本。"""
    return join_items(value)


@app.context_processor
def inject_team_config():
    """把 TOML 成员配置注入所有模板；只有 team 页面会展示成员内容。"""
    return {"team": load_team_config()}


@app.route("/")
def index():
    """首页：展示平台总览、运行指标和数据湖资产列表。"""
    rows = read_builtin_transactions()
    return render_template("index.html", algorithms=ALGORITHMS, stats=dataset_stats(rows), datasets=dataset_library())


@app.route("/team")
def team_page():
    """项目档案页：集中展示成员配置、分工和项目进度。"""
    return render_template("team.html")


@app.route("/history")
def history_page():
    """实验历史中心：同时展示浏览器本地历史和服务器后端记录。"""
    return render_template("history.html", server_runs=list_run_records())


@app.route("/history/<run_id>")
def run_record_page(run_id):
    """后端实验记录详情页：读取 JSON 记录并复用结果页模板展示。"""
    record = load_run_record(run_id)
    if not record:
        abort(404)
    return render_result_from_record(record)


@app.route("/compare")
def compare_page():
    """算法对比页：同一数据湖资产下运行三种算法并展示基准结果。"""
    dataset_id = request.args.get("dataset", DEFAULT_DATASET_ID)
    dataset = DATASETS.get(dataset_id, DATASETS[DEFAULT_DATASET_ID])
    dataset_id = next((key for key, value in DATASETS.items() if value == dataset), DEFAULT_DATASET_ID)
    min_support = parse_threshold(request.args.get("min_support"), dataset["recommended_support"])
    min_confidence = parse_threshold(request.args.get("min_confidence"), dataset["recommended_confidence"])
    max_transactions = clamp_int(request.args.get("max_transactions"), 300)
    comparison = build_algorithm_comparison(dataset_id, min_support, min_confidence, max_transactions)
    return render_template(
        "compare.html",
        datasets=dataset_library(),
        selected_dataset=dataset_id,
        min_support=min_support,
        min_confidence=min_confidence,
        max_transactions=max_transactions,
        comparison=comparison,
    )


@app.route("/recommender")
def recommender_page():
    """推荐模拟器：根据用户选择的购物篮商品生成规则推荐。"""
    dataset_id = request.args.get("dataset", DEFAULT_DATASET_ID)
    dataset = DATASETS.get(dataset_id, DATASETS[DEFAULT_DATASET_ID])
    dataset_id = next((key for key, value in DATASETS.items() if value == dataset), DEFAULT_DATASET_ID)
    algorithm_key = request.args.get("algorithm", "fpgrowth")
    algorithm_key = algorithm_key if algorithm_key in ALGORITHMS else "fpgrowth"
    min_support = parse_threshold(request.args.get("min_support"), dataset["recommended_support"])
    min_confidence = parse_threshold(request.args.get("min_confidence"), dataset["recommended_confidence"])
    max_transactions = clamp_int(request.args.get("max_transactions"), 500)
    rows = read_builtin_transactions(dataset_id)
    selected_items = selected_items_from_request()
    recommendations = []
    run_summary = None

    if selected_items:
        # 只有用户选择了商品后才运行算法，避免打开页面时无意义计算。
        transactions = transaction_sets(rows[:max_transactions])
        run = run_algorithm_with_timing(algorithm_key, transactions, min_support, min_confidence)
        recommendations = build_recommendations(run["result"]["rules"], selected_items)
        run_summary = run

    return render_template(
        "recommender.html",
        algorithms=ALGORITHMS,
        datasets=dataset_library(),
        selected_dataset=dataset_id,
        selected_algorithm=algorithm_key,
        min_support=min_support,
        min_confidence=min_confidence,
        max_transactions=max_transactions,
        item_choices=dataset_item_choices(rows),
        selected_items=selected_items,
        recommendations=recommendations,
        run_summary=run_summary,
    )


@app.route("/algorithms")
def algorithms_page():
    """算法教学页：展示三种算法的可视化步骤和伪代码。"""
    return render_template("algorithms.html", code_snippets=ALGORITHM_CODE_SNIPPETS)


@app.route("/dataset")
def dataset_page():
    """数据湖页面：展示某个内置资产的画像、来源、字段和预览。"""
    dataset_id = request.args.get("dataset", DEFAULT_DATASET_ID)
    dataset = DATASETS.get(dataset_id, DATASETS[DEFAULT_DATASET_ID])
    rows = read_builtin_transactions(dataset_id)
    return render_template(
        "dataset.html",
        preview_rows=rows[:200],
        stats=dataset_stats(rows),
        dataset_info=dataset,
        selected_dataset=dataset_id,
        datasets=dataset_library(),
    )


@app.route("/experiment")
def experiment_page():
    """实验控制台：配置数据源、算法和阈值参数。"""
    rows = read_builtin_transactions()
    return render_template(
        "experiment.html",
        algorithms=ALGORITHMS,
        stats=dataset_stats(rows),
        dataset_info=DATASETS[DEFAULT_DATASET_ID],
        datasets=dataset_library(),
    )


@app.route("/preview_dataset", methods=["POST"])
def preview_dataset():
    """实验页异步接口：预览并校验用户选择的数据湖资产。"""
    try:
        rows, dataset_label = rows_from_request()
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify(preview_payload(rows, dataset_label))


@app.route("/run", methods=["POST"])
def run_algorithm():
    """运行挖掘任务，并把完整结果渲染到结果页。"""
    algorithm_key = request.form.get("algorithm", "apriori")
    min_support = parse_threshold(request.form.get("min_support"), 0.06)
    min_confidence = parse_threshold(request.form.get("min_confidence"), 0.5)
    compare_algorithms = request.form.get("compare_algorithms") == "on"
    compare_datasets = request.form.get("compare_datasets") == "on"
    sweep_thresholds = request.form.get("sweep_thresholds") == "on"

    selected = ALGORITHMS.get(algorithm_key, ALGORITHMS["apriori"])
    algorithm_key = next((key for key, value in ALGORITHMS.items() if value == selected), "apriori")

    try:
        # 统一读取内置、上传或本机路径数据，并套用交易数量限制。
        rows, dataset_label = rows_from_request()
        rows, limit_note = apply_transaction_limit(rows)
    except ValueError as exc:
        builtin_rows = read_builtin_transactions()
        return render_template(
            "experiment.html",
            algorithms=ALGORITHMS,
            stats=dataset_stats(builtin_rows),
            dataset_info=DATASETS[DEFAULT_DATASET_ID],
            datasets=dataset_library(),
            error=str(exc),
        )

    transactions = transaction_sets(rows)
    try:
        max_transactions = int(request.form.get("max_transactions", "300"))
    except ValueError:
        max_transactions = 300
    max_transactions = min(max(max_transactions, 20), 2000)
    history_dataset_id = request.form.get("builtin_dataset", DEFAULT_DATASET_ID) if request.form.get("dataset_mode", "builtin") == "builtin" else ""
    run_keys = list(ALGORITHMS.keys()) if compare_algorithms else [algorithm_key]
    # 如果勾选三算法对比，则一次请求内运行全部算法；否则只运行当前算法。
    run_results = {
        key: run_algorithm_with_timing(key, transactions, min_support, min_confidence)
        for key in run_keys
    }

    selected_run = run_results[algorithm_key]
    result = selected_run["result"]
    # 结果页需要表格、图表、自动分析、过程阶段等多种派生数据。
    analysis = build_analysis(result["frequent_itemsets"], result["rules"])
    result_visuals = build_result_visuals(result["frequent_itemsets"], result["rules"])
    run_stages = build_run_stages(algorithm_key, result["process_logs"], result["frequent_itemsets"], result["rules"])
    dataset_comparison = run_dataset_comparison(algorithm_key, min_support, min_confidence, max_transactions) if compare_datasets else []
    threshold_sweep = run_threshold_sweep(algorithm_key, transactions, min_confidence) if sweep_thresholds else []
    parameter_grid = run_parameter_grid(algorithm_key, transactions) if sweep_thresholds else {}
    grid_analysis = build_grid_analysis(parameter_grid)
    process_logs = list(result["process_logs"])
    if limit_note:
        process_logs.insert(0, limit_note)
    if parameter_grid:
        process_logs.append(
            f"参数网格扫描采用交互演示模式：使用前 {parameter_grid['sample_size']} 条交易，"
            f"扫描 {len(parameter_grid['cells'])} 组 support × confidence 组合。"
        )
    run_id = uuid4().hex[:12]
    created_at = utc_timestamp()
    stats = dataset_stats(rows)
    comparison = summarize_algorithm_runs(run_results) if compare_algorithms else []
    process_logs.append(f"后端实验记录已保存为 run_id={run_id}，可在实验历史中心长期查看。")
    run_record = build_run_record(
        run_id=run_id,
        created_at=created_at,
        algorithm_key=algorithm_key,
        selected_run=selected_run,
        dataset_label=dataset_label,
        history_dataset_id=history_dataset_id,
        max_transactions=max_transactions,
        min_support=min_support,
        min_confidence=min_confidence,
        stats=stats,
        result=result,
        process_logs=process_logs,
        analysis=analysis,
        result_visuals=result_visuals,
        run_stages=run_stages,
        comparison=comparison,
        dataset_comparison=dataset_comparison,
        threshold_sweep=threshold_sweep,
        parameter_grid=parameter_grid,
        grid_analysis=grid_analysis,
    )
    save_run_record(run_record)

    return render_template(
        "result.html",
        run_id=run_id,
        server_record=False,
        created_at=created_at,
        algorithm_key=algorithm_key,
        algorithm_name=selected_run["name"],
        algorithm_tagline=selected_run["tagline"],
        elapsed_ms=selected_run["elapsed_ms"],
        min_support=min_support,
        min_confidence=min_confidence,
        frequent_itemsets=result["frequent_itemsets"],
        rules=result["rules"],
        process_logs=process_logs,
        analysis=analysis,
        stats=stats,
        dataset_label=dataset_label,
        history_dataset_id=history_dataset_id,
        max_transactions=max_transactions,
        comparison=comparison,
        result_visuals=result_visuals,
        run_stages=run_stages,
        dataset_comparison=dataset_comparison,
        threshold_sweep=threshold_sweep,
        parameter_grid=parameter_grid,
        grid_analysis=grid_analysis,
    )


if __name__ == "__main__":
    app.run(debug=True)
