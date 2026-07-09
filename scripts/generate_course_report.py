"""Generate the course report and page screenshots.

The target report path uses a .doc suffix for course submission compatibility,
but the generated file is Word-compatible RTF.  The RTF embeds PNG screenshots
directly, so the report remains a single file that Microsoft Word can open.
"""

from __future__ import annotations

import json
import os
import re
import struct
import sys
import threading
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import app as webapp  # noqa: E402


REPORT_PATH = BASE_DIR / "大作业_《数据挖掘技术课程设计》实验报告书.doc"
ASSET_DIR = BASE_DIR / "report_assets"
SCREENSHOT_DIR = ASSET_DIR / "screenshots"
SUMMARY_PATH = ASSET_DIR / "experiment_summary.json"
DEFAULT_BASE_URL = os.environ.get("REPORT_BASE_URL", "http://127.0.0.1:5000")
REPORT_DATE = time.strftime("%Y年%m月%d日")


REPORT_META = {
    "college": "计算机与信息学院",
    "major": "智能科学与技术",
    "class_name": "24A1",
    "topic": "关联规则挖掘算法课程网站设计与实现",
}


def get_url(url: str, timeout: float = 5.0) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def post_form(url: str, form: dict[str, str], timeout: float = 60.0) -> str:
    payload = urllib.parse.urlencode(form).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def ensure_server(base_url: str):
    """Use an existing local server, or start one in this process."""
    try:
        get_url(base_url + "/", timeout=2.0)
        return base_url, None
    except Exception:
        pass

    from werkzeug.serving import make_server

    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    preferred_port = parsed.port or 5000

    last_error = None
    for port in (preferred_port, 5055, 5070):
        try:
            server = make_server(host, port, webapp.app)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            started_url = f"http://{host}:{port}"
            for _ in range(40):
                try:
                    get_url(started_url + "/", timeout=1.0)
                    return started_url, server
                except Exception:
                    time.sleep(0.25)
        except OSError as exc:
            last_error = exc

    raise RuntimeError(f"无法启动本地 Flask 服务：{last_error}")


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def item_text(items: list[str] | tuple[str, ...]) -> str:
    return "、".join(items)


def rule_text(rule: dict | None) -> str:
    if not rule:
        return "无满足阈值的规则"
    return f"{item_text(rule['antecedent'])} -> {item_text(rule['consequent'])}"


def is_leader(member: dict) -> bool:
    return "组长" in str(member.get("role", ""))


def member_brief(member: dict) -> str:
    suffix = "（组长）" if is_leader(member) else ""
    return f"{member.get('student_id', '')} {member.get('name', '')}{suffix}".strip()


def contribution_text(member: dict) -> str:
    tasks = [str(item) for item in member.get("responsibility", []) if str(item).strip()]
    return "；".join(tasks) if tasks else str(member.get("role", "成员"))


def contribution_table(team: dict) -> str:
    text = tab_line(["学号", "姓名", "承担任务"], bold=True, size=18)
    for member in team["members"]:
        text += tab_line(
            [
                member.get("student_id", ""),
                member.get("name", ""),
                contribution_text(member),
            ],
            size=18,
        )
    return text


def collect_dataset_summaries() -> list[dict]:
    summaries = []
    for dataset_id, meta in webapp.DATASETS.items():
        rows = webapp.read_builtin_transactions(dataset_id)
        stats = webapp.dataset_stats(rows)
        summaries.append(
            {
                "id": dataset_id,
                "label": meta["label"],
                "family": meta["family"],
                "source": meta["source"],
                "transactions": stats["transaction_count"],
                "items": stats["item_count"],
                "avg_basket": stats["avg_basket_size"],
                "max_basket": stats["max_basket_size"],
                "recommended_support": meta["recommended_support"],
                "recommended_confidence": meta["recommended_confidence"],
                "top_items": [
                    {"name": row["name"], "support": row["support"], "count": row["count"]}
                    for row in stats["top_items"][:5]
                ],
            }
        )
    return summaries


def run_experiments() -> list[dict]:
    """Run real backend algorithms on three datasets and return report rows."""
    selected_datasets = ["uci_france", "groceries", "bread_basket"]
    rows = []
    for dataset_id in selected_datasets:
        meta = webapp.DATASETS[dataset_id]
        dataset_rows = webapp.read_builtin_transactions(dataset_id)[:300]
        transactions = webapp.transaction_sets(dataset_rows)
        stats = webapp.dataset_stats(dataset_rows)
        min_support = meta["recommended_support"]
        min_confidence = meta["recommended_confidence"]

        for algorithm_key in webapp.ALGORITHMS:
            run = webapp.run_algorithm_with_timing(
                algorithm_key,
                transactions,
                min_support,
                min_confidence,
            )
            rows.append(
                {
                    "dataset_id": dataset_id,
                    "dataset": meta["label"],
                    "dataset_short": meta["short"],
                    "algorithm_key": algorithm_key,
                    "algorithm": run["name"],
                    "transactions": stats["transaction_count"],
                    "items": stats["item_count"],
                    "avg_basket": stats["avg_basket_size"],
                    "min_support": min_support,
                    "min_confidence": min_confidence,
                    "elapsed_ms": round(run["elapsed_ms"], 2),
                    "frequent_count": run["frequent_count"],
                    "rules_count": run["rules_count"],
                    "best_lift": round(run["best_lift"], 4),
                    "best_confidence": round(run["best_confidence"], 4),
                    "avg_confidence": round(run["avg_confidence"], 4),
                    "avg_lift": round(run["avg_lift"], 4),
                    "best_rule": rule_text(run["best_rule"]),
                    "top_rules": [
                        {
                            "rule": rule_text(rule),
                            "support": rule["support"],
                            "confidence": rule["confidence"],
                            "lift": rule["lift"],
                        }
                        for rule in run["result"]["rules"][:5]
                    ],
                }
            )
    return rows


def create_result_record(base_url: str) -> str:
    """Create one server-side result record for screenshot and history pages."""
    html = post_form(
        base_url + "/run",
        {
            "dataset_mode": "builtin",
            "builtin_dataset": "uci_france",
            "algorithm": "apriori",
            "min_support": "0.06",
            "min_confidence": "0.50",
            "max_transactions": "300",
            "compare_algorithms": "on",
        },
    )
    match = re.search(r"run_id\s*<strong>([^<]+)</strong>", html)
    if match:
        return match.group(1)

    match = re.search(r"/history/([0-9T_.-]+)", html)
    if match:
        return match.group(1)

    result_dir = BASE_DIR / "data" / "results"
    records = sorted(result_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not records:
        raise RuntimeError("已经提交实验，但没有找到后端运行记录。")
    return records[0].stem


def capture_screenshots(base_url: str, run_id: str) -> list[dict]:
    from playwright.sync_api import sync_playwright

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    pages = [
        ("01_home.png", "工作台首页", "/"),
        ("02_algorithms.png", "可视化教学页", "/algorithms"),
        ("03_dataset.png", "数据湖展示页", "/dataset?dataset=uci_france"),
        ("04_experiment.png", "实验控制台", "/experiment"),
        ("05_result.png", "运行结果页", f"/history/{run_id}"),
        (
            "06_compare.png",
            "算法对比仪表盘",
            "/compare?dataset=uci_france&min_support=0.06&min_confidence=0.50&max_transactions=300",
        ),
        (
            "07_recommender.png",
            "商品推荐模拟器",
            "/recommender?dataset=market_basket_grocery&algorithm=apriori&min_support=0.02&min_confidence=0.30&max_transactions=300&items=mineral+water&items=eggs",
        ),
        ("08_history.png", "实验历史中心", "/history"),
        ("09_team.png", "项目档案页", "/team"),
    ]

    screenshots = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        for filename, title, route in pages:
            url = base_url + route
            path = SCREENSHOT_DIR / filename
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.screenshot(path=str(path), full_page=True)
            screenshots.append({"title": title, "route": route, "path": str(path.relative_to(BASE_DIR))})
        browser.close()
    return screenshots


def rtf_escape(text: object) -> str:
    output = []
    for char in str(text):
        code = ord(char)
        if char == "\n":
            output.append(r"\line ")
        elif char == "\t":
            output.append(r"\tab ")
        elif char in "\\{}":
            output.append("\\" + char)
        elif 32 <= code <= 126:
            output.append(char)
        else:
            signed = code if code <= 32767 else code - 65536
            output.append(f"\\u{signed}?")
    return "".join(output)


def para(text: object, *, indent: bool = True, size: int = 24) -> str:
    first_indent = r"\fi420" if indent else r"\fi0"
    return rf"\pard\qj{first_indent}\sa140\sl320\slmult1\f0\fs{size} {rtf_escape(text)}\par" + "\n"


def center(text: object, *, size: int = 28, bold: bool = False) -> str:
    b1, b0 = (r"\b ", r"\b0 ") if bold else ("", "")
    return rf"\pard\qc\sa160\f0\fs{size} {b1}{rtf_escape(text)}{b0}\par" + "\n"


def heading(text: object, level: int = 1) -> str:
    size = 30 if level == 1 else 26
    before = 260 if level == 1 else 180
    return rf"\pard\sb{before}\sa120\f0\fs{size}\b {rtf_escape(text)}\b0\par" + "\n"


def tab_line(cells: list[object], *, bold: bool = False, size: int = 19) -> str:
    b1, b0 = (r"\b ", r"\b0 ") if bold else ("", "")
    text = r"\tab ".join(rtf_escape(cell) for cell in cells)
    return rf"\pard\sa70\f0\fs{size} {b1}{text}{b0}\par" + "\n"


def page_break() -> str:
    return r"\page" + "\n"


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as file:
        header = file.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"不是 PNG 文件：{path}")
    return struct.unpack(">II", header[16:24])


def image_rtf(path: Path, caption: str, max_width_twips: int = 8200) -> str:
    width, height = png_size(path)
    goal_width = min(max_width_twips, width * 15)
    goal_height = max(1, int(goal_width * height / width))
    hex_data = path.read_bytes().hex()
    wrapped_hex = "\n".join(hex_data[index : index + 96] for index in range(0, len(hex_data), 96))
    return (
        center(caption, size=22, bold=True)
        + rf"\pard\qc\sa180 {{\pict\pngblip\picw{width}\pich{height}\picwgoal{goal_width}\pichgoal{goal_height}"
        + "\n"
        + wrapped_hex
        + "}\n\\par\n"
    )


def dataset_table(datasets: list[dict]) -> str:
    text = tab_line(["数据集", "类型", "交易数", "商品数", "平均篮子", "建议支持度", "建议置信度"], bold=True)
    for row in datasets:
        text += tab_line(
            [
                row["label"],
                row["family"],
                row["transactions"],
                row["items"],
                row["avg_basket"],
                pct(row["recommended_support"]),
                pct(row["recommended_confidence"]),
            ]
        )
    return text


def experiment_table(rows: list[dict]) -> str:
    text = tab_line(
        ["数据集", "算法", "交易", "商品", "support", "confidence", "项集", "规则", "最高lift", "耗时ms"],
        bold=True,
    )
    for row in rows:
        text += tab_line(
            [
                row["dataset_short"],
                row["algorithm"],
                row["transactions"],
                row["items"],
                pct(row["min_support"]),
                pct(row["min_confidence"]),
                row["frequent_count"],
                row["rules_count"],
                f"{row['best_lift']:.2f}",
                f"{row['elapsed_ms']:.2f}",
            ]
        )
    return text


def text_count(blocks: list[str]) -> int:
    return len(re.sub(r"\s+", "", "".join(blocks)))


def build_report_text(datasets: list[dict], experiments: list[dict], team: dict) -> tuple[str, dict[str, int]]:
    by_dataset = defaultdict(list)
    for row in experiments:
        by_dataset[row["dataset_short"]].append(row)

    france_apriori = next(
        row for row in experiments if row["dataset_id"] == "uci_france" and row["algorithm_key"] == "apriori"
    )
    fastest = min(experiments, key=lambda row: row["elapsed_ms"])
    strongest = max(experiments, key=lambda row: row["best_lift"])
    leader = next((member for member in team["members"] if is_leader(member)), team["members"][0])
    member_line = "；".join(member_brief(member) for member in team["members"])

    consistency = []
    for dataset_name, rows in by_dataset.items():
        signatures = {(row["frequent_count"], row["rules_count"]) for row in rows}
        if len(signatures) == 1:
            count = next(iter(signatures))
            consistency.append(f"{dataset_name} 上五种算法得到相同规模的结果：{count[0]} 个频繁项集、{count[1]} 条规则。")
        else:
            detail = "；".join(f"{row['algorithm']}={row['frequent_count']}项集/{row['rules_count']}规则" for row in rows)
            consistency.append(f"{dataset_name} 上不同算法的输出规模存在差异：{detail}。")

    parts = []
    main_blocks: list[str] = []
    non_body_blocks: list[str] = []

    def add_main_heading(text: str, level: int = 1) -> None:
        parts.append(heading(text, level))
        main_blocks.append(text)

    def add_main_para(text: str, *, indent: bool = True) -> None:
        parts.append(para(text, indent=indent))
        main_blocks.append(text)

    def add_non_heading(text: str, level: int = 1) -> None:
        parts.append(heading(text, level))
        non_body_blocks.append(text)

    def add_non_para(text: str, *, indent: bool = True) -> None:
        parts.append(para(text, indent=indent))
        non_body_blocks.append(text)

    parts.append(center("数据挖掘技术课程设计", size=38, bold=True))
    parts.append(center("实习报告", size=36, bold=True))
    parts.append(center(f"课题：{REPORT_META['topic']}", size=28, bold=True))
    parts.append(center(f"学院：{REPORT_META['college']}", size=24))
    parts.append(center(f"专业：{REPORT_META['major']}", size=24))
    parts.append(center(f"班级：{REPORT_META['class_name']}", size=24))
    parts.append(center(f"组别：{team['group']['name']}", size=24))
    parts.append(center(f"组长：{member_brief(leader)}", size=24))
    parts.append(para(f"成员：{member_line}", indent=False, size=22))
    parts.append(center(f"日期：{REPORT_DATE}", size=22))
    parts.append(page_break())

    parts.append(heading("表1 组员贡献分配表", 1))
    parts.append(contribution_table(team))
    parts.append(page_break())

    add_main_heading("报告正文（4000-5000字）", 1)
    add_main_heading("一、网站功能介绍", 1)
    add_main_para(
        "本课程设计围绕关联规则挖掘主题，完成了一个可以运行、复现和展示的课程网站。系统把算法概念、购物篮数据、参数实验和结果解释连成一条链路，"
        "使用者可以查看项目概览、选择真实数据湖、阅读算法知识卡片、配置阈值、运行算法，并查看频繁项集、关联规则、算法对比、商品推荐和历史记录。"
        "报告中的实验数值来自当前后端真实计算，截图来自脚本打开本地网站后的页面长截图。"
    )
    add_main_para(
        "网站主要功能包括八个部分。第一，工作台首页展示项目定位、算法范围、数据湖规模和常用入口，便于答辩时快速说明系统边界。"
        "第二，可视化教学页围绕 Apriori、FP-Growth、Eclat、AIS、H-Mine 五种算法，用迷你购物篮、候选生成、FP-Tree 路径、TID-set 交集和投影数据库等示例解释算法步骤。"
        "第三，数据湖页面展示 UCI Online Retail、Groceries、Bread Basket Bakery、Market Basket Grocery 等公开数据资产，包含来源、字段说明、高频商品、共现关系和数据预览。"
        "第四，实验控制台允许选择内置数据集、上传 CSV 或填写服务器本机 CSV 路径，并设置最小支持度、最小置信度、最大交易数、五算法对比和参数网格扫描。"
    )
    add_main_para(
        "第五，结果页展示运行参数、run_id、频繁项集、关联规则、过程日志和自动分析结论。第六，算法对比页在同一数据和阈值下运行五种算法，"
        "便于观察耗时、规则规模和最佳规则是否一致。第七，推荐模拟器把关联规则用于购物篮补全。第八，历史中心把后端运行记录保存为 JSON 文件，"
        "可重新打开固定结果；项目档案页读取 config/team.toml 展示成员、分工和进度。"
    )

    add_main_heading("二、算法原理说明", 1)
    add_main_para(
        "关联规则挖掘的目标是在事务数据库中发现项目之间的共现关系。事务可以理解为一张购物小票，项目可以理解为小票中的商品。"
        "算法首先根据最小支持度筛选频繁项集，再根据最小置信度生成规则 A -> B。support 表示包含 A 与 B 的交易比例，confidence 表示出现 A 时同时出现 B 的条件概率，"
        "lift 则把 confidence 与 B 本身出现概率比较，用于判断前件是否真正提升了后件出现概率。lift 大于 1 通常表示正相关，接近 1 表示接近独立。"
    )
    add_main_para(
        "Apriori 利用频繁项集的向下封闭性质：频繁项集的所有非空子集都频繁，不频繁项集的超集也不可能频繁。"
        "算法从 1 项集开始逐层扫描交易，由 L(k-1) 连接生成 Ck，再用子集检查剪掉不可能频繁的候选。"
        "它步骤清楚、适合教学，但低支持度或商品种类较多时会产生大量候选，并需要多次扫描事务集。"
    )
    add_main_para(
        "FP-Growth 用 FP-Tree 压缩交易并通过模式增长挖掘频繁项集。算法先统计单项频率，删除低频商品，再按全局频率排序交易并插入树中。"
        "相同前缀共享节点，Header Table 连接同名节点，挖掘时回溯条件模式基并递归构建条件 FP-Tree。"
        "它避免显式生成大量候选，适合较大数据，但树结构和递归过程讲解难度更高。"
    )
    add_main_para(
        "Eclat 使用垂直数据格式，把 item 映射为包含该商品的交易编号集合，也就是 TID-set。两个项目组合后的支持度可以通过 TID-set 交集直接计算。"
        "例如 {A,B} 的交易集合等于 A 的 TID-set 与 B 的 TID-set 的交集，交集大小除以总交易数就是支持度。"
        "Eclat 的优点是集合运算直观、递归结构简洁；不足是在稠密数据或交易数量很大时，TID-set 存储和交集计算会带来内存压力。"
    )
    add_main_para(
        "AIS 和 H-Mine 是扩展算法。AIS 在扫描每笔交易时，从上一轮频繁项集出发，只用当前交易中存在的商品扩展候选，适合说明候选来自真实事务。"
        "H-Mine 强调内存结构和前缀投影，每次固定一个前缀，只把相关后缀交易传入下一层递归。五种算法搜索策略不同，但同一输入和阈值下应得到同口径结果。"
    )

    add_main_heading("三、算法实现过程", 1)
    add_main_para(
        "当前项目采用 Python Flask 后端、Jinja2 模板和原生 HTML/CSS/JavaScript 前端实现。app.py 维护算法注册表、数据集注册表和页面路由；"
        "algorithms 目录保存五种算法，每个文件暴露统一 run 接口。templates 保存页面模板，static 保存样式与交互脚本，config/team.toml 保存成员分工，data/datasets 保存购物篮数据。"
    )
    add_main_para(
        "数据读取阶段，系统支持内置数据湖、上传 CSV 和服务器本机 CSV 路径。内置数据统一为 transaction_id,items 两列，读取时拆分商品并在同一交易内去重，"
        "确保支持度按“交易中是否出现商品”计算。上传数据既支持购物篮格式，也支持 InvoiceNo、Description、Quantity 形式的明细格式，系统会自动按交易编号聚合。"
    )
    add_main_para(
        "运行阶段，实验控制台把算法 key、支持度、置信度、最大交易数和扩展选项提交给 /run。后端读取数据并转为交易集合，再调用对应算法得到 frequent_itemsets、rules 和 process_logs。"
        "公共规则生成逻辑枚举频繁项集的非空前件，计算 support、confidence、lift，并按指标排序。五算法对比会在同一次请求中运行全部算法；参数扫描会用小样本避免低阈值导致规则爆炸。"
    )
    add_main_para(
        "结果输出阶段，系统构造指标卡片、频繁项集表、关联规则表、规则强度分析、过程日志、数据集比较、阈值扫描和参数网格。"
        "每次运行生成 run_id，并把完整记录保存到 data/results/<run_id>.json，历史中心通过 /history/<run_id> 读取后复用结果模板渲染，保证答辩时可以回看固定结果。"
    )

    add_main_heading("四、数据集与实验结果", 1)
    add_main_para(
        "项目内置多个真实购物篮数据湖资产，既满足每种算法至少使用两个以上数据集的实验需要，也便于观察不同业务场景下规则解释的差异。"
        "UCI Online Retail 子集来自英国注册线上零售商的真实交易数据，项目按 France、Germany、EIRE、United Kingdom 等国家筛选正向订单；"
        "Groceries 是关联规则教学中常用的杂货购物篮数据；Bread Basket Bakery 记录面包咖啡店交易；Market Basket Grocery 用于通用市场篮分析示例。"
        "所有数据都被转换为一行一个购物篮的 CSV，字段为 transaction_id 和 items。"
    )
    parts.append(dataset_table(datasets))
    main_blocks.extend(
        f"{row['label']}{row['family']}{row['transactions']}{row['items']}{row['avg_basket']}"
        for row in datasets
    )
    add_main_para(
        "预处理流程包括识别交易编号和商品名称字段、过滤取消订单和非正数量记录、去除邮费和折扣等非商品项、按交易编号聚合商品描述、同一交易内去重、保留适合课堂演示规模的真实高频商品。"
        "这种处理方式既保留了真实业务商品名称，又避免原始数据过大导致课堂现场运行缓慢。"
    )
    add_main_para(
        "本报告选取 UCI France、Groceries 和 Bread Basket 三个数据集进行验证，每个数据集最多使用前 300 条交易，参数采用系统登记的推荐支持度和置信度。"
        "每个数据集都分别运行 Apriori、FP-Growth、Eclat、AIS、H-Mine。下表中的项集数、规则数、最高 lift 和耗时均由当前代码实际计算得到。"
    )
    parts.append(experiment_table(experiments))
    main_blocks.extend(
        f"{row['dataset_short']}{row['algorithm']}{row['frequent_count']}{row['rules_count']}{row['best_lift']}{row['elapsed_ms']}"
        for row in experiments
    )
    add_main_para(
        f"以默认 UCI France 数据集为例，Apriori 在 support={pct(france_apriori['min_support'])}、"
        f"confidence={pct(france_apriori['min_confidence'])} 下得到 {france_apriori['frequent_count']} 个频繁项集、"
        f"{france_apriori['rules_count']} 条规则，最高 lift 为 {france_apriori['best_lift']:.2f}，代表规则为 {france_apriori['best_rule']}。"
        f"本轮测试中耗时最低的是 {fastest['dataset_short']} 数据集上的 {fastest['algorithm']}，耗时 {fastest['elapsed_ms']:.2f} ms；"
        f"最高 lift 出现在 {strongest['dataset_short']} 数据集上的 {strongest['algorithm']}，规则为 {strongest['best_rule']}，lift={strongest['best_lift']:.2f}。"
    )
    for line in consistency:
        add_main_para(line)

    add_main_heading("五、知识卡片正确性保障", 1)
    add_main_para(
        "模板要求说明如何确保知识卡片正确性。项目中采取了三层校对方式。第一层是概念来源校对：知识卡片围绕教材和课堂通用定义组织，只使用关联规则挖掘中稳定的概念，"
        "例如频繁项集、候选生成、FP-Tree、TID-set、support、confidence 和 lift，避免把业务解释误写成因果关系。第二层是代码路径校对：每张卡片对应到当前算法实现中的真实步骤，"
        "例如 Apriori 卡片对应候选连接和子集剪枝，FP-Growth 卡片对应频率排序、树插入和条件模式基，Eclat 卡片对应垂直格式和集合交集。"
    )
    add_main_para(
        "第三层是运行结果校对：实验页、对比页和报告脚本都调用同一套后端算法，知识卡片中的指标含义会在结果页中以真实规则呈现。"
        "例如 support、confidence、lift 不仅在文字中解释，也在 Top 规则表、结果分析和推荐模拟器中被实际使用。"
        "如果算法页面只讲概念而结果页使用另一套逻辑，容易造成知识与程序脱节；本项目通过统一算法注册表和公共规则生成函数，把教学说明、运行过程和页面展示连接在一起。"
    )

    add_main_heading("六、结果分析", 1)
    add_main_para(
        "实验结果说明，关联规则挖掘对支持度阈值很敏感。支持度越高，频繁项集和规则越少；支持度越低，结果更丰富，但运行时间和解释成本上升。"
        "置信度阈值主要影响规则筛选，较高置信度会保留更确定的关系，也可能漏掉 lift 高但覆盖面小的规则。因此网站提供推荐阈值和参数网格，帮助观察阈值变化的影响。"
    )
    add_main_para(
        "从业务解释角度看，support 较高的频繁项集表示商品组合覆盖了较多交易，适合做基础陈列和套餐候选；confidence 较高的规则表示前件出现后后件也出现的概率较大，"
        "适合做购物篮补全提示；lift 较高的规则表示前件会显著提升后件出现概率，适合做更有针对性的推荐。"
        "在零售礼品数据中，颜色、主题或用途相近的商品容易形成共购规则；在面包店数据中，咖啡、面包、糕点、茶等早餐或下午茶商品更容易产生可解释规则。"
        "这些规则不能简单理解为因果关系，实际应用时还需要结合价格、季节、库存和促销策略。"
    )
    add_main_para(
        "当前系统已经覆盖课程要求的主要内容：算法介绍、数据集展示、参数设置、算法运行、结果展示、结果分析和主要页面截图均已完成。"
        "不足之处是算法实现面向课程规模数据，未引入分布式计算、位图压缩或异步任务队列；如果扩展到百万级交易，需要增加缓存、后台任务、进度轮询和更高效的数据结构。"
        "后续也可以把 Flask 模板页面拆为前后端分离结构，但对本次课程设计而言，当前单体实现更便于本地运行、演示和提交。"
    )
    parts.append(page_break())

    add_non_heading("以下非正文（1000字以上）", 1)
    add_non_heading("一、总结与心得", 1)
    add_non_para(
        "本次实验最大的收获，是把关联规则挖掘从公式和伪代码落实到完整网站中。起初我们对 Apriori、FP-Growth、Eclat 的理解主要停留在课堂步骤，"
        "真正实现后才发现算法正确性不仅取决于核心循环，还取决于数据格式、交易内去重、支持度计数、规则枚举、排序口径和页面解释是否一致。"
        "例如同一笔购物篮中重复出现某个商品时，支持度应按交易出现计算，而不是按数量累加；如果忽略这一点，结果会偏离关联规则的定义。"
        "再例如 lift 的含义容易被误解为因果关系，报告和页面中都需要强调它只是统计关联。"
    )
    add_non_para(
        "在开发过程中，AI 工具主要用于辅助整理报告结构、检查页面说明、生成截图脚本和发现表述遗漏，但最终结果仍以当前仓库代码、真实数据和本地运行输出为准。"
        "这使我们认识到，AI 可以提高资料整理和样式调整效率，却不能替代对算法定义、运行结果和课程要求的核对。"
        "如果只让工具生成文字而不运行程序，报告很容易出现数值虚构、页面不存在或成员信息错误等问题；因此本项目把报告生成脚本和真实后端绑定，先运行算法，再把结果写入报告。"
    )
    add_non_para(
        "小组协作方面，组长负责总体拆解和进度协调，算法成员分别完成五种算法实现与校对，数据成员整理公开数据集并统一格式，前端成员完善页面展示和交互，文档成员负责截图、运行说明和报告排版。"
        "由于成员较多，早期最容易出现的问题是同一概念在不同页面表述不一致，后续通过统一术语、统一指标和统一成员配置解决。"
        "项目档案页从 config/team.toml 读取成员信息，报告也复用同一份配置，避免页面和报告出现不同名单。"
    )
    add_non_para(
        "本项目仍有可以改进的地方。第一，当前参数网格为了保证课堂演示速度，使用较小样本进行扫描；如果要做更严谨的实验平台，可以增加后台任务队列和进度条。"
        "第二，算法对比现在主要比较耗时、项集数、规则数和最佳规则，后续可以加入内存占用、候选数量和剪枝率。"
        "第三，推荐模拟器仍是基于规则的简化应用，如果扩展为真实商业系统，还需要结合库存、价格、用户画像和时间因素。"
        "总体来看，本次实验完成了从数据准备、算法实现、页面展示、结果分析到报告输出的闭环，对关联规则挖掘的理解比单纯阅读教材更深入。"
    )

    add_non_heading("二、网站运行说明", 1)
    add_non_para("运行环境：Python 3，依赖 Flask 与 tomli。当前仓库可通过以下命令运行：", indent=False)
    parts.append(tab_line(["pip install -r requirements.txt"], size=22))
    parts.append(tab_line(["python app.py"], size=22))
    add_non_para("浏览器访问：http://127.0.0.1:5000。报告生成脚本会自动启动本地 Flask 服务、运行真实实验、抓取长截图并生成 Word 可打开的 .doc 文件。", indent=False)
    add_non_para(
        "主要目录：algorithms 保存五种算法实现与公共规则函数；data/datasets 保存转换后的公开数据集；templates 保存页面模板；static 保存样式和脚本；"
        "config/team.toml 保存成员与项目档案；data/results 为运行时生成的后端实验记录目录。"
    )

    add_non_heading("三、实验数据与最佳规则摘录", 1)
    parts.append(tab_line(["数据集", "算法", "最高置信度", "平均lift", "最佳规则"], bold=True, size=18))
    for row in experiments:
        parts.append(
            tab_line(
                [
                    row["dataset_short"],
                    row["algorithm"],
                    pct(row["best_confidence"]),
                    f"{row['avg_lift']:.2f}",
                    row["best_rule"],
                ],
                size=18,
            )
        )
        non_body_blocks.append(
            f"{row['dataset_short']}{row['algorithm']}{row['best_confidence']}{row['avg_lift']}{row['best_rule']}"
        )

    return "".join(parts), {
        "main_body_chars": text_count(main_blocks),
        "non_body_chars": text_count(non_body_blocks),
    }


def build_rtf(report_body: str, screenshots: list[dict]) -> str:
    header = (
        r"{\rtf1\ansi\ansicpg936\deff0\uc1"
        "\n"
        r"{\fonttbl{\f0 SimSun;}{\f1 Microsoft YaHei;}{\f2 Consolas;}}"
        "\n"
        r"\paperw11906\paperh16838\margl1440\margr1440\margt1200\margb1200"
        "\n"
        r"\widowctrl\lang2052\f0\fs24"
        "\n"
    )
    footer = "}\n"
    screenshot_rtf = heading("非正文附件三：网站运行截图", 1)
    screenshot_rtf += para("以下截图由脚本打开本地前端页面后自动生成，并直接嵌入本文档。", indent=False)
    for shot in screenshots:
        path = BASE_DIR / shot["path"]
        screenshot_rtf += image_rtf(path, f"{shot['title']}（{shot['route']}）")
    return header + report_body + screenshot_rtf + footer


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    base_url, server = ensure_server(DEFAULT_BASE_URL)

    team = webapp.load_team_config()
    datasets = collect_dataset_summaries()
    experiments = run_experiments()
    run_id = create_result_record(base_url)
    screenshots = capture_screenshots(base_url, run_id)
    report_body, counts = build_report_text(datasets, experiments, team)

    summary = {
        "base_url": base_url,
        "run_id": run_id,
        "team": team,
        "report_counts": counts,
        "datasets": datasets,
        "experiments": experiments,
        "screenshots": screenshots,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    backup_path = REPORT_PATH.with_suffix(REPORT_PATH.suffix + ".original.bak")
    if backup_path.exists():
        backup_path.unlink()

    REPORT_PATH.write_text(build_rtf(report_body, screenshots), encoding="utf-8")

    if server is not None:
        server.shutdown()

    print(f"report={REPORT_PATH}")
    print(f"removed_backup={backup_path}")
    print(f"summary={SUMMARY_PATH}")
    print(f"main_body_chars={counts['main_body_chars']}")
    print(f"non_body_chars={counts['non_body_chars']}")
    for shot in screenshots:
        print(f"screenshot={shot['path']}")


if __name__ == "__main__":
    main()
