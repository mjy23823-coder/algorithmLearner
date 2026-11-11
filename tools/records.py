"""练习记录与复习状态：复习间隔、掌握状态解释、记录练习结果、口述复习、历史补录与每日总结。

状态解释统一在这里（mastery_status / progress_summary），网页、图谱和命令行不另写判断。
"""
import json
import re
import shutil
from copy import deepcopy
from datetime import date, timedelta

try:
    from . import catalog, knowledge
    from .store import State, atomic_write, commit_learning_data, digest, file_lock, rotate_backup
except ImportError:
    import catalog, knowledge
    from store import State, atomic_write, commit_learning_data, digest, file_lock, rotate_backup

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



def label(pid, rec=None):
    if rec and rec.get("title"):
        return f"LC{pid} {rec['title']}（{rec.get('topic', '?')}）"
    return f"LC{pid}"



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



