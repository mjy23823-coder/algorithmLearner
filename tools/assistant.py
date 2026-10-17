"""面板里的 AI 点评与问答：口述复习判断、能力周报点评、今日计划问答、画像阶段分析。

原则是 AI 只给建议，进度由脚本决定：
- 口述复习：模型只给四项打分（ok / partial / missing），记哪一档由 oral_result() 按固定规则换算，用户确认后才保存；
- 周报点评与画像分析：数字来自记录，模型只写点评；
- 今日计划问答：模型可以建议调整顺序或可用时间（[[MINUTES:n]]），由用户在页面上点按钮才重新排，不写进度。
没有连接模型或调用失败时，各功能按固定规则给出离线版本并注明。周报、画像和计划问答不发送代码。
"""
import json
import re
from pathlib import Path

try:
    from . import catalog, coach, coach_ai, insights, knowledge, learner, problem_bank
except ImportError:
    import catalog, coach, coach_ai, insights, knowledge, learner, problem_bank

MARKS = ("ok", "partial", "missing")
ORAL_ITEMS = {"recognition": "题型识别", "idea": "核心思路", "complexity": "复杂度", "boundary": "边界情况"}
MINUTES = re.compile(r"\[\[MINUTES:(\d{2,3})\]\]\s*$")


# ---------- 公共 ----------

def ask(root, system, prompt):
    """调用已启用的模型通道。返回 (回复, 设置, 提示)：离线时回复为 None 且没有提示；失败时回复为 None 并说明原因。"""
    settings = coach_ai.load_settings(root)
    provider = settings["provider"]
    if provider == "offline":
        return None, None, ""
    try:
        text = coach_ai.ask_model(provider, system, prompt, settings["model"],
                                  conn=coach_ai.connection(root, provider=provider) if provider in coach_ai.RELAYS else None)
        return text.strip(), settings, ""
    except coach_ai.CoachError as exc:
        return None, None, f"{exc}；本次改用离线版本。"


def source(settings):
    if not settings:
        return {"provider": "offline", "label": coach_ai.PROVIDERS["offline"], "model": None}
    return {"provider": settings["provider"], "label": coach_ai.PROVIDERS[settings["provider"]], "model": settings["model"]}


def cache_path(root, name):
    return Path(root) / ".runtime" / f"{name}.json"


def read_cache(root, name):
    try:
        data = json.loads(cache_path(root, name).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def write_cache(root, name, data):
    path = cache_path(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    coach.atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))


# ---------- 口述复习判断 ----------

ORAL_SYSTEM = """你是算法面试官，正在听候选人口述复习一道他以前写对过的题。只判断他讲到了什么，不替他补充讲解。
按四项打分，每项只能是 ok（讲对且讲清）、partial（讲到了但不完整或有小错）、missing（没讲或讲错）：
- recognition 题型识别：说出题型或解题模板，并说明为什么；
- idea 核心思路：关键变量各代表什么、每一步怎样更新、什么时候结束；
- complexity 复杂度：时间和额外空间，并且与他讲的思路一致；
- boundary 边界情况：至少一个有意义的边界及处理方式。
只输出一个 JSON 对象，不要任何其他文字：
{"recognition": "ok", "idea": "ok", "complexity": "ok", "boundary": "ok", "feedback": "不超过 120 字：先肯定讲对的，再指出缺了哪一项、可以怎样自查；不要给出完整解法或代码"}"""
OFFLINE_ORAL = "离线粗判只检查是否讲到了四项，不判断对错。连接模型后可以得到逐项点评。"
RECOGNITION_WORDS = ("双指针", "滑动窗口", "窗口", "哈希", "字典", "集合", "递归", "回溯", "BFS", "DFS", "广度", "深度", "栈", "队列",
                     "链表", "二分", "动态规划", "DP", "贪心", "堆", "前缀和", "中序", "前序", "后序", "层序", "快慢指针", "排序")
BOUNDARY_WORDS = ("边界", "为空", "空数组", "空树", "空链表", "空字符串", "只有一个", "单个", "一个元素", "重复", "越界", "负数", "None", "null", "0 个")


def oral_result(marks):
    """四项评分换算成口述结果：思路没讲出来算讲不出；思路不完整算有卡顿；
    思路清楚时，其余三项没有 missing 且最多一项 partial 算讲清楚了，否则算有卡顿。"""
    if marks["idea"] == "missing":
        return "failed"
    if marks["idea"] == "partial":
        return "hinted"
    others = [marks[key] for key in ("recognition", "complexity", "boundary")]
    return "independent" if "missing" not in others and others.count("partial") <= 1 else "hinted"


def parse_marks(text):
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        raise ValueError("回复里没有 JSON")
    data = json.loads(match.group(0))
    marks = {key: str(data.get(key, "")).strip().lower() for key in ORAL_ITEMS}
    if any(value not in MARKS for value in marks.values()):
        raise ValueError("评分不在 ok / partial / missing 之内")
    return marks, str(data.get("feedback") or "").strip()[:300]


def offline_marks(text, row):
    lower = text.lower()
    words = RECOGNITION_WORDS + (row["topic"], catalog.family(row["topic"])) + tuple(p["title"] for p in knowledge.PATTERNS if row["id"] in p["problem_ids"])
    big_o = len(re.findall(r"o\s*\(", lower))
    return {"recognition": "ok" if any(w and w.lower() in lower for w in words) else "missing",
            "idea": "ok" if len(text) >= 60 else "partial" if len(text) >= 20 else "missing",
            "complexity": "ok" if big_o >= 2 or (big_o and "空间" in text) else "partial" if big_o else "missing",
            "boundary": "ok" if any(w.lower() in lower for w in BOUNDARY_WORDS) else "missing"}


def last_passing_code(root, pid):
    folder = Path(root) / "solutions" / f"lc{pid}"
    if not folder.exists():
        return ""
    for path in sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if run.get("result", {}).get("passed"):
            return run.get("code", "")[:3000]
    return ""


def judge_oral(root, state, pid, explanation, today):
    """给一段口述讲解打分并换算建议结果；不保存，由用户确认后再记录。"""
    pid = coach.problem_id(pid)
    rec = state.get("completed", {}).get(pid)
    if not rec:
        raise ValueError(f"LC{pid} 还没有练习记录")
    text = explanation.strip() if isinstance(explanation, str) else ""
    if not 10 <= len(text) <= 2000:
        raise ValueError("请先用几句话讲清题型、思路、复杂度和一个边界（10～2000 字）")
    row = coach.problem(state, pid)
    exercise = problem_bank.get_exercise(pid) or {}
    notes = [e.get("note") or e.get("takeaway") for e in rec.get("history") or [] if e.get("note") or e.get("takeaway")][-3:]
    patterns = [f"{p['title']}：{p['description']}" for p in knowledge.PATTERNS if pid in p["problem_ids"]]
    code = last_passing_code(root, pid)
    prompt = "\n\n".join(part for part in [
        f"题目：LC{pid} {row['title']}（{row['topic']}）",
        f"题意：{exercise['description']}" if exercise.get("description") else "",
        "这道题用到的模板：\n" + "\n".join(patterns) if patterns else "",
        "候选人以前的复盘：\n" + "\n".join(f"- {n}" for n in notes) if notes else "",
        "候选人以前通过的代码（只供你核对思路，不要在反馈里复述）：\n```python\n" + code + "\n```" if code else "",
        "候选人这次的口述：\n" + text,
    ] if part)
    reply, settings, notice = ask(root, ORAL_SYSTEM, prompt)
    marks = feedback = None
    if reply:
        try:
            marks, feedback = parse_marks(reply)
        except (ValueError, TypeError):
            settings, notice = None, "模型的回复格式不对，本次改用离线粗判。"
    if marks is None:
        marks, feedback, settings = offline_marks(text, row), OFFLINE_ORAL, None
    result = oral_result(marks)
    return {"id": pid, "marks": marks, "items": ORAL_ITEMS, "result": result, "result_label": coach.ORAL_LABELS[result],
            "feedback": feedback or "", "notice": notice, **source(settings)}


# ---------- 能力周报点评 ----------

WEEKLY_SYSTEM = """你是 Python 算法面试私人教练，根据学习者这一周的记录写周报点评。只依据给出的数据，不编造没有记录的事。
用中文，分条，不超过 300 字，不用 Markdown 标题：
1. 一句话总结本周（和上周比）；
2. 做得好的一点（引用具体记录）；
3. 最需要改进的一点和具体练法；
4. 下周安排：每天大致怎样分配复习、口述复习、新题和限时模拟，优先练哪个专题。
不要给出任何题目的解法或代码。"""


def rate(window):
    return f"{window['independent_rate']}%" if window["independent_rate"] is not None else "无"


def weekly_prompt(report, profile):
    week, prev = report["week"], report["previous_week"]
    dims = "、".join(f"{d['title']} {d['latest']}" for d in report["dimensions"] if d["latest"] is not None) or "本周没有模拟面试评分"
    errors = "\n".join(f"- {e['title']}：近 4 周 {e['count']} 次（LC{'、LC'.join(e['problem_ids'][:4])}）" for e in report["errors"][:4]) or "- 无"
    progress = "\n".join(f"- LC{p['id']} {p['title']}：{p['from']['date']} {p['from']['result']} → {p['to']['date']} 独立完成"
                         for p in report["progress"][:4]) or "- 无"
    topics = "\n".join(f"- {t['name']}：{t['total']} 道，已掌握 {t['learned']}，需巩固 {t['needs_review']}，到期 {t['due']}" for t in report["topics"])
    backlog = report["backlog"]
    return "\n\n".join([
        f"本周（{week['start']}～{week['end']}）：学习 {week['active_days']} 天，练习 {week['practices']} 次，独立完成率 {rate(week)}，"
        f"平均用时 {week['avg_minutes'] or '无记录'} 分钟，限时模拟 {week['mocks']} 次",
        f"上周：学习 {prev['active_days']} 天，练习 {prev['practices']} 次，独立完成率 {rate(prev)}",
        f"模拟面试五维（最近一次）：{dims}",
        "近期反复错因：\n" + errors,
        "有记录支持的进步：\n" + progress,
        "专题进度：\n" + topics,
        f"复习积压 {backlog['count']} 道（可口述 {backlog.get('oral_ready', 0)} 道），约 {backlog['clear_days']} 天消化；待校准旧题 {report['calibration']} 道",
        "学习画像：" + "".join(profile["summary"]),
        f"目标：{profile['goal']['text']}；面试日期 {profile['goal']['target_date'] or '未设置'}；节奏 {profile['pace_label']}；每天 {profile['settings']['daily_minutes']} 分钟",
        "规则生成的下周重点（供参考）：\n" + "\n".join(f"- {f}" for f in report["focus"]),
    ])


def weekly_advice(root, state, log_path, today):
    report = insights.ability_report(state, today, log_path)
    profile = learner.build_profile(state, today, knowledge.error_events(state, log_path))
    reply, settings, notice = ask(root, WEEKLY_SYSTEM, weekly_prompt(report, profile))
    if reply is None:
        week = report["week"]
        lines = [f"本周学习 {week['active_days']} 天、练习 {week['practices']} 次，独立完成率 {rate(week)}（上周 {rate(report['previous_week'])}）。"]
        lines += [f"{i + 1}. {item}" for i, item in enumerate(report["focus"][:4])]
        lines.append("（离线点评只根据固定规则生成；连接模型后可以得到更细的点评和下周安排。）")
        reply, settings = "\n".join(lines), None
    result = {"text": reply, "week_end": report["week"]["end"], "at": coach_ai.now(), **source(settings)}
    write_cache(root, "weekly-advice", result)
    return {**result, "notice": notice}


def current_weekly(root, today):
    """最近 7 天内生成的周报点评；周报是滚动的 7 天，页面会显示生成日期，可以随时重新点评。"""
    data = read_cache(root, "weekly-advice")
    try:
        return data if data and 0 <= (today - coach.parse_date(data["week_end"])).days < 7 else None
    except (KeyError, ValueError, TypeError):
        return None


# ---------- 画像阶段分析 ----------

def profile_advice(root, state, log_path, today):
    """按学习画像生成阶段建议：只发送画像和今日计划，不发送代码。"""
    plan = coach.build_plan(state, today, learner.settings(state)["daily_minutes"], coach.log_mentions(log_path),
                            knowledge.error_events(state, log_path))
    reply, settings, notice = ask(root, learner.ADVICE_SYSTEM, learner.advice_prompt(plan["profile"], plan))
    if reply is None:
        reply, settings = learner.offline_advice(plan["profile"], plan), None
    result = {"text": reply, "at": coach_ai.now(), "date": today.isoformat(), **source(settings)}
    write_cache(root, "profile-advice", result)
    return {**result, "notice": notice}


# ---------- 今日计划问答 ----------

PLAN_SYSTEM = """你是算法学习教练，回答学习者关于今天学习计划的问题。只依据下面的计划和画像，不编造。
- 可以建议调整做题顺序、取舍或可用时间。复习日期和进度由脚本计算，你不能修改它们，也不要声称已经修改。
- 如果建议换成另一个可用时间重新排题，在回复最后单独一行写 [[MINUTES:分钟数]]（30～300），页面会给出按钮让用户自己确认。
- 用户不想做某道推荐新题时，告诉他在页面上点“换一题”。
- 不要给出任何题目的解法、思路要点或代码。
- 用中文，简洁具体，不超过 200 字，不用 Markdown 标题。"""
KIND_LABEL = {"review": "正式复习", "new": "新题", "calibration": "校准", "recall": "短时回忆", "oral": "口述复习"}


def plan_prompt(plan, profile, history, question):
    def row(t):
        kind = "为你推荐" if t.get("source") == "recommended" else KIND_LABEL.get(t.get("kind"), "练习")
        done = f"（已记录：{t.get('result')}）" if t.get("recorded") else ""
        return f"- {kind}：LC{t['id']} {t['title']}（{t['topic']}）{done}；理由：{'；'.join(t.get('reasons') or []) or '无'}"
    talk = "\n".join(f"{'用户' if m['role'] == 'user' else '教练'}：{m['text'][:300]}" for m in history[-6:])
    return "\n\n".join(part for part in [
        f"今天：{plan['date']}；模式：{plan['mode']}；可用 {plan['minutes']} 分钟；当前专题：{plan['current_topic']}",
        "今日任务：\n" + ("\n".join(row(t) for t in plan["tasks"]) or "- 无"),
        "口述复习（每道约 2 分钟，不占正式名额）：\n" + ("\n".join(row(t) for t in plan["oral"]) or "- 无"),
        "短时回忆（5～10 分钟）：\n" + ("\n".join(row(t) for t in plan["short_recall"]) or "- 无"),
        f"到期但顺延 {plan['backlog']['count']} 道，约 {plan['backlog']['clear_days']} 天消化；本周{'还没有' if plan['mock_due'] else '已有'}限时模拟",
        "学习画像：" + "".join(profile["summary"]) + "\n接下来的重点：" + "；".join(profile["focus"][:3]),
        "此前的问答：\n" + talk if talk else "",
        "用户的问题：" + question,
    ] if part)


def parse_minutes(question):
    """离线时从问题里读出可用时间，例如“1 小时”“半小时”“90 分钟”。"""
    words = {"半": 0.5, "一": 1, "两": 2, "二": 2, "三": 3, "四": 4}
    match = re.search(r"(\d+(?:\.\d+)?)\s*(个)?\s*(小时|h|分钟|min)", question, re.I)
    if match:
        value = float(match.group(1))
        return round(value * 60) if match.group(3).lower() in ("小时", "h") else round(value)
    match = re.search(r"(半|一|两|二|三|四)\s*个?\s*(半)?\s*小时", question)
    if match:
        return round((words[match.group(1)] + (0.5 if match.group(2) else 0)) * 60)
    return None


def ask_plan(root, state, log_path, today, minutes, question):
    question = question.strip() if isinstance(question, str) else ""
    if not 2 <= len(question) <= 500:
        raise ValueError("请输入想问的问题（2～500 字）")
    plan = coach.build_plan(state, today, minutes, coach.log_mentions(log_path), knowledge.error_events(state, log_path))
    chat = read_cache(root, "plan-chat")
    history = chat["messages"] if chat and chat.get("date") == today.isoformat() else []
    reply, settings, notice = ask(root, PLAN_SYSTEM, plan_prompt(plan, plan["profile"], history, question))
    suggested = None
    if reply is None:
        settings = None
        suggested = parse_minutes(question)
        if suggested and 30 <= suggested <= 300 and suggested != plan["minutes"]:
            reply = f"离线模式不能自由回答。可以按 {suggested} 分钟重新排今天的计划，点下面的按钮确认。"
        else:
            suggested = None
            reply = "离线模式不能自由回答。可以在上方切换今天的可用时间重新排题，或在推荐新题上点“换一题”。连接模型后可以直接提问。"
    else:
        match = MINUTES.search(reply)
        if match:
            reply = reply[:match.start()].strip()
            value = int(match.group(1))
            suggested = value if 30 <= value <= 300 and value != plan["minutes"] else None
    stamp = coach_ai.now()
    history = (history + [{"role": "user", "text": question, "at": stamp},
                          {"role": "coach", "text": reply, "at": stamp, "minutes": suggested, **source(settings)}])[-20:]
    write_cache(root, "plan-chat", {"date": today.isoformat(), "messages": history})
    return {"reply": reply, "minutes": suggested, "messages": history, "notice": notice, **source(settings)}


def plan_chat(root, today):
    chat = read_cache(root, "plan-chat")
    return chat["messages"] if chat and chat.get("date") == today.isoformat() else []
