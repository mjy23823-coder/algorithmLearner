"""LeetCode 常用结构，供 solutions/ 下的验证脚本使用。

    import sys; sys.path.insert(0, "tools")
    from lc_helpers import *
"""
import sys
from collections import deque
from typing import List, Optional  # noqa: F401  让题解里的类型注解直接可用

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")  # Windows 控制台默认 GBK，中文用例名会乱码


class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next


class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right


def build_list(vals):
    dummy = cur = ListNode()
    for v in vals:
        cur.next = ListNode(v)
        cur = cur.next
    return dummy.next


def list_vals(head):
    out = []
    while head:
        out.append(head.val)
        head = head.next
    return out


def build_tree(vals):
    """按 LeetCode 层序格式建树，如 [3, 9, 20, None, None, 15, 7]。"""
    if not vals or vals[0] is None:
        return None
    root = TreeNode(vals[0])
    queue, i = deque([root]), 1
    while queue and i < len(vals):
        node = queue.popleft()
        for side in ("left", "right"):
            if i < len(vals) and vals[i] is not None:
                child = TreeNode(vals[i])
                setattr(node, side, child)
                queue.append(child)
            i += 1
    return root


def tree_vals(root):
    """转回 LeetCode 层序格式，去掉末尾的 None。"""
    out, queue = [], deque([root])
    while queue:
        node = queue.popleft()
        if node:
            out.append(node.val)
            queue.append(node.left)
            queue.append(node.right)
        else:
            out.append(None)
    while out and out[-1] is None:
        out.pop()
    return out


def check(name, got, expected):
    ok = got == expected
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got={got!r}" + ("" if ok else f" expected={expected!r}"))
    return ok
