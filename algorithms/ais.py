"""AIS 关联规则频繁项集挖掘实现。

AIS 在扫描交易时，从上一轮频繁项集出发，用同一交易中的商品扩展候选。
与 Apriori 的全局连接不同，它只生成至少在一条实际交易中出现过的候选。
"""

from collections import Counter

from . import generate_association_rules, min_support_count, to_itemset_records


def run(transactions, min_support=0.3, min_confidence=0.6):
    """运行 AIS，并返回统一的频繁项集、规则和过程日志结构。"""
    total = len(transactions)
    threshold_count = min_support_count(min_support, total)
    process_logs = [
        f"读取到 {total} 条交易记录，AIS 最小支持度计数为 {threshold_count}。",
        "AIS 按交易扫描，并只用当前交易中的商品扩展候选项集。",
    ]

    single_counts = Counter(item for transaction in transactions for item in transaction)
    current = {
        frozenset([item])
        for item, count in single_counts.items()
        if count >= threshold_count
    }
    frequent_supports = {
        itemset: single_counts[next(iter(itemset))] / total
        for itemset in current
    }
    process_logs.append(f"AIS 第 1 轮扫描：候选单项 {len(single_counts)} 个，保留频繁项集 {len(current)} 个。")

    size = 2
    while current:
        candidate_counts = Counter()
        for transaction in transactions:
            transaction = set(transaction)
            transaction_candidates = set()
            for itemset in current:
                if not itemset.issubset(transaction):
                    continue
                for item in transaction - itemset:
                    candidate = itemset | {item}
                    if len(candidate) == size:
                        transaction_candidates.add(candidate)
            candidate_counts.update(transaction_candidates)

        next_frequents = {
            candidate
            for candidate, count in candidate_counts.items()
            if count >= threshold_count
        }
        for candidate in next_frequents:
            frequent_supports[candidate] = candidate_counts[candidate] / total

        process_logs.append(
            f"AIS 第 {size} 轮扫描：交易内扩展候选 {len(candidate_counts)} 个，"
            f"保留频繁项集 {len(next_frequents)} 个。"
        )
        if not next_frequents:
            break
        current = next_frequents
        size += 1

    rules = generate_association_rules(frequent_supports, min_confidence)
    process_logs.append(f"AIS 扫描结束：得到频繁项集 {len(frequent_supports)} 个，关联规则 {len(rules)} 条。")
    return {
        "frequent_itemsets": to_itemset_records(frequent_supports),
        "rules": rules,
        "process_logs": process_logs,
    }
