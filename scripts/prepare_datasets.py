"""真实数据湖资产转换脚本。

这个脚本把下载的公开数据源统一转换为课程网站使用的购物篮格式：
transaction_id,items

输出文件写入 data/datasets/，Flask 应用直接读取这些转换后的 CSV。
"""

import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
DATASET_DIR = BASE_DIR / "data" / "datasets"
UCI_ZIP = BASE_DIR / "data" / "online_retail.zip"
LEGACY_DATASET = BASE_DIR / "data" / "transactions.csv"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def clean_item(value):
    """清洗商品名称，合并多余空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def write_baskets(path, baskets):
    """把交易篮写成 transaction_id,items CSV，并返回交易数和商品数。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    # 每个交易只保留唯一商品；少于 2 个商品的交易无法产生关联规则，直接过滤。
    rows = [(transaction_id, sorted(set(items))) for transaction_id, items in baskets if len(set(items)) >= 2]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["transaction_id", "items"])
        for transaction_id, items in rows:
            writer.writerow([transaction_id, ",".join(items)])
    return len(rows), len({item for _, items in rows for item in items})


def convert_plain_baskets(source, target, prefix):
    """转换每行一个购物篮的 CSV，例如 groceries.csv。"""
    baskets = []
    with source.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        for index, row in enumerate(reader, start=1):
            items = [clean_item(item) for item in row if clean_item(item)]
            baskets.append((f"{prefix}-{index:05d}", items))
    return write_baskets(target, baskets)


def convert_breadbasket(source, target):
    """转换 BreadBasket_DMS 明细表，按 Transaction 聚合为购物篮。"""
    grouped = defaultdict(list)
    with source.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            transaction_id = clean_item(row.get("Transaction"))
            item = clean_item(row.get("Item"))
            if not transaction_id or not item or item.upper() == "NONE":
                continue
            grouped[transaction_id].append(item)
    return write_baskets(target, [(f"BREAD-{tid}", items) for tid, items in grouped.items()])


def load_shared_strings(zf):
    """读取 xlsx 中的 sharedStrings.xml，供单元格值索引解析。"""
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    strings = []
    with zf.open("xl/sharedStrings.xml") as file:
        for _, elem in ET.iterparse(file, events=("end",)):
            if elem.tag == NS + "si":
                strings.append("".join(t.text or "" for t in elem.iter(NS + "t")))
                elem.clear()
    return strings


def cell_value(cell, shared_strings):
    """解析 xlsx 单元格文本，兼容共享字符串和内联字符串。"""
    cell_type = cell.attrib.get("t")
    value_elem = cell.find(NS + "v")
    if cell_type == "inlineStr":
        return "".join(t.text or "" for t in cell.iter(NS + "t"))
    if value_elem is None or value_elem.text is None:
        return ""
    raw = value_elem.text
    if cell_type == "s":
        return shared_strings[int(raw)]
    return raw


def column_name(ref):
    """从 Excel 单元格坐标中提取列名，例如 C12 -> C。"""
    match = re.match(r"([A-Z]+)", ref or "")
    return match.group(1) if match else ""


def convert_uci_countries(countries):
    """从 UCI Online Retail xlsx 中抽取指定国家的正向订单购物篮。"""
    with zipfile.ZipFile(UCI_ZIP) as outer:
        xlsx_name = next(name for name in outer.namelist() if name.lower().endswith(".xlsx"))
        xlsx_bytes = io.BytesIO(outer.read(xlsx_name))

    country_baskets = {country: defaultdict(set) for country in countries}
    positive_rows = Counter()

    with zipfile.ZipFile(xlsx_bytes) as zf:
        shared_strings = load_shared_strings(zf)
        sheet_name = next(name for name in zf.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"))

        with zf.open(sheet_name) as file:
            header_seen = False
            for _, elem in ET.iterparse(file, events=("end",)):
                if elem.tag != NS + "row":
                    continue
                values = {
                    column_name(cell.attrib.get("r")): cell_value(cell, shared_strings).strip()
                    for cell in elem.findall(NS + "c")
                }
                if not header_seen:
                    # 第一行是表头，跳过后续按固定列读取 Invoice/Description/Quantity/Country。
                    header_seen = True
                    elem.clear()
                    continue

                invoice = values.get("A", "")
                description = clean_item(values.get("C", "")).upper()
                country = values.get("H", "")
                try:
                    quantity = float(values.get("D", "0"))
                except ValueError:
                    quantity = 0

                if country not in countries:
                    elem.clear()
                    continue
                # 过滤取消订单、非正数量、空描述和非商品费用项。
                if not invoice or invoice.upper().startswith("C") or quantity <= 0 or not description:
                    elem.clear()
                    continue
                if any(skip in description for skip in ("POSTAGE", "MANUAL", "DISCOUNT", "BANK CHARGES", "DOTCOM")):
                    elem.clear()
                    continue

                country_baskets[country][invoice].add(description)
                positive_rows[country] += 1
                elem.clear()

    results = {}
    for country, baskets in country_baskets.items():
        item_counts = Counter(item for items in baskets.values() for item in items)
        # 控制资产规模，保证课堂演示时三个算法都能快速跑完。
        top_limit = 80 if country != "United Kingdom" else 100
        transaction_limit = 360 if country != "United Kingdom" else 500
        top_items = {item for item, _ in item_counts.most_common(top_limit)}
        filtered = []
        for invoice, items in sorted(baskets.items()):
            selected = [item for item in items if item in top_items]
            if len(selected) >= 2:
                filtered.append((f"UCI-{country.upper().replace(' ', '-')}-{invoice}", selected))
        filtered = filtered[:transaction_limit]
        filename = f"uci_online_retail_{country.lower().replace(' ', '_')}.csv"
        results[country] = {
            "rows": positive_rows[country],
            "transactions": write_baskets(DATASET_DIR / filename, filtered),
        }

    return results


def main():
    """执行所有数据转换任务。"""
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    results["groceries"] = convert_plain_baskets(
        RAW_DIR / "groceries.csv",
        DATASET_DIR / "groceries.csv",
        "GROCERY",
    )
    results["market_basket_grocery"] = convert_plain_baskets(
        RAW_DIR / "Market_Basket_Data.csv",
        DATASET_DIR / "market_basket_grocery.csv",
        "MARKET",
    )
    results["bread_basket"] = convert_breadbasket(
        RAW_DIR / "BreadBasket_DMS.csv",
        DATASET_DIR / "bread_basket.csv",
    )
    uci_results = convert_uci_countries(["France", "Germany", "EIRE", "United Kingdom"])

    # 课程原始要求固定存在 data/transactions.csv，这里保持它指向真实 France 子集。
    france_path = DATASET_DIR / "uci_online_retail_france.csv"
    if france_path.exists():
        LEGACY_DATASET.write_text(france_path.read_text(encoding="utf-8-sig"), encoding="utf-8")

    print("converted:")
    for name, value in results.items():
        print(name, value)
    print("uci:")
    for name, value in uci_results.items():
        print(name, value)


if __name__ == "__main__":
    main()
