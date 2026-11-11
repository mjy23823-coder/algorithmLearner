import builtins
import json, sys, traceback
from pathlib import Path
from collections import deque
sys.path.insert(0, str(Path(__file__).resolve().parent))
import submission_worker as sw


def send(event, **data):
    sys.stdout.write(json.dumps({"event": event, **data}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def snapshot(frame):
    out = {}
    for key, value in frame.f_locals.items():
        if key.startswith("__"):
            continue
        try:
            out[key] = sw.plain(value)
        except Exception:
            out[key] = f"<{type(value).__name__}>"
    return out


def code_error_line(exc):
    if isinstance(exc, SyntaxError):
        return getattr(exc, "lineno", None)
    tb, line = exc.__traceback__, None
    while tb:
        if tb.tb_frame.f_code.co_filename == "submission.py":
            line = tb.tb_lineno
        tb = tb.tb_next
    return line


def main():
    request = json.loads(sys.stdin.readline())
    code = request["code"]
    exercise = request["exercise"]
    case = (request.get("cases") or exercise["cases"])[0]
    breakpoints = set(request.get("breakpoints") or [])
    commands = {}
    paused = {"value": False}
    stop = {"value": False}
    last_line = {"value": None}

    def wait_command():
        send("paused", line=last_line["value"], locals=paused.get("locals", {}), case=case)
        raw = sys.stdin.readline()
        if not raw:
            stop["value"] = True
            return "stop"
        try:
            return json.loads(raw).get("command", "continue")
        except Exception:
            return "continue"

    def trace(frame, event, arg):
        if frame.f_code.co_filename != "submission.py" or frame.f_code.co_name in ("<module>", "Solution"):
            return trace
        if event == "line":
            line = frame.f_lineno
            should_pause = line in breakpoints or (not breakpoints and last_line["value"] is None)
            if paused["value"] or should_pause:
                last_line["value"] = line
                paused["locals"] = snapshot(frame)
                command = wait_command()
                if command == "stop":
                    raise RuntimeError("调试已停止")
                if command == "step":
                    paused["value"] = True
                else:
                    paused["value"] = False
        return trace

    try:
        compiled = sw.check_source(code)
        safe_names = "abs all any bool dict enumerate filter float int len list map max min print range reversed set sorted str sum tuple zip Exception ValueError TypeError IndexError KeyError RuntimeError StopIteration AssertionError ZeroDivisionError".split()
        safe = {name: getattr(builtins, name) for name in safe_names}
        safe.update({"__build_class__": builtins.__build_class__})
        safe["__import__"] = lambda name, globals=None, locals=None, fromlist=(), level=0: sw.MODULES.get(name) if level == 0 and name in sw.MODULES else (_ for _ in ()).throw(ImportError("不支持的导入"))
        scope = {"__builtins__": safe, "__name__": "submission", "ListNode": sw.ListNode, "TreeNode": sw.TreeNode, "List": sw.MODULES["typing"].List, "Optional": sw.MODULES["typing"].Optional}
        namespace = dict(scope)
        sys.settrace(trace)
        exec(compiled, namespace)
        args = sw.build_args(case["args"], exercise["codecs"])
        method = getattr(namespace["Solution"](), exercise["method"])
        actual = method(*args)
        sys.settrace(None)
        send("done", actual=sw.plain(actual), expected=case["expected"], name=case.get("name", "用例 1"))
    except Exception as exc:
        sys.settrace(None)
        send("error", error=sw.describe_error(exc), line=code_error_line(exc))


if __name__ == "__main__":
    main()
