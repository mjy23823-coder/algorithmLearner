"""工作台内嵌的 AI 智能体。只作用于当前这道题，工具都在本机服务端执行，每一步都记录给页面查看。

模型接口：OpenAI 兼容的 Chat Completions（tools / tool_calls）或 Claude Messages（tool_use / tool_result），
两种格式共用同一组工具、同样的执行与计数规则，区别只在请求和消息的拼装（见 OpenAILoop、ClaudeLoop）。

边界：
- 不能修改用户代码，不能写入学习进度；“草拟记录”只生成建议，由用户确认后填入复盘；
- 看不到内置参考答案；找反例用的是智能体自己写的暴力解，在与用户代码相同的受限进程里运行；
- 是否计为提示由服务端判定：用例通过前找到反例、或最终回复给出了解题方向，都计为提示。
"""
import json
import math
import secrets
import threading
import time

try:
    from . import coach_ai, code_runner, knowledge, problem_bank
except ImportError:
    import coach_ai, code_runner, knowledge, problem_bank

MAX_ROUNDS = 5
# OpenAI 模型可以在一轮里并行调用多个工具，另限制整个任务的工具调用总数。
MAX_CALLS = 8
JOB_TTL = 1800
ACTIONS = {
    "test_cases": "只运行当前代码的全部内置基础用例，明确判断是否全部通过；列出通过数量、失败用例、期望结果和实际结果，不要修改代码。",
    "counterexample": "帮我找出让当前代码出错的输入（用例通过后也可以用来查隐藏的边界问题）。",
    "complexity": "实测我当前代码的运行时间，核对我写的复杂度对不对。",
    "edge_cases": "为这道题补 3～5 个关键边界用例，用我当前的代码运行，告诉我哪些通过、哪些没通过。",
    "draft": "根据本轮的思路、测试结果和提示使用情况，草拟这次的练习记录。",
}
TOOLS = [
    {"name": "run_tests",
     "description": "用用户当前的代码运行本题的全部内置基础用例，可追加最多 5 组你构造的边界用例（必须给出正确的期望输出）。不会修改用户代码。",
     "input_schema": {"type": "object", "properties": {
         "extra_cases": {"type": "array", "maxItems": 5, "items": {"type": "object", "properties": {
             "name": {"type": "string", "description": "用例名称，例如“空数组”"},
             "args": {"type": "array", "description": "按参数顺序的输入；树用层序数组（null 表示空），链表用数组"},
             "expected": {"description": "正确的期望输出，格式与基础用例一致"}}, "required": ["args", "expected"]}}}}},
    {"name": "find_counterexample",
     "description": "对拍。你写一个简单可靠的暴力参考解（class Solution，方法名与参数和本题相同）和随机小输入生成器 make(i)"
                    "（返回按参数顺序的输入列表；可 import random，调用前已按 i 设置随机种子）。在沙箱里比较用户代码与参考解，"
                    "返回最小的几个不一致输入。只能用 math、collections、itertools、functools、heapq、bisect、typing、random 等标准库，不能读写文件。",
     "input_schema": {"type": "object", "properties": {
         "reference_code": {"type": "string", "description": "暴力参考解，优先正确性而不是效率"},
         "generator_code": {"type": "string", "description": "定义 make(i) 的 Python 代码，输入保持很小（例如长度不超过 8）"},
         "count": {"type": "integer", "minimum": 20, "maximum": 300, "description": "随机输入组数，默认 200"}},
         "required": ["reference_code", "generator_code"]}},
    {"name": "measure_complexity",
     "description": "按逐级增大的输入规模给用户代码计时，用于核对复杂度。generator_code 定义 make(n)，返回规模为 n 的输入列表；"
                    "sizes 为 3～6 个递增规模，建议逐级翻倍，总耗时控制在 3 秒内。返回各规模耗时和估计的增长指数。",
     "input_schema": {"type": "object", "properties": {
         "generator_code": {"type": "string"},
         "sizes": {"type": "array", "items": {"type": "integer"}, "minItems": 3, "maxItems": 6}},
         "required": ["generator_code", "sizes"]}},
    {"name": "draft_record",
     "description": "草拟本次练习记录，供用户确认后填入复盘，不会直接写入进度。只在用户要求草拟记录时调用。",
     "input_schema": {"type": "object", "properties": {
         "result": {"type": "string", "enum": ["independent", "hinted", "failed"]},
         "error_tags": {"type": "array", "items": {"type": "string", "enum": [e["id"] for e in knowledge.ERRORS]}},
         "time_complexity": {"type": "string"}, "space_complexity": {"type": "string"},
         "takeaway": {"type": "string", "description": "一句话复盘：规律、改了什么、下次怎样避免"},
         "why": {"type": "string", "description": "为什么这样判定完成情况"}},
         "required": ["result", "takeaway", "why"]}},
]
OPENAI_TOOLS = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
                for t in TOOLS]
RESULT_LABELS = {"independent": "独立完成", "hinted": "提示后完成", "failed": "暂未完成"}
TOOL_LABELS = {"run_tests": "判断用例", "find_counterexample": "对拍找反例", "measure_complexity": "实测复杂度", "draft_record": "草拟记录"}

SYSTEM = """你是嵌在用户算法练习工作台里的 AI 智能体，帮助用户（Python，准备大厂实习面试）练习当前这道题。你可以调用工具获取证据：运行用例、对拍找反例、实测复杂度、草拟记录。
规则：
- 先用工具拿到证据再下结论；引用结果时写明具体输入和输出。只调用与用户请求相关的工具，总共不超过 4 次。
- 采用费曼学习法，引导用户自己发现问题：绝不给出完整的正确代码或完整解法；指出问题时说清位置和现象，不给修正后的代码。
- 只有用户要求草拟记录时才调用 draft_record；不要编造用户没做过的事。
- 结合学习者画像因材施教：画像里的常见错因可能出现在本题时，优先用工具验证、在结论里用对应的问题提醒；不要把画像原样复述给用户。
- 最终回复用中文，简洁具体，不超过 250 字，不用 Markdown 标题。
- 最终回复最后单独一行写 [[ASSIST:yes]] 或 [[ASSIST:no]]：包含解题方向、关键思路、指出具体错误位置或修改方法时写 yes；只是报告测试或计时结果、提问、确认用户自己说对的内容时写 no。"""


def short(value, limit=300):
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return text if len(text) <= limit else text[:limit] + "…"


def growth(timings):
    """相邻规模的 log(时间比)/log(规模比) 的中位数，粗略估计 n 的增长指数。"""
    slopes = []
    for a, b in zip(timings, timings[1:]):
        if a["ms"] > 0.05 and b["ms"] > 0 and b["n"] > a["n"]:
            slopes.append(math.log(b["ms"] / a["ms"]) / math.log(b["n"] / a["n"]))
    if not slopes:
        return None
    slopes.sort()
    return round(slopes[len(slopes) // 2], 2)


class ClaudeLoop:
    """Claude Messages 格式：工具结果作为 tool_result 内容块，放在下一条 user 消息里。"""

    def __init__(self, conn, model, prompt):
        self.conn, self.model = conn, model
        self.messages = [{"role": "user", "content": prompt}]

    def ask(self, last):
        body = {"model": self.model, "max_tokens": 16000, "system": SYSTEM, "tools": TOOLS, "messages": self.messages}
        if last:
            body["tool_choice"] = {"type": "none"}
        data = coach_ai.messages(self.conn, body, timeout=90, effort="medium")
        content = data.get("content") or []
        # 原样追加模型返回的全部内容块（包括 thinking），保持多轮工具调用的上下文完整。
        self.messages.append({"role": "assistant", "content": content})
        uses = [{"id": b.get("id"), "name": b.get("name"), "input": b.get("input") or {}} for b in content if b.get("type") == "tool_use"]
        return coach_ai.text_of(data), uses if data.get("stop_reason") == "tool_use" else []

    def answer(self, results, note=None):
        blocks = [{"type": "tool_result", "tool_use_id": use["id"], "content": content, **({"is_error": True} if failed else {})}
                  for use, (content, failed) in results]
        if note:
            blocks.append({"type": "text", "text": note})
        self.messages.append({"role": "user", "content": blocks})


class OpenAILoop:
    """OpenAI Chat Completions 格式：参数是 JSON 字符串，每个工具结果单独一条 role=tool 消息。"""

    def __init__(self, conn, model, prompt):
        self.conn, self.model = conn, model
        self.messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]

    def ask(self, last):
        body = {"model": self.model, "messages": self.messages, "tools": OPENAI_TOOLS, "tool_choice": "none" if last else "auto"}
        message = coach_ai.chat_completions(self.conn, body, timeout=90, effort="medium")["message"]
        calls, uses = [], []
        for index, call in enumerate(message.get("tool_calls") or []):
            if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
                continue
            # 个别中转不返回调用编号，或把参数直接给成对象；统一后再回传，保证工具结果能对应回去。
            # 无法解析的参数回传为 "{}"，避免中转在转换格式时因坏 JSON 出错。
            uid, name, raw = call.get("id") or f"call_{len(self.messages)}_{index}", call["function"].get("name"), call["function"].get("arguments")
            if isinstance(raw, dict):
                args, raw = raw, json.dumps(raw, ensure_ascii=False)
            else:
                try:
                    args = json.loads(raw or "{}")
                except (TypeError, ValueError):
                    args, raw = None, "{}"
            calls.append({"id": uid, "type": "function", "function": {"name": name, "arguments": raw or "{}"}})
            uses.append({"id": uid, "name": name, "input": args})
        reply = {"role": "assistant", "content": message.get("content")}
        if calls:
            reply["tool_calls"] = calls
        self.messages.append(reply)
        return coach_ai.openai_text(message), uses

    def answer(self, results, note=None):
        for use, (content, failed) in results:
            self.messages.append({"role": "tool", "tool_call_id": use["id"], "content": content})
        if note:
            self.messages.append({"role": "user", "content": note})


class Job:
    def __init__(self, pid, request):
        self.id = secrets.token_hex(16)
        self.pid, self.request = pid, request
        self.status, self.steps, self.result, self.error = "running", [], None, None
        self.created = time.monotonic()

    def view(self):
        return {"job_id": self.id, "status": self.status, "steps": self.steps, "result": self.result, "error": self.error}


class AgentRunner:
    def __init__(self, workspace):
        self.workspace = workspace
        self.jobs = {}
        self.slots = threading.BoundedSemaphore(2)
        self.lock = threading.Lock()

    def start(self, state, payload):
        ws = self.workspace
        pid = payload.get("id", "")
        info = ws.describe(state, pid)
        pid = info["problem"]["id"]
        settings = coach_ai.load_settings(ws.root)
        if settings["provider"] not in coach_ai.RELAYS:
            raise ValueError("智能体需要连接 OpenAI 兼容接口或 Claude API（例如自建的 CPA）：请在教练设置里填写服务地址和 API Key，测试并启用")
        if not info.get("exercise"):
            raise ValueError("这道题还没有本地用例，智能体无法运行工具；可以先用对话模式")
        draft = info["draft"]
        if draft.get("mock") and not draft["mock"].get("completed"):
            raise ValueError("模拟面试进行中不能使用智能体")
        action = payload.get("action")
        request = coach_ai_text(payload.get("message"), 1000) or ACTIONS.get(action, "")
        if not request:
            raise ValueError("请选择一个任务，或写下想让智能体做什么")
        if not draft.get("session_id"):
            draft = ws.save_draft(payload)
        snapshot = {key: coach_ai_text(payload.get(key), 48000 if key == "code" else 2000) for key in ("code", "idea", "boundary", "time_complexity", "space_complexity", "takeaway")}
        if not snapshot["code"].strip():
            raise ValueError("请先写一些代码再让智能体检查")
        with self.lock:
            now = time.monotonic()
            self.jobs = {k: j for k, j in self.jobs.items() if now - j.created < JOB_TTL}
            if not self.slots.acquire(blocking=False):
                raise ValueError("已有两个智能体任务在运行，请稍后再试")
            job = Job(pid, request)
            self.jobs[job.id] = job
        threading.Thread(target=self.run, args=(job, info, draft, snapshot, settings), daemon=True).start()
        return {"job_id": job.id, "draft": draft}

    def status(self, pid, job_id):
        job = self.jobs.get(job_id or "")
        if not job or job.pid != pid:
            raise ValueError("找不到这个智能体任务，可能已过期")
        return job.view()

    def run(self, job, info, draft, snapshot, settings):
        ws = self.workspace
        try:
            provider = settings["provider"]
            run = ws.latest_run(job.pid, draft["session_id"])
            ctx = {"info": info, "draft": draft, "code": snapshot["code"], "passed": bool(run and run["result"]["passed"]),
                   "helped": draft.get("hints_used", 0) + draft.get("coach_hints", 0) + ws.agent_hints(job.pid, draft["session_id"]) > 0,
                   "counted": False, "suggestion": None}
            prompt = self.context(info, snapshot, run, draft) + f"\n\n用户请求：{job.request}"
            loop = (OpenAILoop if provider == "openai" else ClaudeLoop)(coach_ai.connection(ws.root, provider=provider), settings["model"], prompt)
            final = ""
            for round_index in range(MAX_ROUNDS):
                last = round_index == MAX_ROUNDS - 1
                text, uses = loop.ask(last)
                if not uses or last:
                    final = text
                    break
                results = [(use, self.tool_result(job, use, ctx)) for use in uses]
                spent = len(job.steps) >= MAX_CALLS
                loop.answer(results, "工具调用次数已用完，请根据已有结果直接给出结论。" if round_index == MAX_ROUNDS - 2 or spent else None)
                if spent:
                    final = loop.ask(True)[0]
                    break
            text, assisted = coach_ai.split_assist(final or "智能体没有给出结论，请换个说法再试。")
            counted = bool(ctx["counted"] or assisted)
            stamp = coach_ai.now()
            entries = [{"role": "user", "mode": "agent", "text": job.request, "at": stamp},
                       {"role": "agent", "mode": "agent", "text": text, "at": stamp, "provider": provider, "counted": counted,
                        "steps": [{"tool": s["tool"], "label": s["label"], "summary": s.get("summary", ""), "status": s["status"]} for s in job.steps]}]
            with ws.lock:
                transcript = coach_ai.append_transcript(ws.root, job.pid, draft["session_id"], entries, coach_ai_write())
            job.result = {"reply": text, "counted": counted, "suggestion": ctx["suggestion"], "transcript": transcript,
                          "agent_hints": ws.agent_hints(job.pid, draft["session_id"]),
                          "notice": "这次属于提示类帮助，完成时会按“提示后完成”记录。" if counted else ""}
            job.status = "done"
        except (coach_ai.CoachError, ValueError, OSError) as exc:
            job.status, job.error = "error", str(exc)
        except Exception as exc:  # 保证任务状态总能结束，页面不会一直等待。
            job.status, job.error = "error", f"智能体运行出错：{type(exc).__name__}：{exc}"
        finally:
            self.slots.release()

    def context(self, info, snapshot, run, draft):
        problem, exercise = info["problem"], info["exercise"]
        cases = "；".join(json.dumps({"args": c["args"], "expected": c["expected"]}, ensure_ascii=False) for c in exercise["cases"])
        history = "\n".join(f"- {e.get('date')} {e.get('result')}：{(e.get('note') or '')[:100]}" for e in info.get("history", [])[-4:]) or "（无）"
        tags = "、".join(f"{e['id']}={e['title']}" for e in knowledge.ERRORS)
        codecs = {"tree": "二叉树（层序数组，null 为空）", "list": "链表（数组）", "node": "树中节点的值"}
        params = "，".join(f"{name}：{codecs.get(codec, 'JSON 值')}" for name, codec in zip(exercise["params"], exercise["codecs"]))
        return "\n\n".join([
            f"题目：LC{problem['id']} {problem['title']}（{problem['topic']}）",
            f"题意：{exercise['description']}",
            f"方法签名：Solution.{exercise['method']}({', '.join(exercise['params'])})；参数格式：{params}；判题方式：{exercise['judge']}",
            f"内置基础用例：{cases}",
            "用户的思路：" + (snapshot["idea"] or "（空）"),
            "用户写的边界：" + (snapshot["boundary"] or "（空）"),
            f"用户写的复杂度：时间 {snapshot['time_complexity'] or '（空）'}，空间 {snapshot['space_complexity'] or '（空）'}",
            "用户的复盘：" + (snapshot["takeaway"] or "（空）"),
            "用户当前代码：\n```python\n" + snapshot["code"][:8000] + "\n```",
            coach_ai.summarize_run(run),
            f"本轮已用帮助：{draft.get('hints_used', 0)} 层分层提示，{draft.get('coach_hints', 0)} 次教练提示",
            "这道题过去的练习：\n" + history,
            "学习者画像：\n" + (coach_ai.learner_text(info["learner"]) if info.get("learner") else "（无）"),
            f"可用的错因标签：{tags}",
        ])

    def tool_result(self, job, use, ctx):
        """执行一次工具调用，返回 (给模型的结果文字, 是否失败)，由各格式的 loop 拼成消息。"""
        name, args = use.get("name"), use.get("input")
        if len(job.steps) >= MAX_CALLS:
            return "工具调用次数已用完，这次调用没有执行。", True
        step = {"tool": name, "label": TOOL_LABELS.get(name, name), "status": "running", "summary": ""}
        job.steps.append(step)
        try:
            if not isinstance(args, dict):
                raise ValueError("工具参数不是有效的 JSON 对象")
            output, summary = self.execute(name, args, ctx)
            step.update(status="done", summary=summary)
            return short(output, 6000), False
        except (ValueError, KeyError, TypeError, OSError) as exc:
            step.update(status="error", summary=str(exc)[:200])
            return f"工具调用失败：{exc}", True

    def execute(self, name, args, ctx):
        exercise = problem_bank.get_exercise(ctx["info"]["problem"]["id"])
        if name == "run_tests":
            extras = args.get("extra_cases") or []
            if not isinstance(extras, list) or len(extras) > 5:
                raise ValueError("最多追加 5 组用例")
            extras = [{"name": str(c.get("name") or f"智能体用例 {i + 1}")[:60], "args": c.get("args"), "expected": c.get("expected")}
                      for i, c in enumerate(extras) if isinstance(c, dict)]
            result = code_runner.run_code(ctx["code"], exercise, extras)
            failing = [{k: c.get(k) for k in ("name", "args", "expected", "actual", "error")} for c in result["cases"] if not c.get("passed")][:4]
            summary = f"{result['passed_count']}/{result['total']} 组通过" + (f"（含 {len(extras)} 组补充用例）" if extras else "")
            return {"passed": result["passed"], "passed_count": result["passed_count"], "total": result["total"],
                    "error": result.get("error"), "failing": failing}, summary
        if name == "find_counterexample":
            count = args.get("count", 200)
            result = code_runner.compare_code(ctx["code"], exercise, args.get("reference_code"), args.get("generator_code"),
                                              count if type(count) is int else 200)
            if result.get("error"):
                raise ValueError(result["error"])
            if result.get("reference_error"):
                return result, f"参考解在输入 {short(result['reference_error']['args'], 80)} 出错，需要修正参考解"
            if result["mismatches"]:
                # 用例通过前给出反例，等同于帮用户定位错误。
                if not ctx["passed"]:
                    ctx["counted"] = True
                first = result["mismatches"][0]
                return result, f"对拍 {result['checked']} 组，{result['found']} 组不一致；最小反例 {short(first['args'], 80)}"
            return result, f"对拍 {result['checked']} 组随机输入，没有发现不一致"
        if name == "measure_complexity":
            result = code_runner.benchmark_code(ctx["code"], exercise, args.get("generator_code"), args.get("sizes"))
            if result.get("error"):
                raise ValueError(result["error"])
            slope = growth(result["timings"])
            result["growth_exponent"] = slope
            timings = "，".join(f"n={t['n']}: {t['ms']}ms" for t in result["timings"])
            return result, timings + (f"；增长约 n^{slope}" if slope is not None else "")
        if name == "draft_record":
            result = args.get("result")
            if result not in ("independent", "hinted", "failed"):
                raise ValueError("完成情况只能是 independent、hinted 或 failed")
            allowed = {e["id"] for e in knowledge.ERRORS}
            tags = [t for t in args.get("error_tags") or [] if t in allowed]
            notes = []
            if result == "independent" and (ctx["helped"] or ctx["counted"]):
                result = "hinted"
                notes.append("本轮用过提示，按提示后完成")
            if result != "failed" and not ctx["passed"]:
                notes.append("保存前需要先运行并通过本地用例")
            ctx["suggestion"] = {"result": result, "error_tags": tags, "takeaway": coach_ai_text(args.get("takeaway"), 500),
                                 "time_complexity": coach_ai_text(args.get("time_complexity"), 100),
                                 "space_complexity": coach_ai_text(args.get("space_complexity"), 100),
                                 "why": coach_ai_text(args.get("why"), 300), "notes": notes}
            summary = "草拟：" + RESULT_LABELS[result] + (f"（{'；'.join(notes)}）" if notes else "")
            return {"saved": False, "suggestion": ctx["suggestion"], "message": "已生成草稿，等待用户确认后填入复盘"}, summary
        raise ValueError(f"未知工具：{name}")


def coach_ai_text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ""


def coach_ai_write():
    try:
        from . import coach
    except ImportError:
        import coach
    return coach.atomic_write
