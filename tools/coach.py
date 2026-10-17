#!/usr/bin/env python3
"""算法学习教练的状态工具：计算复习队列、生成今日计划、记录练习结果。

learning-state.json 是唯一的进度来源；复习日期、完成次数、状态都通过本脚本更新，
不要手算或手改这些字段。

用法示例：
    python tools/coach.py today --minutes 120
    python tools/coach.py done 42 --result hinted --title 接雨水 --topic 双指针 --note "左右最大值更新顺序写反"
    python tools/coach.py status
    python tools/coach.py queue
    python tools/coach.py new add 11 239
    python tools/coach.py fix 209 --count 2 --status learning
    python tools/coach.py session --next-action "先复写 LC42，再进入单调栈"
"""
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

try:
    from . import catalog, knowledge
except ImportError:
    import catalog, knowledge

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE = ROOT / "learning-state.json"

RESULTS = {"independent": "独立完成", "hinted": "需要提示", "failed": "未完成"}
STATUSES = {
    "learning": "已独立完成，待间隔验证",
    "learned": "连续两次独立完成",
    "needs_review": "依赖提示或未完成",
    "needs_calibration": "记录不确定，待校准",
}

CATALOG = {
    "11": ("盛最多水的容器", "双指针"),
    "42": ("接雨水", "双指针"),
    "209": ("长度最小的子数组", "滑动窗口"),
    "239": ("滑动窗口最大值", "单调队列"),
}


class State(dict):
    """保留读取时的版本，避免网页和聊天教练互相覆盖进度。"""
    source_hash = None


def digest(data):
    return hashlib.sha256(data).hexdigest()


@contextmanager
def file_lock(path):
    lock = path.with_name(path.name + ".lock")
    deadline = time.monotonic() + 5
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValueError("记录正在被其他程序更新，请稍后重试；若程序异常退出，请检查 .lock 文件")
            time.sleep(0.05)
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def atomic_write(path, data):
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, str(path))
    finally:
        if os.path.exists(name):
            os.unlink(name)


# ---------- 读写 ----------

def load(path):
    raw = path.read_bytes()
    state = State(json.loads(raw.decode("utf-8-sig")))
    state.source_hash = digest(raw)
    return state


def save(path, state):
    data = (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with file_lock(path):
        expected = getattr(state, "source_hash", None)
        if expected and (not path.exists() or digest(path.read_bytes()) != expected):
            raise ValueError("学习记录已被其他会话更新，请刷新后重试")
        if path.exists():
            shutil.copyfile(path, path.with_name(path.name + ".bak"))
            rotate_backup(path)
        atomic_write(path, data)
    if isinstance(state, State):
        state.source_hash = digest(data)


BACKUP_DAYS = 14


def rotate_backup(path, today=None):
    """每天第一次写入前，把当天开始时的进度存到 backups/，只保留最近 14 天（.bak 只保留上一次写入前的版本）。"""
    folder = path.parent / "backups"
    folder.mkdir(exist_ok=True)
    target = folder / f"{path.stem}-{(today or date.today()).isoformat()}{path.suffix}"
    if not target.exists():
        shutil.copyfile(path, target)
    for old in sorted(folder.glob(f"{path.stem}-????-??-??{path.suffix}"))[:-BACKUP_DAYS]:
        old.unlink()


def parse_date(s):
    return date.fromisoformat(s)


# ---------- 复习间隔 ----------

def interval(state, stage):
    """第 stage 个复习节点的间隔天数；超出配置后按最后一档翻倍。"""
    days = state.get("review_intervals_days") or [3, 7, 21]
    if any(type(n) is not int or n <= 0 for n in days):
        raise ValueError("复习间隔必须是正整数天数")
    stage = max(0, stage)
    if stage < len(days):
        return days[stage]
    return days[-1] * 2 ** (stage - len(days) + 1)


def stage_of(rec):
    """已通过的间隔节点数。旧记录没有 stage 字段时按完成次数推算。"""
    if "stage" in rec:
        return rec["stage"]
    if rec.get("status") in ("needs_review", "needs_calibration"):
        return 0
    return max(rec.get("count", 1) - 1, 0)


def due_of(state, rec):
    if rec.get("next_due"):
        return parse_date(rec["next_due"])
    return parse_date(rec["last_done"]) + timedelta(days=interval(state, stage_of(rec)))


def last_result(rec):
    history = rec.get("history") or []
    return history[-1]["result"] if history else None


def mastery_status(rec):
    """唯一的掌握状态口径。只解释旧记录，不改写历史标记。"""
    status = rec.get("status", "new")
    if status == "learned" and rec.get("count", 0) < 2:
        return "learning"
    return status


def review_state(state, rec, today):
    if not rec:
        return "not_started"
    if mastery_status(rec) == "needs_calibration":
        return "needs_calibration"
    if rec.get("last_done") == today.isoformat():
        return "practiced_today"
    due = due_of(state, rec)
    return "overdue" if due < today else "due" if due == today else "scheduled"


def progress_summary(state, today):
    completed = state.get("completed", {})
    by_status, by_topic = {}, {}
    for pid, rec in completed.items():
        by_status.setdefault(mastery_status(rec), []).append(pid)
        by_topic.setdefault(rec.get("topic", "待分类"), []).append(pid)
    return {"recorded": len(completed), "learned": len(by_status.get("learned", [])),
            "needs_calibration": len(by_status.get("needs_calibration", [])),
            "by_status": by_status, "by_topic": by_topic,
            "due": sum(review_state(state, rec, today) in ("due", "overdue") for rec in completed.values())}


def related(topic, current):
    return catalog.related(topic, current)


def refresh_next_review(state):
    completed = state.get("completed", {})
    state["next_review"] = sorted(completed, key=lambda p: (due_of(state, completed[p]), p))


def problem_id(value):
    value = str(value).strip()
    if not re.fullmatch(r"[1-9][0-9]{0,5}", value):
        raise ValueError("题号必须是 1～999999 的整数，例如 42")
    return value


def positive_minutes(value):
    if type(value) is not int or not 1 <= value <= 1440:
        raise ValueError("学习时间应为 1～1440 分钟的整数")
    return value


def log_mentions(path):
    if not path or not path.exists():
        return set()
    return set(re.findall(r"\b(?:LC|LeetCode)\s*(\d+)\b", path.read_text(encoding="utf-8-sig"), re.I))


def problem(state, pid):
    rec = state.get("completed", {}).get(pid, {})
    known = catalog.CATALOG.get(pid)
    title, topic = CATALOG.get(pid) or ((known["title"], known["topic"]) if known else ("待填写题名", state.get("current_topic", "")))
    return {"id": pid, "title": rec.get("title", title), "topic": rec.get("topic", topic),
            "count": rec.get("count", 0), "status": mastery_status(rec),
            "stored_status": rec.get("status", "new"), "display_status": mastery_status(rec),
            "practiced": bool(rec), "completion_confirmed": rec.get("count", 0) > 0,
            "count_is_lower_bound": rec.get("count_is_lower_bound", False),
            "history_import": rec.get("history_import"),
            "last_done": rec.get("last_done"),
            "next_due": due_of(state, rec).isoformat() if rec else None,
            "note": (rec.get("history") or [{}])[-1].get("note", "")}


def today_records(state, today):
    rows = []
    for pid, rec in state.get("completed", {}).items():
        if rec.get("last_done") != today.isoformat():
            continue
        history = rec.get("history") or []
        entry = history[-1] if history and history[-1].get("date") == today.isoformat() else {}
        result = entry.get("result")
        if not result:
            result = {"learned": "independent", "learning": "independent", "needs_review": "hinted"}.get(rec.get("status"), "unknown")
        rows.append({**problem(state, pid), "result": result,
                     "kind": entry.get("kind", "review" if rec.get("count", 0) > 1 else "new"),
                     "minutes": entry.get("minutes"), "recorded": True})
    return rows


WEAK_WINDOW_DAYS = 28
MOCK_LIMITS = {"Easy": 15, "Medium": 25, "Hard": 35}


def has_exercise(pid):
    try:
        from . import problem_bank
    except ImportError:
        import problem_bank
    return pid in problem_bank.BANK


def weak_errors(state, today, events=None):
    """近期反复出现的错因：28 天内至少两次，或 7 天内刚出现过。只来自日志证据和主动复盘。"""
    events = knowledge.error_events(state) if events is None else events
    titles = {e["id"]: e["title"] for e in knowledge.ERRORS}
    stats = {}
    for e in events:
        if not 0 <= (today - parse_date(e["date"])).days <= WEAK_WINDOW_DAYS:
            continue
        row = stats.setdefault(e["tag"], {"id": e["tag"], "title": titles.get(e["tag"], e["tag"]), "count": 0,
                                          "last_seen": e["date"], "problem_ids": []})
        row["count"] += 1
        row["last_seen"] = max(row["last_seen"], e["date"])
        if e["problem_id"] not in row["problem_ids"]:
            row["problem_ids"].append(e["problem_id"])
    return {tag: row for tag, row in stats.items()
            if row["count"] >= 2 or (today - parse_date(row["last_seen"])).days <= 7}


ORAL_LABELS = {"independent": "讲清楚了", "hinted": "有卡顿", "failed": "讲不出"}


def last_oral(rec):
    """最近一次口述复习（只算最近一次写代码之后的）。"""
    oral = (rec or {}).get("oral") or []
    if oral and oral[-1]["date"] >= (rec.get("last_done") or ""):
        return oral[-1]
    return None


def oral_eligible(rec):
    """已经独立写对过至少两次、最近一次写代码是独立完成的题，可以用 2 分钟口述代替完整重写。
    口述卡住后要先完整重写一次，才能再口述。"""
    if not rec or mastery_status(rec) not in ("learned", "learning") or rec.get("count", 0) < 2:
        return False
    if last_result(rec) not in ("independent", None):
        return False
    oral = last_oral(rec)
    return not (oral and oral["result"] != "independent")


def oral_slots(minutes):
    """口述复习不占正式复习名额：保底日和忙碌日 1 道，普通日 2 道，时间充足日 3 道。"""
    return 1 if minutes <= 90 else 2 if minutes <= 150 else 3


ORAL_ITEMS = ("recognition", "idea", "complexity", "boundary")


def oral_detail(detail):
    """口述记录可以附上讲解原文和 AI 的四项评分（ok / partial / missing），方便以后回看。"""
    if not detail:
        return {}
    clean = {}
    text = detail.get("explanation")
    if text is not None:
        if not isinstance(text, str) or len(text) > 2000:
            raise ValueError("口述讲解不能超过 2000 字")
        if text.strip():
            clean["explanation"] = text.strip()
    marks = detail.get("marks")
    if marks is not None:
        if not isinstance(marks, dict) or set(marks) != set(ORAL_ITEMS) or any(v not in ("ok", "partial", "missing") for v in marks.values()):
            raise ValueError("口述评分格式不正确")
        clean["marks"] = dict(marks)
    judged = detail.get("judged_by")
    if judged is not None:
        if not isinstance(judged, str) or len(judged) > 40:
            raise ValueError("评分来源格式不正确")
        clean["judged_by"] = judged
    return clean


def oral_events(state):
    return [{**entry, "id": pid} for pid, rec in state.get("completed", {}).items() for entry in rec.get("oral") or []]


def record_oral(state, pid, result, today, detail=None):
    """记录一次口述复习。只调整下次复习日期和间隔节点，不改完成次数和掌握状态（口述不能代替写代码）：
    讲清楚了进入下一个间隔；有卡顿 2 天后完整重写；讲不出第二天完整重写。同一天再次记录会更正本次结果。"""
    pid = problem_id(pid)
    if result not in RESULTS:
        raise ValueError("口述结果只能是 讲清楚了（independent）、有卡顿（hinted）或 讲不出（failed）")
    rec = state.get("completed", {}).get(pid)
    if not rec:
        raise ValueError(f"LC{pid} 还没有练习记录，不能口述复习")
    oral = list(rec.get("oral") or [])
    if oral and oral[-1]["date"] == today.isoformat():
        before = oral.pop()["before"]
    else:
        if not oral_eligible(rec):
            raise ValueError(f"LC{pid} 还需要完整重写一遍，暂时不适合口述复习")
        before = {"next_due": rec.get("next_due"), "stage": rec.get("stage")}
    base = {**rec, **{k: v for k, v in before.items() if v is not None}}
    for key in ("next_due", "stage"):
        if before.get(key) is None:
            base.pop(key, None)
    if result == "independent":
        stage = stage_of(base) + 1
        base.update(stage=stage, next_due=(today + timedelta(days=interval(state, stage))).isoformat())
    else:
        base["next_due"] = (today + timedelta(days=2 if result == "hinted" else 1)).isoformat()
    entry = {"date": today.isoformat(), "result": result, "before": before}
    entry.update(oral_detail(detail))
    base["oral"] = oral + [entry]
    state["completed"][pid] = base
    refresh_next_review(state)
    return base


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
    if shortage and calibration and calibration[0]["id"] in completed:
        pick = calibration[0]
        extra.append({**pick, "recorded": False, "reasons": [
            "待学队列不足，用这个名额核对旧题，不计作新题",
            "历史记录未注明是否独立完成；不看代码重做一次，按实际结果记录",
        ] + (["属于当前专题"] if related(pick["topic"], current) else [])})
        shortage -= 1
    # 待学队列不足时，按学习画像推荐新题直接补进计划；“换一题”过的 7 天内不再推荐。
    try:
        from . import learner
    except ImportError:
        import learner
    profile = learner.build_profile(state, today, events)
    excluded = set(completed) | set(state.get("next_new", [])) | mentioned
    recommended = learner.recommend_new(state, profile, excluded | set(learner.active_skips(state, today)),
                                        limit=4 + max(0, shortage), has_exercise=has_exercise) if len(queue_new) < 3 else []
    suggested = [{**problem(state, r["id"]), "kind": "new", "source": "recommended", "recorded": False,
                  "reasons": ["为你推荐"] + r["reasons"], "tags": r["tags"]} for r in recommended[:max(0, shortage)]]
    shortage -= len(suggested)
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


def label(pid, rec=None):
    if rec and rec.get("title"):
        return f"LC{pid} {rec['title']}（{rec.get('topic', '?')}）"
    return f"LC{pid}"


# ---------- today ----------

def pick_mode(minutes):
    """时间档位，对应 agent.md 第 10 条。返回 (名称, 复习数, 新题数, 备注)。"""
    if minutes <= 45:
        return "保底日", 1, 0, "复习和 1 道保底新题二选一，保持连续性即可"
    if minutes <= 90:
        return "项目较忙日", 1, 1, ""
    if minutes <= 150:
        return "普通日", 1, 2, ""
    return "时间充足日", 2, 2, "可再加 1 道 Medium，或做一次限时模拟（/algo-mock）"


def learner_module():
    try:
        from . import learner
    except ImportError:
        import learner
    return learner


def cmd_today(state, args):
    # 没有指定时，用学习画像里设定的每日计划时间。
    args.minutes = args.minutes or learner_module().settings(state)["daily_minutes"]
    plan = build_plan(state, args.date, args.minutes, log_mentions(args.log))
    if getattr(args, "json", False):
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    print(f"日期：{plan['date']}　模式：{plan['mode']}（{args.minutes} 分钟）　专题：{plan['current_topic']}")
    print("\n【今天已记录】")
    for row in plan["done_today"]:
        print(f"  - {label(row['id'], row)}：{RESULTS.get(row['result'], '待校准')}")
    if not plan["done_today"]:
        print("  （无）")
    print("\n【今日剩余任务】已完成题目会占用今天的题量，不会不断补新题")
    pending = [r for r in plan["tasks"] if not r["recorded"] or r.get("result") not in ("independent", "hinted")]
    for row in pending:
        kind = {"review": "复习", "new": "推荐新题" if row.get("source") == "recommended" else "新题", "calibration": "校准"}.get(row["kind"], "练习")
        print(f"  - {kind}：{label(row['id'], row)}")
        if row.get("reasons"):
            print(f"      理由：{'；'.join(row['reasons'])}")
    if not pending:
        print("  （今天的任务已完成，或待学队列需要补充）")
    if plan["oral"] or plan["oral_done"]:
        print(f"\n【口述复习】每道约 2 分钟，不写代码、不占正式名额（今天最多 {plan['oral_slots']} 道）；讲完用 `oral <题号> --result ...` 记录")
        for row in plan["oral_done"]:
            print(f"  - {label(row['id'], row)}：已口述，{ORAL_LABELS[row['result']]}")
        for row in plan["oral"]:
            print(f"  - {label(row['id'], row)}：{'；'.join(row['reasons'])}")
    print("\n【短时回忆】5～10 分钟，不占正式名额")
    for row in plan["short_recall"]:
        print(f"  - {label(row['id'], row)}：上次未完成，先定位错误")
    backlog = plan["backlog"]
    if backlog["count"]:
        topics = "、".join(f"{name} {n}" for name, n in backlog["by_topic"].items())
        print(f"\n【到期但顺延】{backlog['count']} 道（{topics}），其中 {backlog['oral_ready']} 道可以口述；"
              f"按每天 {backlog['per_day']} 道正式复习 + {backlog['oral_per_day']} 道口述，约 {backlog['clear_days']} 天消化，"
              "每天按优先分重新排序；时间充足日会多安排")
        for row in plan["deferred"][:5]:
            print(f"  - {label(row['id'], row)}：{'；'.join(row['reasons'])}")
        if backlog["count"] > 5:
            print(f"  - 其余 {backlog['count'] - 5} 道见 `queue`")
    print(f"\n【待校准，不算新题】{len(plan['calibration'])} 道，每天最多用 1 个空余名额核对")
    for row in plan["calibration"][:5]:
        print(f"  - {label(row['id'], row)}：{row['reason']}")
    if plan["weak_errors"]:
        print("\n【近期反复错因】" + "、".join(f"{w['title']}（{w['count']} 次）" for w in plan["weak_errors"][:4]))
    if plan["candidates"]:
        print("\n【更多推荐新题】按学习画像挑选；`new add <题号>` 固定加入待学，`new skip <题号>` 7 天内不再推荐：")
        for row in plan["candidates"]:
            print(f"  - LC{row['id']} {row['title']}（{row['topic']}）：{'；'.join(row['reasons'])}")
    print("\n学习画像：" + "".join(plan["profile"]["summary"][:2]) + "（`profile` 查看完整画像）")
    if plan["mock_due"]:
        print("\n最近 7 天没有限时训练记录，本周可安排一次模拟（/algo-mock 或面板“模拟面试”）。")


# ---------- done ----------

def record_result(state, pid, result, today, title=None, topic=None, note="", minutes=None, mock=False):
    pid = problem_id(pid)
    if result not in RESULTS:
        raise ValueError("请选择独立完成、提示后完成或未完成")
    if minutes is not None:
        positive_minutes(minutes)
    completed = state.setdefault("completed", {})
    rec = deepcopy(completed.get(pid, {"count": 0}))
    if rec.get("last_done") and parse_date(rec["last_done"]) > today:
        raise ValueError("不能在最近练习之前追加记录；校准旧记录请使用 fix 命令")
    history = rec.get("history", [])
    same_day = rec.get("last_done") == today.isoformat()
    previous_entry = history[-1] if history and history[-1].get("date") == today.isoformat() else {}
    # 同一天的再次提交是修正本次结果，恢复当日练习前状态后重新计算。
    if same_day and "before" in previous_entry:
        before = deepcopy(previous_entry["before"])
        history = history[:-1]
    else:
        before = {k: deepcopy(v) for k, v in rec.items() if k != "history"}
        if same_day and previous_entry:
            history = history[:-1]
    title = (title or rec.get("title") or "").strip()
    topic = (topic or rec.get("topic") or "").strip()
    if not title or not topic:
        raise ValueError(f"LC{pid} 是新题，请同时提供题名和专题")
    previous_date = parse_date(before["last_done"]) if before.get("last_done") else None
    spaced = previous_date is not None and (today - previous_date).days >= 2
    prev_independent = before.get("status") in ("learned", "learning")
    previous_count = before.get("count", 0)
    is_legacy_same_day = same_day and ("before" not in previous_entry or previous_entry.get("legacy_same_day", False))
    # 缺少历史快照的旧数据当日只补注释/结果，不擅自增加次数。
    count = previous_count + int(result != "failed" and not is_legacy_same_day)
    if result == "independent":
        stage = stage_of(before) + 1 if spaced and prev_independent else 0
        if previous_date and not spaced and prev_independent:
            stage = stage_of(before)
        gap = interval(state, stage)
        status = "learned" if spaced and prev_independent else "learning"
        if not spaced and before.get("status") == "learned" and previous_count >= 2:
            status = "learned"
    elif result == "hinted":
        stage = 0
        gap = interval(state, 0)
        status = "needs_review"
    else:
        stage = 0
        gap = 1
        status = "needs_review"
    if is_legacy_same_day:
        kind = previous_entry.get("kind", "review" if previous_count > 1 else "new")
    else:
        kind = "calibration" if before.get("status") == "needs_calibration" else ("review" if previous_count else "new")
    entry = {"date": today.isoformat(), "result": result, "kind": kind, "before": before}
    if is_legacy_same_day:
        entry["legacy_same_day"] = True
    if minutes is not None:
        entry["minutes"] = minutes
    if note:
        entry["note"] = note.strip()
    if mock:
        entry["mock"] = True
        state["last_mock"] = today.isoformat()
    next_due = (today + timedelta(days=gap)).isoformat()
    if result == "independent" and previous_date and not spaced and before.get("next_due") and parse_date(before["next_due"]) > today:
        next_due = before["next_due"]
    rec = {**before, "title": title, "topic": topic, "count": count, "last_done": today.isoformat(),
           "status": status, "stage": stage, "next_due": next_due, "history": history + [entry]}
    if count and not rec.get("first_done") and not previous_count:
        rec["first_done"] = today.isoformat()
    completed[pid] = rec
    state["next_new"] = [p for p in state.get("next_new", []) if p != pid]
    session = state.setdefault("session", {})
    if session.get("last_date") != today.isoformat():
        session["last_date"] = today.isoformat()
        session["last_completed"] = []
    ids = session.setdefault("last_completed", [])
    if result != "failed" and pid not in ids:
        ids.append(pid)
    elif result == "failed" and pid in ids:
        ids.remove(pid)
    refresh_next_review(state)
    return rec


MOCK_DIMENSIONS = ("recognition", "communication", "code", "complexity", "time")


def mock_scores(text):
    """聊天教练模拟面试的五维评分，顺序：题型识别,沟通表达,代码正确性,复杂度分析,时间控制。"""
    parts = [p.strip() for p in re.split(r"[,，\s]+", text or "") if p.strip()]
    if len(parts) != 5 or not all(p in "12345" and len(p) == 1 for p in parts):
        raise ValueError("--scores 需要 5 个 1～5 的整数，顺序：题型识别,沟通表达,代码正确性,复杂度分析,时间控制")
    return dict(zip(MOCK_DIMENSIONS, map(int, parts)))


def cmd_done(state, args):
    if (args.scores or args.limit) and not args.mock:
        raise ValueError("--scores 和 --limit 只用于限时模拟，请同时加 --mock")
    scores = mock_scores(args.scores) if args.scores else None
    rec = record_result(state, args.id, args.result, args.date, args.title, args.topic,
                        args.note, args.minutes, args.mock)
    if scores:
        if args.limit is not None:
            positive_minutes(args.limit)
        rec["history"][-1]["mock_review"] = {
            "limit_minutes": args.limit, "elapsed_seconds": args.minutes * 60 if args.minutes else None,
            "overtime": bool(args.limit and args.minutes and args.minutes > args.limit), "scores": scores,
            "average": round(sum(scores.values()) / 5, 1), "scored_by": "chat_coach", "improve": (args.note or "").strip()}
    save(args.state, state)
    print(f"已记录 {label(args.id, rec)}：{RESULTS[args.result]}，累计完成 {rec['count']} 次，"
          f"状态 {rec['status']}，下次复习 {rec['next_due']}")


# ---------- status / queue ----------

def cmd_status(state, args):
    today = args.date
    completed = state.get("completed", {})
    summary = progress_summary(state, today)
    if getattr(args, "json", False):
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"目标：{state.get('goal')}　语言：{state.get('language')}　当前专题：{state.get('current_topic')}")
    print(f"已做题目：{len(completed)} 道")

    by_status, by_topic = summary["by_status"], summary["by_topic"]
    print("\n按状态：")
    for s, ids in by_status.items():
        print(f"  {s}（{STATUSES.get(s, '')}）：{len(ids)} 道　" + " ".join(f"LC{p}" for p in ids))
    print("\n按专题：")
    for t, ids in sorted(by_topic.items(), key=lambda kv: -len(kv[1])):
        print(f"  {t}：{len(ids)} 道　" + " ".join(f"LC{p}" for p in ids))

    load_7 = {}
    for rec in completed.values():
        if mastery_status(rec) == "needs_calibration":
            continue
        d = max(due_of(state, rec), today)
        if d <= today + timedelta(days=6):
            load_7[d] = load_7.get(d, 0) + 1
    print("\n未来 7 天复习量（逾期题计入今天）：")
    for i in range(7):
        d = today + timedelta(days=i)
        print(f"  {d}  {'■' * load_7.get(d, 0)} {load_7.get(d, 0)}")
    print(f"\n待学新题：{' '.join('LC' + p for p in state.get('next_new', [])) or '（空）'}")
    print(f"上次限时训练：{state.get('last_mock') or '无记录'}")


def cmd_queue(state, args):
    today = args.date
    completed = state.get("completed", {})
    rows = sorted(completed.items(), key=lambda kv: due_of(state, kv[1]))
    for pid, rec in rows:
        d = due_of(state, rec)
        diff = (d - today).days
        when = f"逾期 {-diff} 天" if diff < 0 else ("今天" if diff == 0 else f"{diff} 天后")
        if mastery_status(rec) == "needs_calibration":
            when = "待校准"
        print(f"{d}  {when:<8} {label(pid, rec)}  次数 {rec.get('count')}  {mastery_status(rec)}")


# ---------- 维护命令 ----------

def cmd_new(state, args):
    args.ids = [problem_id(p) for p in args.ids]
    queue = state.setdefault("next_new", [])
    if args.action == "skip":
        for pid in args.ids:
            learner_module().skip_recommendation(state, pid, args.date)
        save(args.state, state)
        print("7 天内不再推荐：" + " ".join("LC" + p for p in args.ids))
        return
    if args.action == "set":
        state["next_new"] = list(dict.fromkeys(args.ids))
    elif args.action == "add":
        queue.extend(p for p in args.ids if p not in queue)
    else:
        state["next_new"] = [p for p in queue if p not in args.ids]
    save(args.state, state)
    print("next_new：" + (" ".join("LC" + p for p in state["next_new"]) or "（空）"))


def cmd_oral(state, args):
    rec = record_oral(state, args.id, args.result, args.date)
    save(args.state, state)
    print(f"LC{problem_id(args.id)} 口述复习：{ORAL_LABELS[args.result]}，下次复习 {rec['next_due']}"
          + ("（完整重写）" if args.result != "independent" else ""))


def cmd_profile(state, args):
    learner = learner_module()
    changes = {}
    if args.target_date is not None:
        changes["target_date"] = args.target_date
    if args.minutes is not None:
        changes["daily_minutes"] = args.minutes
    if args.pace is not None:
        changes["pace"] = args.pace
    if changes:
        learner.apply_settings(state, changes, args.date)
        save(args.state, state)
        print("学习目标已更新。")
    profile = learner.build_profile(state, args.date)
    if args.json:
        print(json.dumps(profile, ensure_ascii=False, indent=2))
        return
    config, target = profile["settings"], profile["goal"]
    print(f"目标：{target['text']}　面试日期：{config['target_date'] or '未设置'}"
          + (f"（还有 {target['days_left']} 天）" if target["days_left"] is not None else "")
          + f"　每天 {config['daily_minutes']} 分钟　节奏：{profile['pace_label']}")
    print("\n【画像】")
    for line in profile["summary"]:
        print("  " + line)
    print("\n【专题掌握度】按结果计分，近期权重更高；记录少时显示“起步”")
    for t in profile["topics"]:
        idle = f"，{t['idle_days']} 天没练" if t["idle_days"] is not None else ""
        print(f"  - {t['name']}：{t['mastery']}%（{t['level']}）{t['problems']} 道题，{t['graded']} 次有结果，到期 {t['due']} 道{idle}")
    if profile["weaknesses"]:
        print("\n【近期反复错因】")
        for w in profile["weaknesses"]:
            print(f"  - {w['title']}（近 4 周 {w['count']} 次，" + "、".join("LC" + i for i in w["problem_ids"][:4]) + f"）：{w['question']}")
    habit = profile["habits"]
    print(f"\n【近 4 周习惯】练习 {habit['practices']} 次，独立完成率 {habit['independent_rate'] if habit['independent_rate'] is not None else '—'}%，"
          f"提示依赖 {habit['hint_rate'] if habit['hint_rate'] is not None else '—'}%，计时 {habit['timed']} 次，连续 {habit['streak']} 天，模拟 {habit['mocks']} 次")
    print("\n【接下来的重点】")
    for i, point in enumerate(profile["focus"], 1):
        print(f"  {i}. {point}")


def cmd_fix(state, args):
    args.id = problem_id(args.id)
    if args.count is not None and args.count < 0:
        raise ValueError("完成次数不能小于 0")
    completed = state.setdefault("completed", {})
    rec = completed.get(args.id)
    if rec is None:
        if not (args.title and args.topic and args.last_done):
            raise ValueError(f"LC{args.id} 不存在；补录需要 --title --topic --last-done")
        rec = completed[args.id] = {"count": 1, "status": "needs_calibration"}
    for field in ("title", "topic", "last_done", "count", "status"):
        value = getattr(args, field)
        if value is not None:
            rec[field] = value.isoformat() if isinstance(value, date) else value
    if args.count is not None:
        rec.pop("count_is_lower_bound", None)
    if args.due:
        rec["next_due"] = args.due.isoformat()
    elif any(getattr(args, f) is not None for f in ("last_done", "count", "status")):
        rec.pop("next_due", None)  # 让日期按新的次数/状态重新推算
        rec.pop("stage", None)
    refresh_next_review(state)
    save(args.state, state)
    print(f"已修正 {label(args.id, rec)}：次数 {rec.get('count')}，最近 {rec.get('last_done')}，"
          f"状态 {rec.get('status')}，下次复习 {due_of(state, rec)}")


def cmd_session(state, args):
    session = state.setdefault("session", {})
    if args.next_action is not None:
        session["next_action"] = args.next_action
    if args.clear_questions:
        session["open_questions"] = []
    for q in args.open_question or []:
        session.setdefault("open_questions", []).append(q)
    if args.topic:
        state["current_topic"] = args.topic
    save(args.state, state)
    print(json.dumps({"current_topic": state.get("current_topic"), **session}, ensure_ascii=False, indent=2))


def prepare_history_import(state, manifest, log_path, today):
    """重放已人工核对的旧日志，只补缺失题目，不覆盖当前进度。"""
    if manifest.get("schema_version") != 1:
        raise ValueError("不支持的历史核对文件版本")
    source = log_path.read_bytes()
    size = manifest.get("source_bytes")
    if type(size) is not int or size < 1 or digest(source[:size]) != manifest.get("source_sha256"):
        raise ValueError("日志与核对时的内容不同，请重新核对；仅在末尾追加日志不影响导入")
    lines = source.decode("utf-8-sig").splitlines()
    updated = deepcopy(state)
    added, skipped, seen = [], [], set()
    for item in manifest.get("records", []):
        pid = problem_id(item.get("id", ""))
        if pid in seen:
            raise ValueError(f"核对文件内题号重复：LC{pid}")
        seen.add(pid)
        if pid in updated.get("completed", {}):
            skipped.append(pid)
            continue
        title, topic = item.get("title"), item.get("topic")
        if not isinstance(title, str) or not title.strip() or not isinstance(topic, str) or not topic.strip():
            raise ValueError(f"LC{pid} 缺少题名或专题")
        events = item.get("events", [])
        if not events:
            raise ValueError(f"LC{pid} 没有可核对的练习证据")
        scratch = {"completed": {}, "review_intervals_days": updated.get("review_intervals_days", [3, 7, 21])}
        previous = None
        for event in events:
            when = parse_date(event["date"])
            result = event.get("result")
            if when > today or (previous and when <= previous):
                raise ValueError(f"LC{pid} 的历史日期需要按天去重并递增，且不能在未来")
            previous = when
            evidence = event.get("evidence", [])
            if not evidence:
                raise ValueError(f"LC{pid} 缺少日志引用")
            for quote in evidence:
                line = quote.get("line")
                if type(line) is not int or not 1 <= line <= len(lines) or lines[line - 1].strip() != quote.get("text", "").strip():
                    raise ValueError(f"LC{pid} 的日志引用无法验证：第 {line} 行")
            note = event.get("note", "")
            if result in RESULTS:
                rec = record_result(scratch, pid, result, when, title, topic, note)
            elif result == "historical":
                confirmed = event.get("completion_confirmed")
                if type(confirmed) is not bool:
                    raise ValueError(f"LC{pid} 的旧记录须注明完成情况是否明确")
                rec = scratch["completed"].setdefault(pid, {"title": title, "topic": topic, "count": 0, "history": []})
                old_count = rec["count"]
                rec.update(count=old_count + int(confirmed), last_done=when.isoformat(), status="needs_calibration",
                           stage=0, next_due=(when + timedelta(days=interval(scratch, 0))).isoformat())
                if confirmed and not rec.get("first_done"):
                    rec["first_done"] = when.isoformat()
                rec["history"].append({"date": when.isoformat(), "result": "historical", "completion_confirmed": confirmed,
                                       "kind": "review" if old_count else "new", "note": note})
            else:
                raise ValueError(f"LC{pid} 的历史结果不支持：{result}")
            rec["history"][-1]["source"] = {"file": log_path.name, "evidence": deepcopy(evidence)}
        rec["count_is_lower_bound"] = True
        rec["history_import"] = {"source": log_path.name, "audit_id": manifest.get("audit_id"),
                                 "imported_on": today.isoformat(), "note": item.get("audit_note", "完成次数仅累计日志能确认的记录；口述和建议不算完成")}
        updated.setdefault("completed", {})[pid] = rec
        added.append(pid)
    if added:
        imported = set(added)
        updated["next_new"] = [pid for pid in updated.get("next_new", []) if pid not in imported]
        refresh_next_review(updated)
    report = {"added": added, "skipped": skipped, "before": len(state.get("completed", {})),
              "after": len(updated.get("completed", {})), "topics": {}}
    for rec in updated.get("completed", {}).values():
        report["topics"][rec["topic"]] = report["topics"].get(rec["topic"], 0) + 1
    return updated, report


def cmd_import_history(state, args):
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    updated, report = prepare_history_import(state, manifest, args.log, args.date)
    if args.apply and report["added"]:
        save(args.state, updated)
    print("已补录历史记录" if args.apply else "历史补录预览（未写入）")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def practice_events(state):
    """只使用可追溯的日期，旧记录只有最近一次日期时不虚构完整历史。"""
    events = []
    for pid, rec in state.get("completed", {}).items():
        history = rec.get("history") or []
        for entry in history:
            events.append({**entry, "id": pid, "title": rec["title"], "topic": rec["topic"]})
        if rec.get("last_done") and not any(e["date"] == rec["last_done"] for e in history):
            # 旧记录只有最近一次日期和状态；与今日计划相同，按状态推断这一次的结果并单独标注。
            inferred = {"learned": "independent", "learning": "independent", "needs_review": "hinted"}.get(rec.get("status"))
            events.append({"date": rec["last_done"], "id": pid, "title": rec["title"],
                           "topic": rec["topic"], "result": "historical", "inferred_result": inferred})
    return events


def weekly_report(state, today):
    start = today - timedelta(days=6)
    events = [e for e in practice_events(state) if start <= parse_date(e["date"]) <= today]
    notes = [{"id": e["id"], "title": e["title"], "note": e["note"], "date": e["date"]}
             for e in events if e.get("note")]
    return {"start": start.isoformat(), "end": today.isoformat(), "practices": len(events),
            "active_days": len({e["date"] for e in events}), "problems": len({e["id"] for e in events}),
            "minutes": round(sum(e.get("elapsed_seconds", e.get("minutes", 0)*60) for e in events)/60, 1),
            "independent": sum(e.get("result") == "independent" for e in events),
            "hinted": sum(e.get("result") == "hinted" for e in events),
            "failed": sum(e.get("result") == "failed" for e in events),
            "historical": sum(e.get("result") == "historical" for e in events),
            "mock_count": sum(bool(e.get("mock")) for e in events), "notes": notes,
            "coverage": "仅统计有明确日期的练习记录；历史补录按日志证据计数，未注明独立性的记录不推断独立完成率。"}


def wrap_session(state, state_path, log_path, today, note="", next_action=None):
    rows = today_records(state, today)
    if not rows and not note.strip():
        raise ValueError("今天还没有练习记录；请先记录一道题，或填写今日复盘")
    session = state.setdefault("session", {})
    if next_action is not None:
        session["next_action"] = next_action.strip()
    next_text = session.get("next_action") or "按到期复习队列继续"
    key = digest(json.dumps({"date": today.isoformat(), "topic": state.get("current_topic"), "rows": rows, "note": note.strip(),
                             "next": next_text}, ensure_ascii=False, sort_keys=True).encode("utf-8"))[:20]
    marker = f"<!-- algo-wrap:{key} -->"
    lines = [f"\n\n## {today.isoformat()}｜{state.get('current_topic', '算法学习')}（学习总结）", "", marker, ""]
    for row in rows:
        result = RESULTS.get(row["result"], "完成情况待校准")
        lines.append(f"- **LC{row['id']} {row['title']}**：{result}；累计完成 {row['count']} 次；下次复习 {row['next_due']}。")
        if row.get("note"):
            lines.append("  - 卡点 / 收获：" + " ".join(row["note"].splitlines()))
    if note.strip():
        lines.append("- **今日复盘**：" + " ".join(note.strip().splitlines()))
    lines.append("- **下一步**：" + " ".join(next_text.splitlines()))
    text = "\n".join(lines) + "\n"
    # 日志仅追加，保存原始字节和换行；相同总结有固定标识，重试不会重复写。
    with file_lock(state_path), file_lock(log_path):
        original_state = state_path.read_bytes()
        if getattr(state, "source_hash", None) and digest(original_state) != state.source_hash:
            raise ValueError("学习记录已被其他会话更新，请刷新后重试")
        existed = log_path.exists()
        old = log_path.read_bytes() if log_path.exists() else b""
        if marker.encode() in old:
            return {"saved": False, "message": "这份学习总结已经保存", "text": text}
        new_state = (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        shutil.copyfile(state_path, state_path.with_name(state_path.name + ".bak"))
        rotate_backup(state_path)
        if existed:
            shutil.copyfile(log_path, log_path.with_name(log_path.name + ".bak"))
        atomic_write(log_path, old + text.encode("utf-8"))
        try:
            atomic_write(state_path, new_state)
        except OSError:
            if existed:
                atomic_write(log_path, old)
            else:
                log_path.unlink()
            raise
        if isinstance(state, State):
            state.source_hash = digest(new_state)
    snapshot = commit_learning_data(state_path.parent, today)
    return {"saved": True, "message": "学习总结已保存，下次从当前进度继续" + (f"；{snapshot}" if snapshot else ""), "text": text,
            "git": snapshot}


LEARNING_DATA = ("learning-state.json", "learning-log.md", "solutions")


def commit_learning_data(root, today):
    """在本地 git 仓库里提交当天的学习数据（进度、日志、运行过的代码）。只提交这几项，不动其他改动；
    没有仓库、没有变化或 git 出错时跳过，不影响保存。仓库不配置远程，数据不会上传。"""
    root = Path(root)
    if not (root / ".git").exists() or not shutil.which("git"):
        return None
    paths = [name for name in LEARNING_DATA if (root / name).exists()]

    def git(*args):
        return subprocess.run(["git", *args], cwd=str(root), capture_output=True, timeout=30,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        if git("add", "--", *paths).returncode:
            return None
        if not git("diff", "--cached", "--quiet", "--", *paths).returncode:
            return "学习数据没有新变化，无需提交"
        done = git("commit", "-q", "-m", f"学习记录 {today.isoformat()}", "--", *paths)
        return "已提交到本地 git" if done.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def cmd_wrap(state, args):
    result = wrap_session(state, args.state, args.log, args.date, args.note, args.next_action)
    print(result["message"])
    print(result["text"])


def cmd_weekly(state, args):
    try:
        from . import insights
    except ImportError:
        import insights
    report = insights.ability_report(state, args.date, args.log)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if args.markdown:
        print(insights.to_markdown(report))
        return
    week = weekly_report(state, args.date)
    print(f"周复盘｜{week['start']} ～ {week['end']}")
    print(f"学习 {week['active_days']} 天，练习 {week['practices']} 次，涉及 {week['problems']} 道题")
    rate = report["week"]["independent_rate"]
    print(f"独立完成率 {'—' if rate is None else str(rate) + '%'}（有结果的 {report['week']['graded']} 次），"
          f"已记录用时 {week['minutes']} 分钟，限时训练 {week['mock_count']} 次")
    for item in week["notes"]:
        print(f"- LC{item['id']}：{item['note']}")
    print("\n下周重点：")
    for item in report["focus"] or ["保持当前节奏，按复习队列推进。"]:
        print(f"  - {item}")
    for gap in report["gaps"]:
        print(f"说明：{gap}")
    print("完整周报：python tools/coach.py weekly --markdown")


# ---------- 入口 ----------

def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--state", type=Path, default=DEFAULT_STATE, help="状态文件路径")
    common.add_argument("--date", type=parse_date, default=date.today(), help="按指定日期计算，默认今天")
    common.add_argument("--log", type=Path, help="学习日志路径，默认与进度文件同目录")

    parser = argparse.ArgumentParser(description="算法学习教练状态工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("today", parents=[common], help="生成今日计划")
    p.add_argument("--minutes", type=int, help="今天可用分钟数，默认用学习画像里的每日计划时间（初始 120）")
    p.add_argument("--json", action="store_true", help="输出结构化计划")
    p.set_defaults(func=cmd_today)

    p = sub.add_parser("done", parents=[common], help="记录一次练习")
    p.add_argument("id", help="LeetCode 题号")
    p.add_argument("--result", required=True, choices=RESULTS)
    p.add_argument("--title")
    p.add_argument("--topic")
    p.add_argument("--note", help="卡点或错因，一句话")
    p.add_argument("--minutes", type=int)
    p.add_argument("--mock", action="store_true", help="本次是限时模拟")
    p.add_argument("--scores", help="模拟面试五维评分，如 4,3,4,4,5（题型识别,沟通表达,代码正确性,复杂度分析,时间控制）")
    p.add_argument("--limit", type=int, help="模拟面试限时（分钟）")
    p.set_defaults(func=cmd_done)

    p = sub.add_parser("status", parents=[common], help="总体进度")
    p.add_argument("--json", action="store_true", help="输出与网页相同口径的统计")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("queue", parents=[common], help="完整复习排期")
    p.set_defaults(func=cmd_queue)

    p = sub.add_parser("new", parents=[common], help="维护待学新题队列")
    p.add_argument("action", choices=["add", "remove", "set", "skip"], help="skip：换掉推荐，7 天内不再推荐")
    p.add_argument("ids", nargs="*")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("oral", parents=[common], help="记录一次口述复习（已写对过两次的题，2 分钟讲清思路）")
    p.add_argument("id")
    p.add_argument("--result", required=True, choices=RESULTS, help="independent 讲清楚了 / hinted 有卡顿 / failed 讲不出")
    p.set_defaults(func=cmd_oral)

    p = sub.add_parser("profile", parents=[common], help="学习画像；带参数时更新学习目标")
    p.add_argument("--target-date", help="目标面试日期 YYYY-MM-DD，none 表示不设")
    p.add_argument("--minutes", type=int, help="每天计划学习分钟数")
    p.add_argument("--pace", choices=["steady", "normal", "push"], help="节奏：steady 稳扎稳打 / normal 正常推进 / push 冲刺加速")
    p.add_argument("--json", action="store_true", help="输出结构化画像")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("fix", parents=[common], help="校准一道题的记录")
    p.add_argument("id")
    p.add_argument("--title")
    p.add_argument("--topic")
    p.add_argument("--last-done", type=parse_date)
    p.add_argument("--count", type=int)
    p.add_argument("--status", choices=STATUSES)
    p.add_argument("--due", type=parse_date, help="直接指定下次复习日期")
    p.set_defaults(func=cmd_fix)

    p = sub.add_parser("session", parents=[common], help="更新会话备注")
    p.add_argument("--next-action")
    p.add_argument("--open-question", action="append")
    p.add_argument("--clear-questions", action="store_true")
    p.add_argument("--topic", help="切换当前专题")
    p.set_defaults(func=cmd_session)

    p = sub.add_parser("wrap", parents=[common], help="追加当日总结，重复执行不会重复写入")
    p.add_argument("--note", default="", help="今日收获或卡点")
    p.add_argument("--next-action", default=None)
    p.set_defaults(func=cmd_wrap)

    p = sub.add_parser("weekly", parents=[common], help="最近 7 天复盘与能力周报")
    p.add_argument("--json", action="store_true", help="输出结构化能力周报")
    p.add_argument("--markdown", action="store_true", help="输出可保存的 Markdown 周报")
    p.set_defaults(func=cmd_weekly)

    p = sub.add_parser("import-history", parents=[common], help="预览或补录经核对的历史题目；保留已有记录")
    p.add_argument("--manifest", type=Path, required=True, help="含日志引用的历史核对文件")
    p.add_argument("--apply", action="store_true", help="保存已验证的补录结果，默认只预览")
    p.set_defaults(func=cmd_import_history)

    args = parser.parse_args(argv)
    args.log = args.log or args.state.with_name("learning-log.md")
    try:
        args.func(load(args.state), args)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"错误：{exc}\n")


if __name__ == "__main__":
    main()
