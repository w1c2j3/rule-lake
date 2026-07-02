"""Eclat 算法实现。

Eclat 使用垂直数据格式：每个商品对应一个 TID-set（出现该商品的交易 ID 集合）。
组合项集的支持度可以通过 TID-set 交集直接得到，适合展示集合计算思想。
"""

from . import generate_association_rules, min_support_count, to_itemset_records


def run(transactions, min_support=0.3, min_confidence=0.6):
    """运行 Eclat，并返回频繁项集、关联规则和过程日志。"""
    total = len(transactions)
    threshold_count = min_support_count(min_support, total)
    process_logs = [
        f"读取到 {total} 条交易记录，最小支持度阈值对应至少出现 {threshold_count} 次。",
        "Eclat 将水平交易数据转换为垂直 TID-set，通过集合交集计算组合项集支持度。",
    ]

    # 水平交易表 -> 垂直 TID-set 映射。
    vertical = {}
    for tid, transaction in enumerate(transactions, start=1):
        for item in transaction:
            vertical.setdefault(item, set()).add(tid)

    process_logs.append(f"垂直数据格式构建完成：得到 {len(vertical)} 个商品到交易 ID 集合的映射。")

    # 先筛选频繁 1 项集，作为递归扩展的起点。
    initial_items = [
        (frozenset([item]), tidset)
        for item, tidset in sorted(vertical.items(), key=lambda row: (row[0],))
        if len(tidset) >= threshold_count
    ]
    process_logs.append(f"初始频繁单项筛选完成：保留 {len(initial_items)} 个频繁单项。")

    frequent_supports = {}
    recursion_steps = 0

    def eclat(prefix_items):
        """递归扩展前缀项集，并用 TID-set 交集计算新组合支持度。"""
        nonlocal recursion_steps
        for index, (itemset, tidset) in enumerate(prefix_items):
            support = len(tidset) / total
            frequent_supports[itemset] = support

            suffix_items = []
            for next_itemset, next_tidset in prefix_items[index + 1:]:
                combined = itemset | next_itemset
                # Eclat 的关键：组合项集出现的交易集合等于两个 TID-set 的交集。
                combined_tidset = tidset & next_tidset
                if len(combined_tidset) >= threshold_count:
                    suffix_items.append((combined, combined_tidset))

            recursion_steps += 1
            if suffix_items:
                process_logs.append(
                    f"扩展前缀 {{{', '.join(sorted(itemset))}}}：通过 TID-set 交集得到 "
                    f"{len(suffix_items)} 个可继续扩展的频繁组合。"
                )
                eclat(suffix_items)

    eclat(initial_items)

    # 频繁项集全部得到后，复用公共规则生成函数计算 confidence/lift。
    rules = generate_association_rules(frequent_supports, min_confidence)
    process_logs.append(f"递归扩展完成：执行 {recursion_steps} 次前缀扩展，得到频繁项集 {len(frequent_supports)} 个。")
    process_logs.append(f"生成关联规则：保留置信度不低于 {min_confidence:.2f} 的规则 {len(rules)} 条。")

    return {
        "frequent_itemsets": to_itemset_records(frequent_supports),
        "rules": rules,
        "process_logs": process_logs,
    }
