"""FP-Growth 算法实现。

FP-Growth 不显式枚举大量候选项集，而是：
1. 统计单项频率并删除低支持度项；
2. 按全局频率排序每条交易；
3. 构建共享前缀的 FP-Tree；
4. 递归挖掘条件模式基和条件 FP-Tree。
"""

from collections import Counter

from . import generate_association_rules, min_support_count, to_itemset_records


class FPNode:
    """FP-Tree 中的节点。

    item 是商品名，count 是经过该节点的交易计数，link 用于 header table
    串联同名节点，方便从某个商品快速回溯条件模式基。
    """

    def __init__(self, item=None, parent=None):
        """初始化一个 FP-Tree 节点。

        参数:
        - item: 当前节点代表的商品名；根节点没有商品名，因此为 None。
        - parent: 父节点引用，用于从 header table 节点回溯条件模式基。

        count 初始为 0，插入交易路径时再累加；children 保存子节点，
        link 则把同名商品节点连成链表，便于后续挖掘条件模式。
        """
        self.item = item
        self.count = 0
        self.parent = parent
        self.children = {}
        self.link = None

    def increment(self, count):
        """累加节点计数。"""
        self.count += count


def _append_header_link(header_table, item, node):
    """把同名节点追加到 header table 的链表尾部。"""
    if header_table[item]["head"] is None:
        header_table[item]["head"] = node
        return

    current = header_table[item]["head"]
    while current.link is not None:
        current = current.link
    current.link = node


def _insert_tree(items, node, header_table, count):
    """把一条已排序交易插入 FP-Tree。"""
    if not items:
        return 0

    first = items[0]
    if first in node.children:
        # 已有同样前缀时复用节点，只增加计数。
        child = node.children[first]
        child.increment(count)
        created = 0
    else:
        # 新前缀路径需要创建节点，并同步挂到 header table。
        child = FPNode(first, node)
        child.increment(count)
        node.children[first] = child
        _append_header_link(header_table, first, child)
        created = 1

    return created + _insert_tree(items[1:], child, header_table, count)


def _build_fp_tree(weighted_transactions, min_count):
    """根据带权交易构建 FP-Tree 和 header table。"""
    item_counts = Counter()
    for items, count in weighted_transactions:
        for item in items:
            item_counts[item] += count

    # 低于最小支持度计数的商品不进入 FP-Tree。
    frequent_counts = {
        item: count
        for item, count in item_counts.items()
        if count >= min_count
    }
    if not frequent_counts:
        return None, {}, 0, []

    header_table = {
        item: {"count": count, "head": None}
        for item, count in frequent_counts.items()
    }
    # 高频商品排在前面，可以让更多交易共享前缀路径。
    rank = {
        item: index
        for index, item in enumerate(sorted(frequent_counts, key=lambda name: (-frequent_counts[name], name)))
    }

    root = FPNode()
    node_count = 1
    ordered_transactions = []
    for items, count in weighted_transactions:
        # 每条交易过滤低支持度项，再按全局频率排序后插入树。
        ordered = [item for item in items if item in frequent_counts]
        ordered.sort(key=lambda item: (rank[item], item))
        if ordered:
            ordered_transactions.append((ordered, count))
            node_count += _insert_tree(ordered, root, header_table, count)

    return root, header_table, node_count, ordered_transactions


def _prefix_paths(item, header_table):
    """收集以 item 为后缀的所有前缀路径，即条件模式基。"""
    paths = []
    node = header_table[item]["head"]

    while node is not None:
        path = []
        parent = node.parent
        while parent is not None and parent.item is not None:
            path.append(parent.item)
            parent = parent.parent

        if path:
            paths.append((list(reversed(path)), node.count))
        node = node.link

    return paths


def _mine_tree(header_table, min_count, total, prefix, frequent_supports, logs, state):
    """递归挖掘 FP-Tree，输出频繁模式。"""
    mining_order = sorted(header_table, key=lambda item: (header_table[item]["count"], item))

    for item in mining_order:
        # 当前后缀 item 与已有 prefix 组合成新的频繁模式。
        new_pattern = frozenset(set(prefix) | {item})
        count = header_table[item]["count"]
        frequent_supports[new_pattern] = count / total
        state["patterns"] += 1

        conditional_patterns = _prefix_paths(item, header_table)
        _, conditional_header, conditional_nodes, _ = _build_fp_tree(conditional_patterns, min_count)

        if conditional_header:
            # 条件 FP-Tree 非空时继续递归挖掘更长模式。
            state["conditional_trees"] += 1
            if state["logged_trees"] < state["log_limit"]:
                logs.append(
                    f"挖掘条件模式基 {{{item}}}：包含 {len(conditional_patterns)} 条前缀路径，"
                    f"构建条件 FP-Tree 得到 {len(conditional_header)} 个频繁项，节点数 {conditional_nodes}。"
                )
                state["logged_trees"] += 1
            _mine_tree(conditional_header, min_count, total, new_pattern, frequent_supports, logs, state)


def run(transactions, min_support=0.3, min_confidence=0.6):
    """运行 FP-Growth，并返回频繁项集、关联规则和过程日志。"""
    total = len(transactions)
    threshold_count = min_support_count(min_support, total)
    weighted_transactions = [(sorted(transaction), 1) for transaction in transactions if transaction]
    item_counts = Counter(item for transaction in transactions for item in transaction)

    process_logs = [
        f"统计单项频率：共发现 {len(item_counts)} 种商品，最小支持度计数为 {threshold_count}。",
    ]

    root, header_table, node_count, ordered_transactions = _build_fp_tree(weighted_transactions, threshold_count)
    if root is None:
        process_logs.append("删除低支持度项后没有可用交易，FP-Growth 结束。")
        return {"frequent_itemsets": [], "rules": [], "process_logs": process_logs}

    process_logs.extend(
        [
            f"删除低支持度项：保留 {len(header_table)} 个频繁单项。",
            f"按全局频率排序交易：得到 {len(ordered_transactions)} 条非空有序交易。",
            f"构建 FP-Tree：树节点总数 {node_count} 个，根节点分支 {len(root.children)} 个。",
        ]
    )

    frequent_supports = {}
    state = {"patterns": 0, "conditional_trees": 0, "logged_trees": 0, "log_limit": 14}
    # 从完整 FP-Tree 开始递归挖掘所有频繁模式。
    _mine_tree(header_table, threshold_count, total, frozenset(), frequent_supports, process_logs, state)
    rules = generate_association_rules(frequent_supports, min_confidence)

    if state["conditional_trees"] > state["logged_trees"]:
        process_logs.append(f"还有 {state['conditional_trees'] - state['logged_trees']} 棵条件 FP-Tree 已省略日志展示。")
    process_logs.append(
        f"挖掘频繁模式：实际通过 FP-Tree 和条件模式基得到频繁项集 {len(frequent_supports)} 个。"
    )
    process_logs.append(f"生成关联规则：保留置信度不低于 {min_confidence:.2f} 的规则 {len(rules)} 条。")

    return {
        "frequent_itemsets": to_itemset_records(frequent_supports),
        "rules": rules,
        "process_logs": process_logs,
    }
