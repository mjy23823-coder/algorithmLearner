"""学习画像与个性化推荐。

画像只来自进度里的练习记录和用户自己设定的目标（state["profile"]），不修改记录：
- 专题掌握度：按结果给分（独立 1、提示后 0.4、未完成 0），近期权重更高（半衰期 30 天），
  再做平滑，记录少时不会给出极端值；旧格式记录按状态推断结果，与周报口径一致；
- 反复错因：沿用排题的口径（近 4 周至少两次，或 7 天内刚出现）；
- 习惯：近 4 周的独立完成率、提示依赖、用时、打卡和模拟次数。

推荐新题综合主线位置、专题掌握度、近期错因用到的解题模板、难度匹配、节奏偏好、目标日期和面试频率，
每道题都写明理由。理由只说明“为什么适合你”，不写解法要点。
"""
import math
from datetime import date, timedelta

try:
    from . import catalog, coach, knowledge
except ImportError:
    import catalog, coach, knowledge

PACES = {"steady": "稳扎稳打", "normal": "正常推进", "push": "冲刺加速"}
DEFAULT_SETTINGS = {"target_date": None, "daily_minutes": 120, "pace": "normal"}
SKIP_DAYS = 7
HALF_LIFE_DAYS = 30
SCORES = {"independent": 1.0, "hinted": 0.4, "failed": 0.0}
# 掌握度分档：记录太少时只说明“起步”，不下结论。
LEVELS = (("起步", "记录还少"), ("需要加强", "先把基础题做独立"), ("巩固中", "同模板再练几道"), ("较稳", "可以加难度或推进主线"))
DIFFICULTY_FIT = {
    "起步": {"Easy": 2, "Medium": 1, "Hard": -4},
    "需要加强": {"Easy": 2, "Medium": 0, "Hard": -5},
    "巩固中": {"Easy": 0, "Medium": 2, "Hard": -2},
    "较稳": {"Easy": -1, "Medium": 2, "Hard": 1},
}
PACE_FIT = {"steady": {"Easy": 1, "Medium": 0, "Hard": -2}, "normal": {"Easy": 0, "Medium": 0, "Hard": 0},
            "push": {"Easy": -1, "Medium": 1, "Hard": 1}}
FREQUENCY_POINTS = {3: 2, 2: 1, 1: 0}
URGENT_WEEKS = 8


# ---------- 设置 ----------

def settings(state):
    saved = state.get("profile") if isinstance(state.get("profile"), dict) else {}
    return {**DEFAULT_SETTINGS, **{k: v for k, v in saved.items() if k in DEFAULT_SETTINGS}}


def validate_settings(payload, today):
    """校验用户设定；target_date 为空表示不设面试日期。"""
    result = {}
    if "target_date" in payload:
        raw = payload["target_date"]
        if raw in (None, "", "none"):
            result["target_date"] = None
        else:
            try:
                target = date.fromisoformat(str(raw))
            except ValueError:
                raise ValueError("面试日期格式应为 YYYY-MM-DD")
            if not today <= target <= today + timedelta(days=3 * 365):
                raise ValueError("面试日期应在今天到 3 年之内")
            result["target_date"] = target.isoformat()
    if "daily_minutes" in payload:
        minutes = payload["daily_minutes"]
        if type(minutes) is not int or not 15 <= minutes <= 600:
            raise ValueError("每天计划时间应为 15～600 分钟")
        result["daily_minutes"] = minutes
    if "pace" in payload:
        if payload["pace"] not in PACES:
            raise ValueError("节奏只能是 稳扎稳打、正常推进 或 冲刺加速")
        result["pace"] = payload["pace"]
    return result


def apply_settings(state, payload, today):
    state["profile"] = {**settings(state), **validate_settings(payload, today)}
    return state["profile"]


def active_skips(state, today):
    """“换一题”后 7 天内不再推荐。"""
    skips = state.get("recommend_skips") if isinstance(state.get("recommend_skips"), dict) else {}
    return {pid: day for pid, day in skips.items() if 0 <= (today - coach.parse_date(day)).days < SKIP_DAYS}


def skip_recommendation(state, pid, today):
    skips = active_skips(state, today)
    skips[coach.problem_id(pid)] = today.isoformat()
    state["recommend_skips"] = skips
    return skips


# ---------- 画像 ----------

def result_of(event):
    return event["result"] if event.get("result") in SCORES else event.get("inferred_result")


def minutes_of(entry):
    if entry.get("elapsed_seconds"):
        return max(0.1, entry["elapsed_seconds"] / 60)
    return entry.get("minutes")


def level_of(graded, mastery):
    if graded < 2:
        return "起步"
    return "需要加强" if mastery < 50 else "巩固中" if mastery < 75 else "较稳"


def topic_stats(state, today, events):
    rows = {}
    for pid, rec in state.get("completed", {}).items():
        name = catalog.family(rec.get("topic"))
        row = rows.setdefault(name, {"name": name, "problems": 0, "learned": 0, "due": 0, "calibration": 0,
                                     "graded": 0, "independent": 0, "hinted": 0, "failed": 0, "weight": 0.0, "points": 0.0,
                                     "last_practiced": None})
        row["problems"] += 1
        status = coach.mastery_status(rec)
        row["learned"] += status == "learned"
        row["calibration"] += status == "needs_calibration"
        row["due"] += coach.review_state(state, rec, today) in ("due", "overdue")
    for e in events:
        row = rows.get(catalog.family(e["topic"]))
        if not row:
            continue
        row["last_practiced"] = max(filter(None, [row["last_practiced"], e["date"]]))
        result = result_of(e)
        if not result:
            continue
        age = max(0, (today - coach.parse_date(e["date"])).days)
        weight = 0.5 ** (age / HALF_LIFE_DAYS)
        row["graded"] += 1
        row[result] += 1
        row["weight"] += weight
        row["points"] += weight * SCORES[result]
    order = {name: i for i, name in enumerate(catalog.MAIN_LINE)}
    topics = []
    for row in rows.values():
        # 平滑：相当于先验一次 0.5 分的练习，记录少时掌握度靠近 50%。
        mastery = round(100 * (row["points"] + 1) / (row["weight"] + 2))
        level = level_of(row["graded"], mastery)
        idle = (today - coach.parse_date(row["last_practiced"])).days if row["last_practiced"] else None
        topics.append({**{k: v for k, v in row.items() if k not in ("weight", "points")}, "mastery": mastery, "level": level,
                       "level_note": dict(LEVELS)[level], "idle_days": idle})
    return sorted(topics, key=lambda t: (order.get(t["name"], 99), t["name"]))


def habits(events, today):
    start = today - timedelta(days=27)
    recent = [e for e in events if start <= coach.parse_date(e["date"]) <= today]
    graded = [e for e in recent if result_of(e)]
    count = {key: sum(result_of(e) == key for e in graded) for key in SCORES}
    timed = [minutes_of(e) for e in recent if minutes_of(e)]
    days = {e["date"] for e in events}
    streak, cursor = 0, today if today.isoformat() in days else today - timedelta(days=1)
    while cursor.isoformat() in days:
        streak += 1
        cursor -= timedelta(days=1)
    mocks = [e for e in recent if e.get("mock")]
    scored = [e["mock_review"]["average"] for e in mocks if (e.get("mock_review") or {}).get("average")]
    return {"practices": len(recent), "graded": len(graded), **count,
            "independent_rate": round(100 * count["independent"] / len(graded)) if graded else None,
            "hint_rate": round(100 * count["hinted"] / len(graded)) if graded else None,
            "avg_minutes": round(sum(timed) / len(timed), 1) if timed else None, "timed": len(timed),
            "active_days_14": len({e["date"] for e in events if 0 <= (today - coach.parse_date(e["date"])).days < 14}),
            "streak": streak, "per_week": round(len(recent) / 4, 1),
            "mocks": len(mocks), "mock_average": round(sum(scored) / len(scored), 1) if scored else None,
            "inferred": sum(e.get("result") not in SCORES for e in graded)}


def current_families(current):
    names = [name for name in catalog.MAIN_LINE if catalog.related(name, current)]
    return names or [catalog.MAIN_LINE[catalog.line_position(current)]]


def next_family(current):
    families = current_families(current)
    later = [name for name in catalog.MAIN_LINE[catalog.line_position(current) + 1:] if name not in families]
    return later[0] if later else None


def goal(state, today, current):
    config = settings(state)
    position = catalog.line_position(current)
    remaining = [name for name in catalog.MAIN_LINE[position + 1:] if name not in current_families(current)]
    target = coach.parse_date(config["target_date"]) if config["target_date"] else None
    days_left = (target - today).days if target else None
    return {"text": state.get("goal") or "大厂实习算法面试", "target_date": config["target_date"], "days_left": days_left,
            "weeks_left": math.ceil(days_left / 7) if days_left is not None else None,
            "urgent": days_left is not None and days_left <= URGENT_WEEKS * 7,
            "position": position + 1, "total_topics": len(catalog.MAIN_LINE), "remaining_topics": remaining,
            "days_per_topic": round(days_left / max(1, len(remaining) + 1), 1) if days_left is not None else None}


def weaknesses(state, today, error_events):
    titles = {e["id"]: e for e in knowledge.ERRORS}
    rows = []
    for row in sorted(coach.weak_errors(state, today, error_events).values(), key=lambda w: (-w["count"], w["id"])):
        info = titles.get(row["id"], {})
        rows.append({**row, "description": info.get("description", ""), "question": info.get("question", ""),
                     "patterns": sorted(weak_patterns_for(row["problem_ids"]))})
    return rows


def weak_patterns_for(problem_ids):
    ids = set(problem_ids)
    return {p["id"] for p in knowledge.PATTERNS if ids & set(p["problem_ids"])}


def patterns_of(pid):
    return {p["id"] for p in knowledge.PATTERNS if pid in p["problem_ids"]}


def build_profile(state, today, error_events=None):
    """学习画像：专题掌握度、反复错因、习惯、目标与可执行的重点。"""
    error_events = knowledge.error_events(state) if error_events is None else error_events
    events = coach.practice_events(state)
    current = state.get("current_topic", "")
    topics = topic_stats(state, today, events)
    index = {t["name"]: t for t in topics}
    focus_topics = [index[name] for name in current_families(current) if name in index]
    weak = weaknesses(state, today, error_events)
    habit = habits(events, today)
    target = goal(state, today, current)
    config = settings(state)
    profile = {"date": today.isoformat(), "settings": config, "pace_label": PACES[config["pace"]], "current_topic": current,
               "current": focus_topics, "topics": topics, "weaknesses": weak, "habits": habit, "goal": target,
               "strengths": [t["name"] for t in topics if t["level"] == "较稳"],
               "needs_work": [t["name"] for t in topics if t["level"] == "需要加强"],
               "next_topic": next_family(current)}
    profile["summary"] = summarize(profile)
    profile["focus"] = focus_points(profile)
    return profile


def current_mastery(profile):
    rows = [t for t in profile["current"] if t["graded"]]
    if not rows:
        return None, "起步"
    graded = sum(t["graded"] for t in rows)
    mastery = round(sum(t["mastery"] * t["graded"] for t in rows) / graded)
    return mastery, level_of(graded, mastery)


def summarize(profile):
    lines = []
    mastery, level = current_mastery(profile)
    if mastery is None:
        lines.append(f"当前专题「{profile['current_topic'] or '未设置'}」还没有足够的练习记录。")
    else:
        lines.append(f"当前专题「{profile['current_topic']}」掌握度 {mastery}%（{level}）。")
    if profile["strengths"]:
        lines.append("比较稳的专题：" + "、".join(profile["strengths"][:3]) + "。")
    if profile["weaknesses"]:
        top = profile["weaknesses"][0]
        lines.append(f"最需要留意「{top['title']}」，近 4 周出现 {top['count']} 次。")
    habit = profile["habits"]
    if habit["graded"] >= 3:
        lines.append(f"近 4 周独立完成率 {habit['independent_rate']}%，提示依赖 {habit['hint_rate']}%。")
    target = profile["goal"]
    if target["days_left"] is not None:
        lines.append(f"距离目标面试还有 {target['days_left']} 天，主线还剩 {len(target['remaining_topics'])} 个专题。")
    return lines


def focus_points(profile):
    points = []
    mastery, level = current_mastery(profile)
    nxt = profile["next_topic"]
    if level == "较稳" and nxt:
        points.append(f"当前专题已经较稳（{mastery}%），新题开始推进到主线下一专题「{nxt}」。")
    elif level in ("需要加强", "起步"):
        points.append("当前专题还没稳：新题以 Easy 和基础 Medium 为主，同一模板多练一道，先求独立写出。")
    if profile["weaknesses"]:
        top = profile["weaknesses"][0]
        points.append(f"涉及「{top['title']}」的到期题会优先复习；写代码前先问自己：{top['question']}")
    habit = profile["habits"]
    if habit["graded"] >= 4 and (habit["hint_rate"] or 0) >= 50:
        points.append(f"近 4 周提示依赖 {habit['hint_rate']}%：卡住时只看第 1 层提示，自己补完再看下一层。")
    if habit["practices"] >= 3 and habit["timed"] * 2 < habit["practices"]:
        points.append("多数练习没有计时：在工作台开始计时，建立面试时间感。")
    if not habit["mocks"]:
        points.append("近 4 周没有限时模拟，本周安排一次。")
    target = profile["goal"]
    if target["urgent"]:
        points.append(f"离目标面试约 {target['weeks_left']} 周：新题优先大厂高频，每周至少两次限时模拟。")
    elif target["days_left"] is None:
        points.append("还没设置面试日期；设置后会按剩余时间调整推荐节奏。")
    return points[:5]


# ---------- 推荐新题 ----------

def recommend_new(state, profile, excluded, limit=4, has_exercise=None):
    """按画像给目录里的新题打分，返回最多 limit 道（每个专题最多 2 道，有弱项时至少保留 1 道弱项巩固题）。"""
    runnable = has_exercise or (lambda pid: False)
    index = {t["name"]: t for t in profile["topics"]}
    families = current_families(profile["current_topic"])
    nxt = profile["next_topic"]
    _, current_level = current_mastery(profile)
    ready = current_level == "较稳"
    pace = profile["settings"]["pace"]
    habit = profile["habits"]
    dependent = habit["graded"] >= 4 and (habit["hint_rate"] or 0) >= 50
    target = profile["goal"]
    weak = [(w, set(w["patterns"])) for w in profile["weaknesses"] if w["patterns"]]
    order = {name: i for i, name in enumerate(catalog.MAIN_LINE)}
    next_position = order.get(nxt, len(catalog.MAIN_LINE))
    scored = []
    for p in catalog.PROBLEMS:
        if p["id"] in excluded:
            continue
        name = catalog.family(p["topic"])
        topic = index.get(name)
        level = topic["level"] if topic else "起步"
        score, reasons, tags = 0.0, [], []
        if name in families:
            score += 3 if ready else 6
            reasons.append(f"当前专题已较稳，再练一道收尾" if ready else f"属于当前专题「{profile['current_topic']}」，趁热巩固")
            tags.append("当前专题")
        elif name == nxt:
            score += 6 if ready else 3
            reasons.append(f"当前专题已较稳，推进到主线下一专题「{nxt}」" if ready else f"主线下一专题「{nxt}」，提前预热")
            tags.append("推进主线")
        elif topic and level == "需要加强":
            score += 3
            reasons.append(f"「{name}」掌握度 {topic['mastery']}%，补一道同专题题")
            tags.append("补弱专题")
        else:
            score -= 1.5 * max(0, order.get(name, len(catalog.MAIN_LINE)) - next_position)
        shared = [(w, w_patterns & patterns_of(p["id"])) for w, w_patterns in weak]
        shared = [(w, s) for w, s in shared if s]
        if shared:
            top = max(shared, key=lambda item: item[0]["count"])[0]
            score += 2 + min(2, top["count"] / 2)
            reasons.append(f"能练到你近期常错的「{top['title']}」（近 4 周 {top['count']} 次）")
            tags.append("弱项巩固")
        fit = DIFFICULTY_FIT[level][p["difficulty"]] + PACE_FIT[pace][p["difficulty"]]
        if dependent and p["difficulty"] == "Hard":
            fit -= 2
        score += fit
        if fit >= 2:
            reasons.append(f"{p['difficulty']} 适合你在「{name}」的水平（{level}）")
        elif p["difficulty"] == "Hard" and fit >= 1:
            reasons.append(f"你在「{name}」较稳，可以挑战 Hard")
        weight = 2 if target["urgent"] else 1
        score += FREQUENCY_POINTS[p["frequency"]] * weight
        if target["urgent"] and p["frequency"] == 3:
            reasons.append(f"离目标面试约 {target['weeks_left']} 周，优先大厂高频")
        reasons.append(f"{p['difficulty']} · {catalog.frequency_label(p)}")
        if runnable(p["id"]):
            score += 1
        else:
            score -= 3
            reasons.append("工作台暂无本地用例，可由聊天教练检查")
        scored.append({**p, "score": round(score, 2), "reasons": reasons, "reason": reasons, "tags": tags,
                       "workbench": runnable(p["id"])})
    scored.sort(key=lambda r: (-r["score"], -r["frequency"], int(r["id"])))
    picks, per_topic = [], {}
    for row in scored:
        name = catalog.family(row["topic"])
        if per_topic.get(name, 0) >= 2:
            continue
        picks.append(row)
        per_topic[name] = per_topic.get(name, 0) + 1
        if len(picks) >= limit:
            break
    # 有反复错因时，至少保留一道能练到它的题。
    if weak and picks and not any("弱项巩固" in r["tags"] for r in picks):
        extra = next((r for r in scored if "弱项巩固" in r["tags"] and r not in picks), None)
        if extra:
            picks[-1] = extra
    return sorted(picks, key=lambda r: (-r["score"], int(r["id"])))


# ---------- 给教练的画像摘要 ----------

def coach_brief(state, today, pid, error_events=None):
    """教练提示词里的学习者画像：本题专题的掌握度、可能在本题出现的常见错因、提示依赖和节奏偏好。"""
    profile = build_profile(state, today, error_events)
    row = coach.problem(state, pid)
    name = catalog.family(row["topic"])
    topic = next((t for t in profile["topics"] if t["name"] == name), None)
    own = patterns_of(pid)
    relevant = []
    for w in profile["weaknesses"]:
        families = {catalog.family(coach.problem(state, other)["topic"]) for other in w["problem_ids"]}
        if own & set(w["patterns"]) or name in families:
            relevant.append({"id": w["id"], "title": w["title"], "count": w["count"], "question": w["question"]})
    return {"topic": name, "mastery": topic["mastery"] if topic else None, "level": topic["level"] if topic else "起步",
            "graded": topic["graded"] if topic else 0, "relevant_errors": relevant[:3],
            "other_errors": [w["title"] for w in profile["weaknesses"] if w["id"] not in {r["id"] for r in relevant}][:3],
            "hint_rate": profile["habits"]["hint_rate"], "independent_rate": profile["habits"]["independent_rate"],
            "pace": profile["pace_label"], "days_left": profile["goal"]["days_left"]}


def brief_text(brief):
    lines = [f"- 本题专题「{brief['topic']}」" + (f"掌握度 {brief['mastery']}%（{brief['level']}，{brief['graded']} 次有结果的练习）"
                                                if brief["graded"] else "还没有练习记录（起步）")]
    if brief["hint_rate"] is not None:
        lines.append(f"- 近 4 周独立完成率 {brief['independent_rate']}%，提示依赖 {brief['hint_rate']}%")
    for e in brief["relevant_errors"]:
        lines.append(f"- 可能在本题出现的常见错因：{e['title']}（近 4 周 {e['count']} 次），提醒时可问：{e['question']}")
    if brief["other_errors"]:
        lines.append("- 其他近期错因：" + "、".join(brief["other_errors"]))
    lines.append(f"- 节奏偏好：{brief['pace']}" + (f"；距离目标面试 {brief['days_left']} 天" if brief["days_left"] is not None else ""))
    return "\n".join(lines)


# ---------- AI 分析 ----------

ADVICE_SYSTEM = """你是一名 Python 算法面试私人教练，正在给学习者写一份个性化的阶段建议。只依据下面的学习画像和今日计划，不编造没有记录的事。
用中文，分条输出，总共不超过 320 字，不用 Markdown 标题：
1. 一句话判断当前状态（结合掌握度和习惯）；
2. 接下来一周的 2～3 个重点（结合薄弱专题、反复错因和目标日期）；
3. 针对最常见的错因给一个具体练法（例如写代码前自问什么、用什么小例子手动走一遍）；
4. 节奏建议（每天时间分配、复习与新题比例、是否安排模拟）。
不要给出任何题目的解法或代码。"""


def advice_prompt(profile, plan):
    target = profile["goal"]
    topics = "\n".join(f"- {t['name']}：掌握度 {t['mastery']}%（{t['level']}），{t['problems']} 道题，{t['graded']} 次有结果，"
                       f"到期 {t['due']} 道" + (f"，{t['idle_days']} 天没练" if t["idle_days"] is not None else "") for t in profile["topics"])
    weak = "\n".join(f"- {w['title']}：近 4 周 {w['count']} 次（涉及 {'、'.join('LC' + i for i in w['problem_ids'][:4])}）"
                     for w in profile["weaknesses"]) or "- 暂无"
    habit = profile["habits"]
    tasks = "\n".join(f"- {t.get('kind')}：LC{t['id']} {t['title']}（{t['topic']}）" for t in plan["tasks"] if not t.get("recorded")) or "- 今日任务已完成"
    return "\n\n".join([
        f"目标：{target['text']}；面试日期：{target['target_date'] or '未设置'}" + (f"（还有 {target['days_left']} 天）" if target["days_left"] is not None else ""),
        f"节奏偏好：{profile['pace_label']}；每天计划 {profile['settings']['daily_minutes']} 分钟；当前专题：{profile['current_topic']}；"
        f"主线第 {target['position']}/{target['total_topics']} 个专题，之后还有：{'、'.join(target['remaining_topics']) or '无'}",
        "各专题掌握度：\n" + topics,
        "近期反复错因：\n" + weak,
        f"近 4 周习惯：练习 {habit['practices']} 次，有结果 {habit['graded']} 次，独立完成率 {habit['independent_rate']}%，"
        f"提示依赖 {habit['hint_rate']}%，平均用时 {habit['avg_minutes'] or '无记录'} 分钟，近 14 天练习 {habit['active_days_14']} 天，"
        f"连续 {habit['streak']} 天，限时模拟 {habit['mocks']} 次",
        f"复习积压：{plan['backlog']['count']} 道；待校准旧题：{len(plan['calibration'])} 道",
        "今日待完成：\n" + tasks,
    ])


def offline_advice(profile, plan):
    lines = ["当前状态：" + "".join(profile["summary"][:2])]
    lines += [f"{i + 1}. {point}" for i, point in enumerate(profile["focus"][:4])]
    picks = [t for t in plan["tasks"] if not t.get("recorded")]
    if picks:
        lines.append("今天先做：" + "、".join(f"LC{t['id']} {t['title']}" for t in picks[:3]) + "。")
    lines.append("（离线分析只根据固定规则生成；连接模型后可以得到更细的个性化建议。）")
    return "\n".join(lines)
