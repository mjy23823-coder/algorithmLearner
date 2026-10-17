"""网页内的教练对话。默认离线引导；用户在设置里开启并测试通过后，才调用模型。

模型通道（只用标准库）：
- openai：OpenAI 兼容的 Chat Completions 接口（/v1/chat/completions，Bearer 认证），
  包括 OpenAI 官方 API 和自建的 CLIProxyAPI（CPA）等中转；
- anthropic：Claude Messages 格式接口（/v1/messages，x-api-key 认证），同样支持 CPA；
- claude_cli：本机已登录的 Claude Code，以 `claude -p` 关闭全部工具后调用。

两个接口通道共用“教练设置”里填写的服务地址和 API Key（Key 保存在本机 .runtime/coach-secret.json）；
未填写时分别读取环境变量 OPENAI_BASE_URL、OPENAI_API_KEY 或 ANTHROPIC_BASE_URL、ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN。

教练只看到这道题的题意、你的草稿、本轮测试结果和练习记录，不读写其他文件。
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_MODELS = {"offline": DEFAULT_MODEL, "openai": "gpt-5", "anthropic": DEFAULT_MODEL, "claude_cli": DEFAULT_MODEL}
TIMEOUT = 90
MODES = {
    "explain": "检查我的讲解",
    "hint": "给我一层提示",
    "review": "帮我看代码",
    "reflect": "复盘总结",
    "ask": "问题意或语法",
}
PROVIDERS = {"offline": "离线引导", "openai": "OpenAI 兼容接口 / CPA", "anthropic": "Claude API / CPA 中转", "claude_cli": "本机 Claude Code"}
# 需要服务地址和 API Key 的接口通道；智能体只能走这两种。
RELAYS = ("openai", "anthropic")
MODEL_NAME = re.compile(r"[A-Za-z0-9._:/\-]{2,100}")
OFFICIAL_BASES = {"openai": "https://api.openai.com", "anthropic": "https://api.anthropic.com"}
ENV_NAMES = {"openai": ("OPENAI_BASE_URL", "OPENAI_API_KEY"), "anthropic": ("ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY")}
ASSIST = re.compile(r"\[\[ASSIST:(yes|no)\]\]\s*$", re.I)
# 由 Claude Code 会话启动面板时，避免子进程把自己当成嵌套会话。
NESTED_ENV = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT", "CLAUDE_CODE_SESSION_ID",
              "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_PID")


class CoachError(Exception):
    pass


# ---------- 设置 ----------

def settings_path(root):
    return Path(root) / ".runtime" / "coach-settings.json"


def secret_path(root):
    return Path(root) / ".runtime" / "coach-secret.json"


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def normalize_base(url):
    """接受 https://host:8317、.../v1 或完整接口地址，统一成不带 /v1 的服务地址。"""
    url = (url or "").strip()
    if not url:
        return ""
    if not re.fullmatch(r"https?://[^\s/?#]+(/[^\s?#]*)?", url):
        raise ValueError("服务地址需要以 http:// 或 https:// 开头，例如 https://你的域名:8317")
    url = url.rstrip("/")
    for suffix in ("/v1/chat/completions", "/v1/messages", "/v1/models", "/v1"):
        if url.endswith(suffix):
            url = url[:-len(suffix)]
            break
    return url


def connection(root=None, override=None, provider=None):
    """模型接口的地址与凭据：页面临时填写 > 本机保存 > 环境变量。凭据不返回给页面。
    provider 省略时按已保存的接口通道，没有则按 Claude 格式。"""
    override = override or {}
    saved = read_json(settings_path(root)) if root else {}
    secret = read_json(secret_path(root)) if root else {}
    if provider not in RELAYS:
        provider = saved.get("provider") if saved.get("provider") in RELAYS else "anthropic"
    env_base, env_key = ENV_NAMES[provider]
    custom = override.get("base_url") or saved.get("base_url")
    base = normalize_base(custom or os.environ.get(env_base) or OFFICIAL_BASES[provider])
    # 设置里填了自己的服务地址（例如 CPA）时，不拿环境变量里的官方 Key 去请求它，Key 也必须在设置里填写。
    key = (override.get("api_key") or "").strip() or secret.get("api_key") or (None if custom else os.environ.get(env_key))
    conn = {"base_url": base, "headers": {}, "source": None, "format": provider}
    if key:
        conn.update(headers={"authorization": "Bearer " + key} if provider == "openai" else {"x-api-key": key}, source="key")
    elif provider == "anthropic" and not custom and os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        conn.update(headers={"authorization": "Bearer " + os.environ["ANTHROPIC_AUTH_TOKEN"]}, source="token")
    return conn


def available(root=None):
    return {"offline": True, **{p: bool(connection(root, provider=p)["source"]) for p in RELAYS}, "claude_cli": bool(shutil.which("claude"))}


def load_settings(root):
    data = read_json(settings_path(root))
    secret = read_json(secret_path(root)).get("api_key") or ""
    provider = data.get("provider") if data.get("provider") in PROVIDERS else "offline"
    model = data.get("model") if isinstance(data.get("model"), str) and MODEL_NAME.fullmatch(data["model"]) else DEFAULT_MODELS[provider]
    try:
        base = normalize_base(data.get("base_url") or "")
    except ValueError:
        base = ""
    return {"provider": provider, "model": model, "tested_at": data.get("tested_at"), "base_url": base,
            "has_key": bool(secret), "key_hint": ("…" + secret[-4:]) if len(secret) > 8 else ("已保存" if secret else ""),
            "env_base_urls": {p: bool(os.environ.get(ENV_NAMES[p][0])) for p in RELAYS}, "relays": list(RELAYS),
            "default_models": DEFAULT_MODELS, "available": available(root), "labels": PROVIDERS, "modes": MODES}


def save_settings(root, payload):
    provider = payload.get("provider")
    if provider not in PROVIDERS:
        raise ValueError("请选择离线引导、OpenAI 兼容接口、Claude API 或本机 Claude Code")
    model = (payload.get("model") or DEFAULT_MODELS[provider]).strip()
    if not MODEL_NAME.fullmatch(model):
        raise ValueError(f"模型名称格式不正确，例如 {DEFAULT_MODELS[provider]}")
    old = read_json(settings_path(root))
    base = normalize_base(payload["base_url"]) if "base_url" in payload else old.get("base_url", "")
    key = payload.get("api_key")
    if key is not None and (not isinstance(key, str) or len(key) > 400 or any(c.isspace() for c in key.strip())):
        raise ValueError("API Key 格式不正确")
    if provider in RELAYS:
        usable = bool(connection(root, {"base_url": base, "api_key": key or ""}, provider)["source"])
    else:
        usable = provider == "offline" or bool(shutil.which("claude"))
    if not usable:
        raise ValueError("这个通道还不能使用：" + ("请填写服务地址和 API Key" if provider in RELAYS else "请先安装并登录 Claude Code"))
    Path(root, ".runtime").mkdir(parents=True, exist_ok=True)
    if key and key.strip():
        secret_path(root).write_text(json.dumps({"api_key": key.strip()}), encoding="utf-8")
    data = {"provider": provider, "model": model, "base_url": base, "tested_at": payload.get("tested_at")}
    settings_path(root).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return load_settings(root)


# ---------- 上下文与提示词 ----------

MODE_RULES = {
    "explain": "只提问并指出讲解中的漏洞，不提供新的思路。围绕用户写下的题型、思路、变量和边界追问 1～3 个问题；用户没写思路时，请他先用两三句话说明。",
    "hint": "只给第 {level} 层提示（1=题型与切入角度；2=关键变量或状态，配合一个小例子推演；3=终止条件、状态更新与返回值的结构）。不写代码，不越级给出完整解法。",
    "review": "检查代码。本地用例未通过时，只指出最关键的一处问题的位置或现象，让用户自己修改，不给修正后的代码；全部通过时，分三行给出：正确性、复杂度、最小修改建议（各一句）。",
    "reflect": "帮助复盘：追问题型识别、一句话模板、复杂度和一个错因；最后只总结用户已经说对的内容，帮他确认模板。",
    "ask": "只回答题意澄清和 Python 语法问题。用户问解题思路或要答案时，礼貌说明需要使用“给我一层提示”。",
}


PERSONALIZE = ("结合下面的学习者画像因材施教：掌握度低或起步的专题多用小例子分步追问，较稳的专题多追问复杂度、边界和更优解；"
               "如果画像里的常见错因可能出现在本题，适时用对应的问题提醒，但不要替用户指出答案；不要把画像原样复述给用户。")


def system_prompt(mode, level=1, mock=False):
    rule = MODE_RULES[mode].format(level=level)
    lines = [
        "你是一名 Python 算法面试教练，在用户本机的学习面板里陪他练一道题。默认采用费曼学习法：先让用户解释题型、核心思路、关键变量和一个小例子，再写代码。",
        "用中文，简洁、具体、鼓励；不超过 220 字，代码点评最多 350 字；不用 Markdown 标题。",
        "绝不给出完整代码或完整解法。只依据下面提供的题目、草稿、测试结果和练习记录，不编造用户没做过的事。",
        f"本次模式：{MODES[mode]}。{rule}",
    ]
    if mock:
        lines.append("现在是限时模拟面试，你扮演面试官：不透露题型和题号，不主动提示；用户求助时只给方向性提示，并像面试官一样追问复杂度和边界。")
    else:
        lines.append(PERSONALIZE)
    lines.append("回复最后单独一行写 [[ASSIST:yes]] 或 [[ASSIST:no]]：包含解题方向、关键思路、指出具体错误位置或修改方法时写 yes；只是提问、复述题意、解释 Python 语法或确认用户自己说对的内容时写 no。")
    return "\n".join(lines)


def summarize_run(run):
    if not run:
        return "本轮还没有运行本地用例。"
    result = run["result"]
    lines = [f"本地用例：{result['passed_count']}/{result['total']} 通过" + ("（全部通过）" if result["passed"] else "")]
    if result.get("error"):
        lines.append("运行错误：" + result["error"][:400])
    for case in result.get("cases", []):
        if not case.get("passed"):
            lines.append(f"未通过「{case['name']}」：输入 {json.dumps(case['args'], ensure_ascii=False)[:300]}；"
                         f"期望 {json.dumps(case['expected'], ensure_ascii=False)[:200]}；"
                         f"{'错误 ' + case['error'][:300] if case.get('error') else '实际 ' + json.dumps(case.get('actual'), ensure_ascii=False)[:200]}")
            break
    return "\n".join(lines)


def context_text(info, draft, run, transcript, mock=False):
    problem, exercise = info["problem"], info.get("exercise") or {}
    title = "（模拟面试，题号与题名不显示给用户）" if mock else f"LC{problem['id']} {problem['title']}（{problem['topic']}）"
    history = []
    for entry in (info.get("history") or [])[-4:]:
        history.append(f"- {entry.get('date')} {entry.get('result')}：{(entry.get('note') or '')[:120]}")
    errors = [f"- {e['title']}：{e['question']}" for e in info.get("historical_errors", [])][:3]
    parts = [
        f"题目：{title}",
        f"题意：{exercise.get('description', '（未配置）')}",
        f"方法签名：Solution.{exercise.get('method', '?')}({', '.join(exercise.get('params', []))})" if exercise else "",
        "基础用例：" + "；".join(json.dumps({"args": c["args"], "expected": c["expected"]}, ensure_ascii=False) for c in exercise.get("cases", [])[:3]),
        f"本轮已看提示：{draft.get('hints_used', 0)} 层分层提示，{draft.get('coach_hints', 0)} 次教练提示",
        "用户写下的思路：" + (draft.get("idea") or "（空）"),
        "用户写下的边界：" + (draft.get("boundary") or "（空）"),
        f"用户写的复杂度：时间 {draft.get('time_complexity') or '（空）'}，空间 {draft.get('space_complexity') or '（空）'}",
        "用户复盘：" + (draft.get("takeaway") or "（空）"),
        "用户代码：\n```python\n" + (draft.get("code") or "")[:6000] + "\n```",
        summarize_run(run),
    ]
    if not mock:
        if info.get("learner"):
            parts.append("学习者画像：\n" + learner_text(info["learner"]))
        parts.append("这道题过去的练习：\n" + ("\n".join(history) or "（无）"))
        if errors:
            parts.append("这道题有证据的历史错因：\n" + "\n".join(errors))
    if transcript:
        talk = "\n".join(f"{'用户' if m['role'] == 'user' else '教练'}（{MODES.get(m.get('mode'), '')}）：{m['text'][:600]}" for m in transcript[-10:])
        parts.append("此前对话：\n" + talk)
    return "\n\n".join(p for p in parts if p)


def learner_text(brief):
    try:
        from . import learner
    except ImportError:
        import learner
    return learner.brief_text(brief)


# ---------- 离线引导 ----------

def offline_reply(mode, info, draft, run, hint_text=None, mock=False):
    exercise = info.get("exercise") or {}
    patterns = info.get("patterns") or []
    if mode == "explain":
        if not draft.get("idea", "").strip():
            return "先别急着写代码。用两三句话写在“我的核心思路”里：这题属于什么类型？你打算维护哪些变量，每个变量代表什么？写好后再点一次，我按你的讲解追问。"
        questions = ["你的关键变量分别代表什么？在循环或递归的每一步，它们怎样变化？",
                     "拿第一组基础用例，手动走一遍，写出每一步变量的值。"]
        if not mock:
            # 你常犯、且可能出现在本题的错因，排在模板问题前面。
            questions[1:1] = [f"你近期常出现「{e['title']}」：{e['question']}" for e in (info.get("learner") or {}).get("relevant_errors", [])[:1]]
            questions += [q for p in patterns for q in p.get("questions", [])][:2]
        if not draft.get("boundary", "").strip():
            questions.append("再补一个边界情况：最小输入、重复值或空节点时会怎样？")
        if not draft.get("time_complexity", "").strip():
            questions.append("你预计的时间和空间复杂度是多少？说明依据。")
        return "我按你的讲解追问几个问题，答清楚再动手：\n" + "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions[:4]))
    if mode == "hint":
        return hint_text or "三层分层提示都已展开。可以对照未通过的用例逐行打印变量，或在设置里连接模型教练继续讨论。"
    if mode == "review":
        if not run:
            return "先点“运行本地用例”，我根据真实结果和你一起定位问题。"
        result = run["result"]
        if not result["passed"]:
            case = next((c for c in result.get("cases", []) if not c.get("passed")), None)
            text = f"本地用例 {result['passed_count']}/{result['total']} 通过。"
            if result.get("error"):
                text += f"\n运行错误：{result['error'][:300]}"
            if case:
                text += (f"\n先看「{case['name']}」：输入 {json.dumps(case['args'], ensure_ascii=False)[:200]}，期望 "
                         f"{json.dumps(case['expected'], ensure_ascii=False)[:120]}，"
                         + (f"报错 {case['error'][:200]}。" if case.get("error") else f"你得到 {json.dumps(case.get('actual'), ensure_ascii=False)[:120]}。"))
            asks = [e["question"] for e in info.get("historical_errors", [])][:1] if not mock else []
            asks += ["用这组输入手动走一遍，第一次和期望不一致的是哪一步？", "检查终止条件、状态更新顺序和返回值这三处。"]
            return text + "\n" + "\n".join(f"- {q}" for q in asks[:3])
        return ("本地用例全部通过，接下来确认三件事：\n- 时间复杂度：循环或递归一共执行多少次？和你写的 "
                f"{draft.get('time_complexity') or '（还没填写）'} 一致吗？\n- 额外空间：哪些变量或递归栈随输入规模增长？\n"
                "- 再补一个自己的边界用例（空输入、单元素、重复值）运行一次。\n离线模式不能点评 Python 写法细节，需要时可连接模型教练。")
    if mode == "reflect":
        lines = []
        if not draft.get("takeaway", "").strip():
            lines.append("用一句话写下这题的模板或规律，填在“一句话复盘”里，再点一次复盘。")
        else:
            lines.append("对照你的复盘，检查是否说清了：题型识别依据、核心状态、复杂度、一个易错点。")
            if patterns and not mock:
                lines.append("参考模板：" + "；".join(f"{p['title']}——{p['description']}" for p in patterns[:2]))
        errors = info.get("historical_errors", []) if not mock else []
        if errors:
            lines.append(f"这题以前出现过「{errors[0]['title']}」。这次是否还出现？没有的话，在复盘里写下你是怎样避免的。")
        lines.append("最后勾选这次真实遇到的错因（没有就不选），再保存结果。")
        return "\n".join(lines)
    return ("离线模式只能提供固定引导，无法回答自由提问。题意："
            f"{exercise.get('description', '见左侧题目描述')}\n需要自由提问时，可在“教练设置”里连接模型。")


# ---------- 模型调用 ----------

HTTP_ERRORS = {401: "API Key 无效或已失效（CPA 的 Key 需与 config.yaml 的 api-keys 一致）", 403: "当前凭据无权使用这个模型",
               404: "找不到接口或模型：服务地址不要带 /v1，并检查模型名称", 429: "请求过于频繁或额度用完，请稍后再试",
               529: "模型服务繁忙，请稍后再试"}


def http_json(conn, path, body=None, timeout=TIMEOUT, extra_headers=None):
    if not conn["source"]:
        raise CoachError("还没有配置模型接口：请在教练设置里填写服务地址和 API Key")
    version = {"anthropic-version": "2023-06-01"} if conn.get("format", "anthropic") == "anthropic" else {}
    headers = {"content-type": "application/json", **version, **conn["headers"], **(extra_headers or {})}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = Request(conn["base_url"] + path, data=data, headers=headers, method="POST" if body is not None else "GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            raw = json.loads(exc.read().decode("utf-8"))
            detail = (raw.get("error") or {}).get("message", "") if isinstance(raw.get("error"), dict) else str(raw.get("error") or "")
        except (ValueError, OSError, AttributeError):
            detail = ""
        error = CoachError(HTTP_ERRORS.get(exc.code, f"模型服务返回 {exc.code}") + (f"：{detail[:200]}" if detail else ""))
        error.status = exc.code
        raise error
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise CoachError(f"连接不到模型服务（{conn['base_url']}）：{getattr(exc, 'reason', exc)}")


def messages(conn, body, timeout=TIMEOUT, effort="low"):
    """调用 /v1/messages。先带上备选模型与 effort；中转或旧模型不支持时，去掉这些可选参数重试一次。"""
    full = {**body, "output_config": {"effort": effort}, "fallbacks": "default"}
    try:
        data = http_json(conn, "/v1/messages", full, timeout, {"anthropic-beta": "server-side-fallback-2026-07-01"})
    except CoachError as exc:
        if getattr(exc, "status", None) != 400:
            raise
        data = http_json(conn, "/v1/messages", body, timeout)
    if data.get("stop_reason") == "refusal":
        raise CoachError("模型拒绝回答这条请求")
    return data


def text_of(data):
    return "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text").strip()


def call_anthropic(system, prompt, model, timeout=TIMEOUT, conn=None):
    data = messages(conn or connection(provider="anthropic"), {"model": model, "max_tokens": 16000, "system": system,
                                                               "messages": [{"role": "user", "content": prompt}]}, timeout)
    text = text_of(data)
    if not text:
        raise CoachError("模型没有返回文字内容")
    return text


def chat_completions(conn, body, timeout=TIMEOUT, effort="low"):
    """调用 OpenAI 兼容的 /v1/chat/completions，返回第一个 choice。
    先带上 reasoning_effort；中转或非推理模型不支持而返回 400 时，去掉它重试一次。"""
    try:
        data = http_json(conn, "/v1/chat/completions", {**body, "reasoning_effort": effort}, timeout)
    except CoachError as exc:
        if getattr(exc, "status", None) != 400:
            raise
        data = http_json(conn, "/v1/chat/completions", body, timeout)
    choices = data.get("choices") if isinstance(data, dict) else None
    if not choices or not isinstance(choices[0], dict) or not isinstance(choices[0].get("message"), dict):
        raise CoachError("模型服务没有返回有效结果（缺少 choices）")
    if choices[0]["message"].get("refusal"):
        raise CoachError("模型拒绝回答这条请求")
    return choices[0]


def openai_text(message):
    """content 一般是字符串；部分中转返回内容片段数组。"""
    content = message.get("content")
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") in ("text", "output_text"))
    return (content or "").strip() if isinstance(content, str) else ""


def call_openai(system, prompt, model, timeout=TIMEOUT, conn=None):
    choice = chat_completions(conn or connection(provider="openai"),
                              {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}, timeout)
    text = openai_text(choice["message"])
    if not text:
        raise CoachError("模型没有返回文字内容" + ("（输出长度已达上限）" if choice.get("finish_reason") == "length" else ""))
    return text


def list_models(conn):
    """读取接口提供的模型（CPA、OpenAI 与 Claude 官方 API 都支持 GET /v1/models）。"""
    headers = {}
    if "x-api-key" in conn["headers"]:
        headers["authorization"] = "Bearer " + conn["headers"]["x-api-key"]
    data = http_json(conn, "/v1/models", None, 20, headers)
    ids = [m.get("id") for m in data.get("data", []) if isinstance(m, dict) and isinstance(m.get("id"), str)]
    return sorted(dict.fromkeys(i for i in ids if MODEL_NAME.fullmatch(i)))


def call_cli(system, prompt, model, timeout=TIMEOUT):
    executable = shutil.which("claude")
    if not executable:
        raise CoachError("没有找到 claude 命令，请先安装并登录 Claude Code")
    env = {k: v for k, v in os.environ.items() if k not in NESTED_ENV}
    args = [executable, "-p", "--output-format", "json", "--tools", "", "--no-session-persistence",
            "--strict-mcp-config", "--disable-slash-commands", "--system-prompt", system, "--model", model]
    # 在空目录运行，避免加载项目 CLAUDE.md；工具全部关闭，只生成文字。
    with tempfile.TemporaryDirectory(prefix="algo-coach-") as folder:
        try:
            done = subprocess.run(args, input=prompt.encode("utf-8"), capture_output=True, cwd=folder, env=env,
                                  timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            raise CoachError(f"Claude Code 超过 {timeout} 秒没有回应，可在终端运行 claude 检查登录状态")
        except OSError as exc:
            raise CoachError(f"无法启动 Claude Code：{exc}")
    output = done.stdout.decode("utf-8", errors="replace").strip()
    try:
        data = json.loads(output.splitlines()[-1]) if output else {}
    except ValueError:
        data = {}
    if done.returncode or data.get("is_error") or not data.get("result"):
        detail = data.get("result") or done.stderr.decode("utf-8", errors="replace").strip()[-300:] or output[-300:]
        raise CoachError("Claude Code 调用失败" + (f"：{detail}" if detail else ""))
    return str(data["result"]).strip()


def ask_model(provider, system, prompt, model, timeout=TIMEOUT, conn=None):
    if provider == "openai":
        return call_openai(system, prompt, model, timeout, conn)
    if provider == "anthropic":
        return call_anthropic(system, prompt, model, timeout, conn)
    if provider == "claude_cli":
        return call_cli(system, prompt, model, timeout)
    raise CoachError("离线模式不调用模型")


def split_assist(text):
    """去掉末尾的提示标记，返回 (正文, 是否提供了解题帮助)。"""
    match = ASSIST.search(text)
    if not match:
        return text.strip(), None
    return text[:match.start()].strip(), match.group(1).lower() == "yes"


def probe(root, provider, model, override=None):
    started = time.monotonic()
    text = ask_model(provider, "你在做连通性测试，只回复“连接正常”。", "连通性测试", model, timeout=60,
                     conn=connection(root, override, provider) if provider in RELAYS else None)
    return {"ok": True, "provider": provider, "model": model, "reply": text[:80],
            "seconds": round(time.monotonic() - started, 1), "tested_at": datetime.now(timezone.utc).isoformat()}


# ---------- 对话记录 ----------

def transcript_path(root, pid, session_id):
    return Path(root) / "solutions" / ".coach" / f"lc{pid}-{session_id}.json"


def read_transcript(root, pid, session_id):
    if not session_id or not re.fullmatch(r"[0-9a-f]{32}", session_id):
        return []
    try:
        return json.loads(transcript_path(root, pid, session_id).read_text(encoding="utf-8"))["messages"]
    except (OSError, ValueError, KeyError):
        return []


def append_transcript(root, pid, session_id, messages, write):
    path = transcript_path(root, pid, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    history = (read_transcript(root, pid, session_id) + messages)[-60:]
    write(path, json.dumps({"id": pid, "session_id": session_id, "messages": history}, ensure_ascii=False, indent=2).encode("utf-8"))
    return history


def now():
    return datetime.now(timezone.utc).isoformat()
