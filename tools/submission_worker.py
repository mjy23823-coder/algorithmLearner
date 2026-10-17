"""独立测试进程。仅由 workbench.py 启动，不提供 HTTP 服务。

限制导入/反射、阻止文件与网络操作，并由父进程限制时间和内存。
这是本地个人练习执行器，不作为面向不可信租户的安全沙箱。
"""
import ast
import builtins
import importlib
import json
import math
import sys
import traceback
from collections import deque
from types import SimpleNamespace, ModuleType

MODULE_NAMES = ("math", "collections", "itertools", "functools", "heapq", "bisect", "typing", "operator", "statistics", "random", "array")
EXPORTS = {
    "collections": "Counter defaultdict deque OrderedDict ChainMap namedtuple",
    "functools": "cache lru_cache reduce partial cmp_to_key total_ordering wraps",
    "typing": "Any List Optional Dict Tuple Set FrozenSet Deque DefaultDict Sequence Iterable Iterator Callable Union",
    "operator": "add sub mul truediv floordiv mod pow eq ne lt le gt ge and_ or_ xor not_ itemgetter neg abs contains countOf indexOf index",
    "statistics": "mean median median_low median_high mode multimode pstdev stdev variance pvariance fmean geometric_mean harmonic_mean",
    "random": "random randint randrange choice choices shuffle sample seed uniform getrandbits",
    "array": "array",
}
MODULES = {}
for _name in MODULE_NAMES:
    _module = importlib.import_module(_name)
    _exports = EXPORTS[_name].split() if _name in EXPORTS else dir(_module)
    MODULES[_name] = SimpleNamespace(**{name: getattr(_module, name) for name in _exports
                                      if not name.startswith("_") and not isinstance(getattr(_module, name), ModuleType)})


class ListNode:
    def __init__(self, val=0, next=None):
        self.val, self.next = val, next


class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val, self.left, self.right = val, left, right


def build_list(values):
    dummy = tail = ListNode()
    for value in values:
        tail.next = ListNode(value)
        tail = tail.next
    return dummy.next


def build_tree(values):
    if not values or values[0] is None:
        return None
    root, index = TreeNode(values[0]), 1
    queue = deque([root])
    while queue and index < len(values):
        node = queue.popleft()
        for side in ("left", "right"):
            if index < len(values) and values[index] is not None:
                child = TreeNode(values[index])
                setattr(node, side, child)
                queue.append(child)
            index += 1
    return root


def tree_nodes(root):
    queue, seen, nodes = deque([root]), set(), []
    while queue:
        node = queue.popleft()
        if node is None:
            continue
        if id(node) in seen or len(seen) > 5000:
            raise ValueError("返回树中存在环、共享节点或节点过多")
        if not isinstance(node, TreeNode):
            raise TypeError("需要返回 TreeNode 或 None")
        seen.add(id(node)); nodes.append(node)
        queue.extend([node.left, node.right])
    return nodes


def tree_values(root):
    tree_nodes(root)
    queue, values = deque([root]), []
    while queue:
        node = queue.popleft()
        if node is None:
            values.append(None)
        else:
            values.append(node.val)
            queue.extend([node.left, node.right])
    while values and values[-1] is None:
        values.pop()
    return values


def list_values(head):
    values, seen = [], set()
    while head is not None:
        if not isinstance(head, ListNode):
            raise TypeError("需要返回 ListNode 或 None")
        if id(head) in seen or len(values) > 5000:
            raise ValueError("返回链表存在环或节点过多")
        seen.add(id(head)); values.append(head.val); head = head.next
    return values


def bst_properties(root):
    tree_nodes(root)
    values = []
    def walk(node):
        if node is None:
            return 0, True
        lh, lb = walk(node.left)
        values.append(node.val)
        rh, rb = walk(node.right)
        return max(lh, rh) + 1, lb and rb and abs(lh-rh) <= 1
    _, balanced = walk(root)
    return values, balanced, all(a < b for a, b in zip(values, values[1:]))


def plain(value, depth=0):
    if depth > 30:
        raise ValueError("返回值嵌套过深")
    if value is None or type(value) in (bool, int, float, str):
        if type(value) is float and not math.isfinite(value):
            return str(value)
        if isinstance(value, str) and len(value) > 12000:
            raise ValueError("返回字符串过长")
        return value
    if isinstance(value, (list, tuple)):
        if len(value) > 5000:
            raise ValueError("返回列表过长")
        return [plain(v, depth+1) for v in value]
    if isinstance(value, dict) and len(value) < 1000:
        return {str(k): plain(v, depth+1) for k, v in value.items()}
    raise TypeError("返回值需要能够转换为 JSON")


def grade(judge, got, args, expected, original_args):
    if judge == "tree":
        actual = tree_values(got)
    elif judge == "linked_list":
        actual = list_values(got)
    elif judge == "ancestor":
        valid = any(got is node for node in tree_nodes(args[0]))
        actual = got.val if isinstance(got, TreeNode) else plain(got)
        return valid and actual == expected, actual
    elif judge in ("bst", "balanced_bst"):
        values, balanced, valid = bst_properties(got)
        actual = {"inorder": values}
        if judge == "balanced_bst":
            actual["balanced"] = balanced
        return valid and actual == expected, actual
    elif judge == "mutated_array":
        actual = plain(args[0])
    elif judge in ("unique_prefix", "remove_prefix"):
        if type(got) is not int or not 0 <= got <= len(args[0]):
            return False, {"k": plain(got), "error": "返回值必须是合法的有效长度"}
        actual = {"k": got, "prefix": plain(args[0][:got])}
        if judge == "remove_prefix":
            return got == expected["k"] and sorted(actual["prefix"]) == sorted(expected["prefix"]), actual
    elif judge in ("two_sum", "two_sum_1based"):
        actual = plain(got)
        offset = int(judge == "two_sum_1based")
        valid = isinstance(actual, list) and len(actual) == 2 and all(type(i) is int for i in actual)
        if valid:
            a, b = [i-offset for i in actual]
            nums, target = original_args
            valid = a != b and 0 <= a < len(nums) and 0 <= b < len(nums) and nums[a] + nums[b] == target
        return valid, actual
    elif judge == "triplets":
        actual = plain(got)
        valid = isinstance(actual, list) and all(isinstance(v, list) and len(v) == 3 for v in actual)
        return valid and sorted(sorted(v) for v in actual) == sorted(sorted(v) for v in expected), actual
    elif judge == "unordered":
        actual = plain(got)
        return isinstance(actual, list) and sorted(actual) == sorted(expected), actual
    elif judge == "nested_unordered":
        actual = plain(got)
        valid = isinstance(actual, list) and all(isinstance(v, list) for v in actual)
        return valid and sorted(sorted(v) for v in actual) == sorted(sorted(v) for v in expected), actual
    elif judge == "one_of":
        actual = plain(got)
        return actual in expected, actual
    else:
        actual = plain(got)
    # 布尔答案不能用整数 0/1 冒充。
    if type(expected) is bool and type(actual) is not bool:
        return False, actual
    return actual == expected, actual


ALLOWED_DUNDERS = {"__init__", "__lt__", "__eq__", "__hash__", "__repr__", "__str__", "__len__", "__iter__", "__next__", "__getitem__"}


def check_source(code, filename="submission.py"):
    parsed = ast.parse(code, filename=filename)
    for node in ast.walk(parsed):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [node.module] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names]
            if getattr(node, "level", 0) or any(name not in MODULE_NAMES for name in modules):
                raise ValueError("仅支持算法常用标准库：" + ", ".join(MODULE_NAMES))
            if any(alias.name.startswith("_") for alias in node.names):
                raise ValueError("不支持导入内部成员")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ValueError("本地用例执行不支持内部属性或反射访问")
        if isinstance(node, ast.Name) and node.id.startswith("__") and node.id != "__name__":
            raise ValueError("本地用例执行不支持内部变量访问")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("__") and node.name not in ALLOWED_DUNDERS:
            raise ValueError("不支持该特殊方法")
        if isinstance(node, ast.ClassDef) and node.keywords:
            raise ValueError("不支持自定义元类")
    return compile(parsed, filename, "exec")


def build_args(raw_args, codecs):
    args = []
    for raw, codec in zip(raw_args, codecs):
        if codec == "tree":
            value = build_tree(raw)
        elif codec == "list":
            value = build_list(raw)
        elif codec == "node":
            value = next((n for n in tree_nodes(args[0]) if n.val == raw), None)
            if value is None:
                raise ValueError("p/q 的值必须在输入树中存在")
        else:
            value = json.loads(json.dumps(raw))
        args.append(value)
    return args


def capture(judge, got, args):
    """把返回值转成可比较的形式，用于参考解与用户代码对拍。"""
    if judge == "tree":
        return tree_values(got)
    if judge == "linked_list":
        return list_values(got)
    if judge == "ancestor":
        return got.val if isinstance(got, TreeNode) else plain(got)
    if judge in ("bst", "balanced_bst"):
        values, balanced, _ = bst_properties(got)
        return {"inorder": values, "balanced": balanced} if judge == "balanced_bst" else {"inorder": values}
    if judge == "mutated_array":
        return plain(args[0])
    if judge in ("unique_prefix", "remove_prefix"):
        if type(got) is not int or not 0 <= got <= len(args[0]):
            raise ValueError("参考解返回的有效长度不合法")
        return {"k": got, "prefix": plain(args[0][:got])}
    return plain(got)


def describe_error(exc, filename="submission.py"):
    tb, line = exc.__traceback__, None
    while tb:
        if tb.tb_frame.f_code.co_filename == filename:
            line = tb.tb_lineno
        tb = tb.tb_next
    location = f"（代码第 {line} 行）" if line else ""
    return f"{type(exc).__name__}{location}：{str(exc)[:1500]}"


def generated_args(make, index, codecs, seed):
    seed(index)
    raw = make(index)
    if not isinstance(raw, list) or len(raw) != len(codecs):
        raise ValueError(f"make({index}) 需要返回与参数个数相同的列表")
    return json.loads(json.dumps(raw))


def compare(request, scope):
    """用智能体写的暴力解和随机输入，对拍用户代码，返回最小的几个不一致输入。"""
    user = check_source(request["code"])
    reference = check_source(request["reference"], "reference.py")
    generator = check_source(request["generator"], "generator.py")
    space = dict(scope)
    exec(generator, space)
    if "make" not in space:
        raise ValueError("生成器需要定义 make(i)")
    seed = MODULES["random"].seed
    mismatches, checked = [], 0
    for index in range(request["count"]):
        raw = generated_args(space["make"], index, request["codecs"], seed)
        try:
            ref_space = dict(scope)
            exec(reference, ref_space)
            ref_args = build_args(raw, request["codecs"])
            expected = capture(request["judge"], getattr(ref_space["Solution"](), request["method"])(*ref_args), ref_args)
        except Exception as exc:
            return {"checked": checked, "mismatches": [], "reference_error": {"args": raw, "error": describe_error(exc, "reference.py")}}
        if request["judge"] == "one_of":
            expected = [expected]
        checked += 1
        try:
            user_space = dict(scope)
            exec(user, user_space)
            args = build_args(raw, request["codecs"])
            got = getattr(user_space["Solution"](), request["method"])(*args)
            ok, actual = grade(request["judge"], got, args, expected, raw)
            if not ok:
                mismatches.append({"args": raw, "expected": expected, "actual": actual})
        except Exception as exc:
            mismatches.append({"args": raw, "expected": expected, "error": describe_error(exc)})
        if len(mismatches) >= 20:
            break
    mismatches.sort(key=lambda m: len(json.dumps(m["args"])))
    return {"checked": checked, "mismatches": mismatches[:3], "found": len(mismatches)}


def benchmark(request, scope):
    """按输入规模逐级计时，用于核对复杂度；总耗时受父进程超时限制。"""
    import time
    user = check_source(request["code"])
    generator = check_source(request["generator"], "generator.py")
    space = dict(scope)
    exec(generator, space)
    if "make" not in space:
        raise ValueError("生成器需要定义 make(n)")
    seed, timings, spent = MODULES["random"].seed, [], 0.0
    for n in request["sizes"]:
        raw = generated_args(space["make"], n, request["codecs"], seed)
        user_space = dict(scope)
        exec(user, user_space)
        args = build_args(raw, request["codecs"])
        started = time.perf_counter()
        getattr(user_space["Solution"](), request["method"])(*args)
        elapsed = time.perf_counter() - started
        spent += elapsed
        timings.append({"n": n, "ms": round(elapsed * 1000, 3)})
        if spent > 3:
            break
    return {"timings": timings}


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    request = json.loads(sys.stdin.read())
    if sys.platform != "win32":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (384*1024*1024, 384*1024*1024))
        resource.setrlimit(resource.RLIMIT_CPU, (4, 4))
    output, output_size = [], 0

    def safe_print(*values, sep=" ", end="\n", **kwargs):
        nonlocal output_size
        if output_size >= 12000:
            return
        line = (sep.join(str(v) for v in values) + end)[:12000-output_size]
        output.append(line); output_size += len(line)

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level or name not in MODULES:
            raise ImportError("不支持的导入")
        return MODULES[name]

    safe_names = "abs all any bin bool bytearray bytes callable chr dict divmod enumerate filter float format frozenset hash hex int isinstance issubclass iter len list map max min next object ord pow range repr reversed round set slice sorted str sum super tuple zip Exception ValueError TypeError IndexError KeyError RuntimeError StopIteration AssertionError ZeroDivisionError NotImplementedError".split()
    safe = {name: getattr(builtins, name) for name in safe_names}
    safe.update({"__build_class__": builtins.__build_class__, "__import__": safe_import, "print": safe_print})
    scope = {"__builtins__": safe, "__name__": "submission", "ListNode": ListNode, "TreeNode": TreeNode,
             "List": MODULES["typing"].List, "Optional": MODULES["typing"].Optional}
    results = []
    try:
        compiled = check_source(request["code"])

        def audit(event, args):
            if event == "open" or event.startswith(("socket.", "subprocess.", "ctypes.", "os.system", "os.exec", "os.spawn", "os.remove", "os.rename", "os.mkdir", "os.rmdir")):
                raise PermissionError("算法测试不允许文件、网络或外部进程操作")

        sys.addaudithook(audit)
        if request.get("mode") in ("compare", "benchmark"):
            result = (compare if request["mode"] == "compare" else benchmark)(request, scope)
            sys.stdout.write(json.dumps({**result, "stdout": "".join(output), "error": None}, ensure_ascii=False, allow_nan=False))
            return
        for item in request["cases"]:
            try:
                # 每个用例使用新的 Solution 和全局命名空间，避免相互污染。
                namespace = dict(scope)
                exec(compiled, namespace)
                args = build_args(item["args"], request["codecs"])
                if "Solution" not in namespace:
                    raise ValueError("请定义 class Solution")
                method = getattr(namespace["Solution"](), request["method"])
                got = method(*args)
                ok, actual = grade(request["judge"], got, args, item["expected"], item["args"])
                results.append({"name": item["name"], "passed": bool(ok), "args": item["args"], "expected": item["expected"], "actual": actual})
            except Exception as exc:
                results.append({"name": item["name"], "passed": False, "args": item["args"], "expected": item["expected"],
                                "error": describe_error(exc)})
        response = {"cases": results, "stdout": "".join(output), "error": None}
    except Exception as exc:
        response = {"cases": [], "stdout": "".join(output), "error": f"{type(exc).__name__}：{str(exc)[:2000]}"}
    sys.stdout.write(json.dumps(response, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
