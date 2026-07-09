"""关联规则算法公共工具函数。

五个算法模块都会输出同一种结构：
- frequent_itemsets: 频繁项集列表
- rules: 关联规则列表
- process_logs: 页面展示用的运行过程日志

这里集中放支持度统计、最小支持度计数和规则生成逻辑，避免 Apriori、
FP-Growth、Eclat、AIS、H-Mine 重复实现同一套公式。
"""

from itertools import combinations


def sorted_items(items):
    """把项集转成稳定排序的 tuple，便于展示和比较。"""
    return tuple(sorted(items))


def itemset_key(items):
    """把普通列表/集合转成 frozenset，作为字典 key 使用。"""
    return frozenset(items)


def count_support(itemset, transactions):
    """统计 itemset 在多少条交易中完整出现。"""
    target = set(itemset)
    return sum(1 for transaction in transactions if target.issubset(transaction))


def min_support_count(min_support, total_transactions):
    """把比例形式的 min_support 转成最少出现次数。"""
    return max(1, int((min_support * total_transactions) + 0.999999))


def to_itemset_records(frequent_supports):
    """把内部字典格式转换成模板更容易渲染的列表格式。"""
    records = [
        {"items": list(sorted(itemset)), "support": support}
        for itemset, support in frequent_supports.items()
    ]
    return sorted(records, key=lambda row: (len(row["items"]), -row["support"], row["items"]))


def generate_association_rules(frequent_supports, min_confidence):
    """根据频繁项集生成关联规则，并计算 support/confidence/lift。

    公式：
    - support(A -> B) = support(A union B)
    - confidence(A -> B) = support(A union B) / support(A)
    - lift(A -> B) = confidence(A -> B) / support(B)
    """
    rules = []

    for itemset, support in frequent_supports.items():
        if len(itemset) < 2:
            continue

        items = list(itemset)
        # 对一个频繁项集枚举所有非空前件，剩余部分作为后件。
        for size in range(1, len(items)):
            for antecedent_tuple in combinations(items, size):
                antecedent = frozenset(antecedent_tuple)
                consequent = itemset - antecedent
                antecedent_support = frequent_supports.get(antecedent)
                consequent_support = frequent_supports.get(consequent)

                # 如果前件或后件本身不在频繁项集中，无法用当前支持度字典生成规则。
                if not antecedent_support or not consequent_support:
                    continue

                confidence = support / antecedent_support
                if confidence + 1e-12 < min_confidence:
                    continue

                lift = confidence / consequent_support if consequent_support else 0
                rules.append(
                    {
                        "antecedent": list(sorted(antecedent)),
                        "consequent": list(sorted(consequent)),
                        "support": support,
                        "confidence": confidence,
                        "lift": lift,
                    }
                )

    return sorted(
        rules,
        key=lambda row: (-row["confidence"], -row["lift"], -row["support"], row["antecedent"], row["consequent"]),
    )
