"""Apriori 算法实现。

Apriori 的核心思想是“向下封闭性质”：
如果一个项集是频繁的，那么它的所有子集也必须是频繁的。
因此算法可以从 1 项集开始逐层生成候选项集，并在每一层剪枝。
"""

from itertools import combinations

from . import count_support, generate_association_rules, min_support_count, to_itemset_records


def _create_candidates(previous_frequents, size):
    """由上一轮频繁项集连接生成下一轮候选项集。

    previous_frequents 是 L(k-1)，size 是要生成的 k 项集大小。
    生成候选时会检查所有 k-1 子集是否都频繁，提前剪掉不可能频繁的候选。
    """
    previous_tuples = [tuple(sorted(itemset)) for itemset in previous_frequents]
    previous_lookup = {frozenset(itemset) for itemset in previous_frequents}
    candidates = set()

    for left_index in range(len(previous_tuples)):
        for right_index in range(left_index + 1, len(previous_tuples)):
            left = previous_tuples[left_index]
            right = previous_tuples[right_index]
            merged = tuple(sorted(set(left) | set(right)))

            if len(merged) != size:
                continue

            # Apriori 剪枝：候选项集的所有 size-1 子集都必须出现在上一轮频繁项集中。
            all_subsets_frequent = all(
                frozenset(subset) in previous_lookup
                for subset in combinations(merged, size - 1)
            )
            if all_subsets_frequent:
                candidates.add(frozenset(merged))

    return sorted(candidates, key=lambda itemset: tuple(sorted(itemset)))


def run(transactions, min_support=0.3, min_confidence=0.6):
    """运行 Apriori，并返回频繁项集、关联规则和过程日志。"""
    total = len(transactions)
    threshold_count = min_support_count(min_support, total)
    process_logs = [
        f"读取到 {total} 条交易记录，最小支持度阈值为 {min_support:.2f}，对应至少出现 {threshold_count} 次。",
        "Apriori 使用向下封闭性质：如果一个项集是频繁的，它的所有子集也必须是频繁的。",
    ]

    unique_items = sorted({item for transaction in transactions for item in transaction})
    candidates = [frozenset([item]) for item in unique_items]
    frequent_supports = {}
    previous_frequents = []

    # 第 1 轮直接扫描所有单个商品，得到 L1。
    for candidate in candidates:
        count = count_support(candidate, transactions)
        support = count / total
        if count >= threshold_count:
            frequent_supports[candidate] = support
            previous_frequents.append(candidate)

    process_logs.append(
        f"第 1 轮：生成 C1 候选项集 {len(candidates)} 个，筛选出 L1 频繁项集 {len(previous_frequents)} 个。"
    )

    size = 2
    while previous_frequents:
        # 从 L(k-1) 生成 Ck，再扫描交易计算支持度得到 Lk。
        candidates = _create_candidates(previous_frequents, size)
        current_frequents = []

        for candidate in candidates:
            count = count_support(candidate, transactions)
            support = count / total
            if count >= threshold_count:
                frequent_supports[candidate] = support
                current_frequents.append(candidate)

        process_logs.append(
            f"第 {size} 轮：由 L{size - 1} 连接剪枝生成 C{size} 候选项集 {len(candidates)} 个，"
            f"筛选出 L{size} 频繁项集 {len(current_frequents)} 个。"
        )

        if not current_frequents:
            process_logs.append(f"L{size} 为空，Apriori 迭代结束。")
            break

        # 当前轮频繁项集成为下一轮候选生成的基础。
        previous_frequents = current_frequents
        size += 1

    # 所有频繁项集挖掘结束后，再统一生成关联规则。
    rules = generate_association_rules(frequent_supports, min_confidence)
    process_logs.append(f"基于全部频繁项集生成关联规则，保留置信度不低于 {min_confidence:.2f} 的规则 {len(rules)} 条。")

    return {
        "frequent_itemsets": to_itemset_records(frequent_supports),
        "rules": rules,
        "process_logs": process_logs,
    }
