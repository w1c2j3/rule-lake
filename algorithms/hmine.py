"""H-Mine 风格的投影数据库频繁项集挖掘实现。

实现使用内存投影列表表达 H-Struct 的核心行为：每次固定一个前缀，
只把该项之后的后缀交易传入下一层递归，避免生成全局候选集合。
"""

from collections import Counter

from . import generate_association_rules, min_support_count, to_itemset_records


def run(transactions, min_support=0.3, min_confidence=0.6):
    """运行 H-Mine，并返回统一的频繁项集、规则和过程日志结构。"""
    total = len(transactions)
    threshold_count = min_support_count(min_support, total)
    frequent_supports = {}
    state = {"projections": 0, "max_depth": 0}
    process_logs = [
        f"读取到 {total} 条交易记录，H-Mine 最小支持度计数为 {threshold_count}。",
        "H-Mine 构建内存 H-Struct，并按前缀递归投影相关交易。",
    ]

    def mine(projected_db, prefix):
        counts = Counter(item for transaction in projected_db for item in set(transaction))
        frequent_items = sorted(
            (item for item, count in counts.items() if count >= threshold_count),
            key=lambda item: (counts[item], item),
        )
        state["max_depth"] = max(state["max_depth"], len(prefix) + bool(frequent_items))

        for index, item in enumerate(frequent_items):
            pattern = prefix | {item}
            frequent_supports[frozenset(pattern)] = counts[item] / total
            allowed_suffix = set(frequent_items[index + 1 :])
            next_db = []
            for transaction in projected_db:
                if item not in transaction:
                    continue
                suffix = set(transaction) & allowed_suffix
                if suffix:
                    next_db.append(suffix)
            if next_db:
                state["projections"] += 1
                mine(next_db, pattern)

    normalized = [set(transaction) for transaction in transactions]
    unique_items = {item for transaction in normalized for item in transaction}
    process_logs.append(f"H-Struct 构建完成：连接 {len(normalized)} 条交易中的 {len(unique_items)} 类商品。")
    mine(normalized, set())
    process_logs.append(
        f"H-Mine 投影挖掘完成：执行 {state['projections']} 次数据库投影，"
        f"最大递归深度 {state['max_depth']}，得到频繁项集 {len(frequent_supports)} 个。"
    )

    rules = generate_association_rules(frequent_supports, min_confidence)
    process_logs.append(f"基于 H-Mine 频繁项集生成关联规则 {len(rules)} 条。")
    return {
        "frequent_itemsets": to_itemset_records(frequent_supports),
        "rules": rules,
        "process_logs": process_logs,
    }
