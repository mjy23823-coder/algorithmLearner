"""排题：复习优先级、今日计划（build_plan）、限时模拟候选题与时间档位。"""
import math
from datetime import timedelta

try:
    from . import catalog, knowledge, learner
    from .records import (MOCK_LIMITS, ORAL_LABELS, due_of, has_exercise, last_oral, last_result, mastery_status,
                          oral_eligible, oral_slots, parse_date, positive_minutes, problem, today_records, weak_errors)
except ImportError:
    import catalog, knowledge, learner
    from records import (MOCK_LIMITS, ORAL_LABELS, due_of, has_exercise, last_oral, last_result, mastery_status,
                         oral_eligible, oral_slots, parse_date, positive_minutes, problem, today_records, weak_errors)

def related(topic, current):
    return catalog.related(topic, current)



def family_last_practice(state):
    last = {}
    for rec in state.get("completed", {}).values():
        name = catalog.family(rec.get("topic"))
        for value in filter(None, [e.get("date") for e in rec.get("history") or []] + [rec.get("last_done")]):
            last[name] = max(last.get(name, value), value)
    return last


def review_priority(state, pid, rec, today, current, weak, problem_tags, family_last):
    """正式复习的优先分与理由：遗忘风险、上次表现、近期错因、专题衔接和专题轮换。"""
    overdue = max(0, (today - due_of(state, rec)).days)
    score = 2 * math.log2(1 + min(overdue, 60))
    reasons = [f"已逾期 {overdue} 天" if overdue else "今天到期"]
    status = mastery_status(rec)
    oral = last_oral(rec)
    if oral and oral["result"] != "independent":
        score += 5
        reasons.append(f"口述复习时{ORAL_LABELS[oral['result']]}，完整重写一遍")
    elif last_result(rec) == "hinted":
        score += 5
        reasons.append("上次需要提示，先确认能否独立写出")
    elif status == "learning" and rec.get("count", 0) <= 1:
        score += 2
        reasons.append("只独立完成过 1 次，需要一次间隔验证")
    elif status == "learned":
        score -= 2
    # 专题衔接权重较高：agent.md 要求当天任务尽量同一专题、避免频繁跳转。
    if related(rec.get("topic"), current):
        score += 6
        reasons.append(f"与当前专题「{current}」衔接")
    tags = [weak[t] for t in dict.fromkeys(problem_tags.get(pid, [])) if t in weak]
    if tags:
        score += min(3, 2 * len(tags))
        top = max(tags, key=lambda t: t["count"])
        reasons.append(f"曾出现「{top['title']}」，近 4 周记录 {top['count']} 次")
    name = catalog.family(rec.get("topic"))
    seen = family_last.get(name)
    idle = (today - parse_date(seen)).days if seen else None
    if idle is not None and idle >= 7 and not related(rec.get("topic"), current):
        score += 1.5
        reasons.append(f"「{name}」已 {idle} 天没有练习，轮换回来防止遗忘")
    return round(score, 2), reasons


def build_plan(state, today, minutes=120, mentioned=None, events=None):
    """网页与命令行共用的排题逻辑；不修改进度。"""
    positive_minutes(minutes)
    mode, n_review, n_new, note = pick_mode(minutes)
    completed = state.get("completed", {})
    mentioned = mentioned or set()
    current = state.get("current_topic", "")
    done = today_records(state, today)
    events = knowledge.error_events(state) if events is None else events
    weak = weak_errors(state, today, events)
    problem_tags = {}
    for e in events:
        problem_tags.setdefault(e["problem_id"], []).append(e["tag"])
    family_last = family_last_practice(state)
    formal, short, calibration, upcoming = [], [], [], []
    recent = []
    for pid, rec in completed.items():
        last = parse_date(rec["last_done"])
        row = problem(state, pid)
        if 0 <= (today - last).days <= 2:
            recent.append(row)
        if last >= today:
            continue
        due = due_of(state, rec)
        row["overdue_days"] = max(0, (today - due).days)
        if rec.get("status") == "needs_calibration":
            calibration.append({**row, "kind": "calibration", "reason": "完成情况待核对，不计作新题"})
        elif due <= today:
            if last_result(rec) == "failed":
                short.append({**row, "kind": "recall", "reasons": ["上次未完成，先用 5～10 分钟定位错误"]})
            elif (today - last).days >= 2:
                score, reasons = review_priority(state, pid, rec, today, current, weak, problem_tags, family_last)
                formal.append({**row, "kind": "review", "score": score, "reasons": reasons})
        elif due <= today + timedelta(days=3):
            upcoming.append(row)
    formal.sort(key=lambda r: (-r["score"], r["next_due"], r["count"], int(r["id"])))
    oral_done = [{**problem(state, pid), "result": rec["oral"][-1]["result"], "next_due": rec.get("next_due")}
                 for pid, rec in completed.items() if (rec.get("oral") or [{}])[-1].get("date") == today.isoformat()]
    short.sort(key=lambda r: (r["next_due"], int(r["id"])))
    upcoming.sort(key=lambda r: (r["next_due"], int(r["id"])))
    queue_new = []
    for pid in dict.fromkeys(state.get("next_new", [])):
        if pid in completed:
            continue
        if pid in mentioned:
            calibration.append({**problem(state, pid), "kind": "calibration",
                                "reason": "日志中出现过，但尚未进入进度表，请先核对历史记录"})
        else:
            queue_new.append(pid)
    # 与当前专题相关、能在工作台验证、最近练过的旧题优先核对。
    calibration.sort(key=lambda r: (not related(r["topic"], current), not has_exercise(r["id"]),
                                    -(parse_date(r["last_done"]).toordinal() if r.get("last_done") else 0), int(r["id"])))
    # 今日已完成题占用对应名额。校准练习先填补待学不足的新题空位，否则占复习名额。
    reviews_left = n_review - sum(r["kind"] == "review" for r in done)
    new_left = n_new - sum(r["kind"] == "new" for r in done)
    for _ in [r for r in done if r["kind"] == "calibration"]:
        if len(queue_new) < new_left or reviews_left <= 0:
            new_left -= 1
        else:
            reviews_left -= 1
    reviews_left, new_left = max(0, reviews_left), max(0, new_left)
    # 保底日没有到期复习时，给一道新题，避免空计划。
    if minutes <= 45 and not formal and not done:
        new_left = 1
    picks = []
    for index, pid in enumerate(queue_new[:new_left]):
        row, known = problem(state, pid), catalog.CATALOG.get(pid)
        reasons = [f"待学队列第 {index + 1} 位"]
        if known:
            reasons.append(f"{known['difficulty']} · {catalog.frequency_label(known)}")
        if related(row["topic"], current):
            reasons.append("属于当前专题")
        picks.append({**row, "kind": "new", "recorded": False, "reasons": reasons})
    shortage = new_left - len(picks)
    extra = []
    # 待学队列不足时，先用画像推荐补足“2 道新题”名额；校准题不能挤掉新题。
    # “换一题”过的 7 天内不再推荐。
    profile = learner.build_profile(state, today, events)
    excluded = set(completed) | set(state.get("next_new", [])) | mentioned
    recommended = learner.recommend_new(state, profile, excluded | set(learner.active_skips(state, today)),
                                        limit=4 + max(0, shortage), has_exercise=has_exercise) if len(queue_new) < 3 else []
    suggested = [{**problem(state, r["id"]), "kind": "new", "source": "recommended", "recorded": False,
                  "reasons": ["为你推荐"] + r["reasons"], "tags": r["tags"]} for r in recommended[:max(0, shortage)]]
    shortage -= len(suggested)
    # 只有新题目录和推荐都无法补足时，才用校准题填补空位；校准不算新题。
    if shortage and calibration and calibration[0]["id"] in completed:
        pick = calibration[0]
        extra.append({**pick, "recorded": False, "reasons": [
            "待学队列不足，用这个名额核对旧题，不计作新题",
            "历史记录未注明是否独立完成；不看代码重做一次，按实际结果记录",
        ] + (["属于当前专题"] if related(pick["topic"], current) else [])})
        shortage -= 1
    # 正式复习先给需要完整重写的题；已经写对过两次的题放进口述复习，不占正式名额。
    written = [r for r in formal if not oral_eligible(completed[r["id"]])]
    speakable = [r for r in formal if oral_eligible(completed[r["id"]])]
    formal_picks = (written + speakable)[:reviews_left]
    picked = {r["id"] for r in formal_picks}
    oral_left = max(0, oral_slots(minutes) - len(oral_done))
    oral = [{**r, "kind": "oral", "reasons": [f"已经独立写对过 {r['count']} 次，合上代码用 2 分钟讲清思路、复杂度和一个边界"] + r["reasons"][:2]}
            for r in speakable if r["id"] not in picked][:oral_left]
    tasks = done + [{**r, "recorded": False} for r in formal_picks] + picks + suggested + extra
    taken = picked | {r["id"] for r in oral}
    deferred = [r for r in formal if r["id"] not in taken]
    by_topic = {}
    for row in deferred:
        name = catalog.family(row["topic"])
        by_topic[name] = by_topic.get(name, 0) + 1
    per_day = max(1, n_review)
    # 积压按两条线消化：需要重写的走正式复习名额，可口述的走口述名额。
    rest_written = sum(not oral_eligible(completed[r["id"]]) for r in deferred)
    clear_days = max(math.ceil(rest_written / per_day), math.ceil((len(deferred) - rest_written) / oral_slots(minutes)))
    last_mock = state.get("last_mock")
    return {"date": today.isoformat(), "minutes": minutes, "mode": mode, "mode_note": note,
            "current_topic": current, "tasks": tasks, "done_today": done,
            "pending_count": sum(not r.get("recorded") or r.get("result") not in ("independent", "hinted") for r in tasks),
            "short_recall": short, "reviews": formal, "deferred": deferred,
            "calibration": calibration, "upcoming": upcoming, "recent": recent,
            "new_shortage": max(0, shortage),
            "candidates": [r for r in recommended if r["id"] not in {s["id"] for s in suggested}][:4],
            "profile": profile,
            "oral": oral, "oral_done": oral_done, "oral_slots": oral_slots(minutes),
            "backlog": {"count": len(deferred), "per_day": per_day, "oral_per_day": oral_slots(minutes), "clear_days": clear_days,
                        "oral_ready": len(deferred) - rest_written,
                        "by_topic": dict(sorted(by_topic.items(), key=lambda kv: -kv[1]))},
            "weak_errors": sorted(weak.values(), key=lambda w: (-w["count"], w["id"])),
            "mock_due": not last_mock or (today - parse_date(last_mock)).days >= 7, "last_mock": last_mock,
            "mock_candidates": mock_candidates(state, excluded),
            "session": state.get("session", {})}


def mock_candidates(state, excluded, limit=3):
    """模拟面试选题：已学专题里没做过、工作台能验证的题，优先高频 Medium。"""
    families = {}
    for rec in state.get("completed", {}).values():
        if rec.get("count", 0) > 0:
            name = catalog.family(rec.get("topic"))
            families[name] = families.get(name, 0) + 1
    order = {"Medium": 0, "Easy": 1, "Hard": 2}
    pool = [p for p in catalog.PROBLEMS if p["id"] not in excluded and has_exercise(p["id"])
            and families.get(catalog.family(p["topic"]), 0) >= 3]
    pool.sort(key=lambda p: (order[p["difficulty"]], -p["frequency"], -families[catalog.family(p["topic"])], int(p["id"])))
    return [{**p, "limit_minutes": MOCK_LIMITS[p["difficulty"]],
             "reason": [f"已学专题「{catalog.family(p['topic'])}」中没做过的题", f"{p['difficulty']} · {catalog.frequency_label(p)}"]}
            for p in pool[:limit]]



# ---------- today ----------

def pick_mode(minutes):
    """时间档位，对应 agent.md 第 10 条。返回 (名称, 复习数, 新题数, 备注)。"""
    if minutes <= 45:
        return "保底日", 1, 0, "复习和 1 道保底新题二选一，保持连续性即可"
    if minutes <= 90:
        return "项目较忙日", 1, 1, ""
    if minutes <= 150:
        return "普通日", 2, 2, "默认 2 道旧题复习 + 2 道新题"
    return "时间充足日", 2, 2, "默认 2 道旧题复习 + 2 道新题；可再加 1 道 Medium，或做一次限时模拟（/algo-mock）"



