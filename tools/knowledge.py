"""已核对的解题模板与历史错因关系；不会据此自动改掌握状态。"""
import re


def pattern(key, title, ids, description, questions):
    return {"id": key, "title": title, "problem_ids": ids.split(), "description": description, "questions": questions}


PATTERNS = [
    pattern("hash_lookup", "哈希查找与计数", "1 217 242 438 567 383 49 128 454", "用集合判重或用字典维护出现次数，避免重复扫描。", ["字典或集合里保存的是什么？", "什么时候先查询，什么时候再写入？"]),
    pattern("opposing_pointers", "相向双指针", "11 15 16 167 344 977 42 125 18", "两个端点逐步缩小搜索区间；每次移动都要有排除依据。", ["为什么可以移动这一侧？", "答案应在移动前还是移动后更新？"]),
    pattern("write_pointer", "快慢指针原地写入", "26 27 283 75", "扫描指针找有效元素，写入指针维护已完成的前缀。", ["slow 是最后一个有效位置，还是下一个写入位置？", "返回下标还是长度？"]),
    pattern("window", "滑动窗口", "3 209 438 567 904 1004 424 76", "维护连续区间中的状态，根据约束扩大或收缩窗口。", ["窗口什么时候有效？", "收缩一次就够，还是需要 while？"]),
    pattern("stack", "栈顶匹配与消除", "20 1047 150", "新元素只需与当前栈顶比较，局部匹配后更新栈。", ["访问栈顶前是否判断空栈？", "循环结束时返回什么？"]),
    pattern("rewire", "链表连接修改", "203 206 21 24 92 2", "区分移动变量和修改 next 连接，必要时先保存后继节点。", ["这条赋值改变的是变量还是连接？", "删除后是否还应移动 cur？"]),
    pattern("dfs_order", "递归遍历顺序", "94 144 145 226 617", "递归访问左右子树，用处理当前节点的位置控制遍历或修改顺序。", ["当前节点的处理放在哪个位置？", "空节点分支如何结束？"]),
    pattern("bfs_level", "按层 BFS", "102 199 513", "队列保存待访问节点，用本层开始时的队列长度划定一层。", ["level_size 在什么时候记录？", "每个节点是否在层内出队？"]),
    pattern("subtree_return", "递归返回与子树合并", "100 101 104 110 112 235 236 543 700 404 222", "定义子问题返回的信息，再在当前节点合并或向上返回。", ["递归函数返回什么信息？", "调用结果是否被使用并传回上层？"]),
    pattern("inorder_state", "BST 中序状态维护", "230 501 530 538", "利用 BST 遍历顺序，维护计数、前一个值或累计值。", ["需要正向中序还是反向中序？", "共享状态在哪一步更新？"]),
    pattern("bst_bounds", "BST 有序性质与范围", "98 235 450 669 700 701", "利用大小关系缩小递归范围，或传递合法上下界。", ["约束来自直接父节点还是全部祖先？", "什么时候能排除整棵子树？"]),
    pattern("tree_connect", "递归构造与子树接回", "108 226 450 617 669 701 105", "让递归返回新子树的根，并把它接回父节点的对应位置。", ["返回的新根接回哪里？", "零、单、双子节点情况都处理了吗？"]),
    pattern("path_backtrack", "路径传递与回溯", "112 257 437", "将路径状态或剩余目标传入子问题，分支之间保持独立。", ["状态会不会影响另一条分支？", "递归返回时是否需要恢复现场？"]),
    pattern("fast_slow", "快慢指针定位", "876 19 234 141 142", "让两个指针以不同速度或固定间隔前进，定位中点、倒数位置或环。", ["快指针的循环条件要检查哪些节点？", "删除结点时慢指针应停在目标还是前驱？"]),
    pattern("prefix_sum", "前缀和与哈希计数", "560 437", "用前缀和把区间和转成两次前缀和之差，并用字典记录出现次数。", ["字典的初始值为什么是 {0: 1}？", "先查询还是先写入当前前缀和？"]),
    pattern("monotonic", "单调栈与单调队列", "739 239 84", "按单调性弹出不再可能成为答案的元素，栈或队列里通常保存下标。", ["栈里保存值还是下标？", "什么时候弹出，弹出时结算什么？"]),
    pattern("string_scan", "字符串扫描与中心扩展", "14 151 5 459", "按字符或单词扫描，必要时从中心向两侧扩展。", ["奇数和偶数长度是否都处理了？", "多余空格或空字符串会怎样？"]),
]

ERRORS = [
    {"id": "return_loss", "title": "遗漏递归返回值", "description": "递归算出了结果，但调用方没有接住或返回。", "question": "这次递归调用的返回值最终流向哪里？"},
    {"id": "node_scope", "title": "混淆 root 与当前节点", "description": "递归内部误用了外层根节点，影响分支判断或子树连接。", "question": "这一行应该操作当前 node，还是最外层 root？"},
    {"id": "pointer_link", "title": "变量移动与连接混淆", "description": "移动指针变量并不能替代修改链表节点的 next。", "question": "赋值前后，从 dummy 出发能看到什么变化？"},
    {"id": "loop_position", "title": "遗漏循环或循环层级", "description": "扫描或出队操作的位置不对，导致少处理或重复处理节点。", "question": "哪些操作每个元素执行一次，哪些操作每层执行一次？"},
    {"id": "window_condition", "title": "窗口条件写错", "description": "将窗口有效条件写成了不符合题意的比较。", "question": "题目要求等于、至少还是至多？"},
    {"id": "update_order", "title": "状态含义与更新顺序", "description": "混淆变量代表的量，或在计算答案之前改变了关键状态。", "question": "变量保存的究竟是值、下标、距离还是计数？"},
    {"id": "boundary", "title": "边界与指针方向", "description": "初始化、移动方向、空输入或返回长度存在问题。", "question": "用最小输入和边界下标手动走一次。"},
    {"id": "python_syntax", "title": "Python 写法与参数", "description": "算法思路之外的 Python 语法、构造方式或参数顺序问题。", "question": "方法名、参数顺序和节点构造符合 Python 写法吗？"},
]

# 每条是日志中实际发生过的问题；讲解里仅提到的知识点不会自动当成错因。
OBSERVED = [
    ("return_loss", "100", "2026-09-23", 515, "没有使用返回值"),
    ("return_loss", "235", "2026-10-03", 680, "缺少 `return`"),
    ("node_scope", "112", "2026-10-02", 641, "root` 和当前递归节点 `node"),
    ("node_scope", "450", "2026-10-06", 738, "误用外层 `root`"),
    ("node_scope", "226", "2026-09-23", 503, "`root` 与 `node` 混用"),
    ("pointer_link", "203", "2026-09-20", 390, "cur = cur.next.next"),
    ("loop_position", "102", "2026-09-26", 524, "每层循环外"),
    ("loop_position", "26", "2026-10-07", 762, "遗漏循环"),
    ("window_condition", "209", "2026-10-13", 845, "sum == target"),
    ("update_order", "501", "2026-10-07", 750, "更新顺序混淆"),
    ("update_order", "16", "2026-10-16", 874, "最近距离"),
    ("update_order", "404", "2026-10-01", 623, "total_val +="),
    ("boundary", "11", "2026-10-11", 829, "len(height) - 1"),
    ("python_syntax", "242", "2026-09-15", 167, "dict.get(key, default)"),
    ("python_syntax", "108", "2026-10-04", 708, "TreeNode root = new TreeNode"),
]


def error_events(state, log_path=None):
    """有证据的错因事件。给定日志时逐行核对原文；排题时不读日志，直接使用已核对的条目。"""
    ids = set(state.get("completed", {})) | set(state.get("next_new", []))
    lines = log_path.read_text(encoding="utf-8-sig").splitlines() if log_path and log_path.exists() else None
    events = []
    for tag, pid, when, line, needle in OBSERVED:
        if pid not in ids:
            continue
        if lines is None:
            events.append({"tag": tag, "problem_id": pid, "date": when, "source": "学习日志", "line": line, "text": needle})
        elif line <= len(lines) and needle in lines[line-1]:
            events.append({"tag": tag, "problem_id": pid, "date": when, "source": "学习日志",
                           "line": line, "text": lines[line-1].lstrip("- ")})
    allowed = {item["id"] for item in ERRORS}
    for pid, rec in state.get("completed", {}).items():
        for entry in rec.get("history", []):
            for tag in entry.get("error_tags", []):
                if tag in allowed:
                    events.append({"tag": tag, "problem_id": pid, "date": entry["date"], "source": "练习复盘",
                                   "text": entry.get("note") or "本次练习主动标记了这个错因"})
    unique = {(e["tag"], e["problem_id"], e["date"], e["source"]): e for e in events}
    return sorted(unique.values(), key=lambda e: (e["date"], int(e["problem_id"])), reverse=True)


def build_knowledge(state, log_path):
    ids = set(state.get("completed", {})) | set(state.get("next_new", []))
    patterns = [dict(item, problem_ids=[pid for pid in item["problem_ids"] if pid in ids]) for item in PATTERNS]
    events = error_events(state, log_path)
    errors = []
    for item in ERRORS:
        evidence = [e for e in events if e["tag"] == item["id"]]
        errors.append(dict(item, problem_ids=list(dict.fromkeys(e["problem_id"] for e in evidence)), evidence=evidence,
                           last_seen=evidence[0]["date"] if evidence else None))
    return {"patterns": patterns, "errors": errors,
            "note": "模板关系由项目题解规则维护；错因只展示日志证据和主动复盘标记，历史错因不代表现在仍不会。"}


def pattern_ids(pid):
    return [item["id"] for item in PATTERNS if pid in item["problem_ids"]]
