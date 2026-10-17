"""能力周报：只统计有记录支持的数据，不推断没有记录的能力。

- 独立完成率只计算结果明确的练习（独立 / 提示后 / 未完成）；旧格式记录按进度表状态推断并单独计数，
  历史补录里未注明独立性的记录不计入；
- 用时只来自填写或工作台计时的记录；
- 模拟面试评分来自模拟后的自评或教练建议分，并注明来源；
- 进步证据必须是同一道题先需要提示或未完成，间隔至少两天后独立完成。
"""
from datetime import timedelta

try:
    from . import catalog, coach, knowledge
except ImportError:
    import catalog, coach, knowledge

DIMENSIONS = {"recognition": "题型识别", "communication": "沟通表达", "code": "代码正确性",
              "complexity": "复杂度分析", "time": "时间控制"}


def minutes_of(entry):
    if entry.get("elapsed_seconds"):
        return max(0.1, round(entry["elapsed_seconds"] / 60, 1))
    return entry.get("minutes")


def result_of(event):
    return event["result"] if event.get("result") in coach.RESULTS else event.get("inferred_result")


def window(events, start, end):
    rows = [e for e in events if start <= coach.parse_date(e["date"]) <= end]
    graded = [e for e in rows if result_of(e)]
    count = {key: sum(result_of(e) == key for e in graded) for key in coach.RESULTS}
    timed = [minutes_of(e) for e in rows if minutes_of(e)]
    return {"start": start.isoformat(), "end": end.isoformat(), "practices": len(rows), "graded": len(graded),
            "problems": len({e["id"] for e in rows}), "active_days": len({e["date"] for e in rows}), **count,
            "independent_rate": round(count["independent"] * 100 / len(graded)) if graded else None,
            "inferred": sum(e.get("result") not in coach.RESULTS for e in graded),
            "timed": len(timed), "avg_minutes": round(sum(timed) / len(timed), 1) if timed else None,
            "mocks": sum(bool(e.get("mock")) for e in rows)}


def mock_rows(events):
    rows = []
    for e in sorted((e for e in events if e.get("mock")), key=lambda e: e["date"]):
        review = e.get("mock_review") or {}
        rows.append({"date": e["date"], "id": e["id"], "title": e["title"], "topic": e["topic"], "result": e.get("result"),
                     "scores": review.get("scores"), "average": review.get("average"), "scored_by": review.get("scored_by"),
                     "limit_minutes": review.get("limit_minutes"), "minutes": minutes_of(e), "overtime": review.get("overtime"),
                     "help_used": review.get("help_used"), "improve": review.get("improve") or e.get("note", "")})
    return rows


def dimension_summary(mocks):
    scored = [m for m in mocks if m["scores"]]
    summary = []
    for key, title in DIMENSIONS.items():
        values = [m["scores"][key] for m in scored]
        summary.append({"id": key, "title": title, "latest": values[-1] if values else None,
                        "previous": values[-2] if len(values) > 1 else None,
                        "average": round(sum(values[-4:]) / len(values[-4:]), 1) if values else None})
    return summary


def progress_evidence(state, limit=8):
    """先需要提示或未完成，间隔至少两天后独立完成的题目。"""
    found = []
    for pid, rec in state.get("completed", {}).items():
        history = rec.get("history") or []
        for i, later in enumerate(history):
            if later.get("result") != "independent":
                continue
            earlier = next((e for e in reversed(history[:i]) if e.get("result") in ("hinted", "failed")), None)
            if earlier and (coach.parse_date(later["date"]) - coach.parse_date(earlier["date"])).days >= 2:
                found.append({"id": pid, "title": rec["title"], "topic": rec["topic"],
                              "from": {"date": earlier["date"], "result": earlier["result"], "note": earlier.get("note", "")},
                              "to": {"date": later["date"], "note": later.get("note", "")}})
                break
    return sorted(found, key=lambda f: f["to"]["date"], reverse=True)[:limit]


def error_trends(state, today, events):
    weak = coach.weak_errors(state, today, events)
    questions = {e["id"]: e["question"] for e in knowledge.ERRORS}
    completed = state.get("completed", {})
    rows = []
    for tag, row in sorted(weak.items(), key=lambda kv: (-kv[1]["count"], kv[0])):
        # 出现错因后又独立完成的同一道题，作为“已在改善”的证据。
        fixed = []
        for e in events:
            if e["tag"] != tag:
                continue
            later = [h for h in completed.get(e["problem_id"], {}).get("history", [])
                     if h.get("result") == "independent" and h["date"] > e["date"]]
            if later:
                fixed.append({"id": e["problem_id"], "error_date": e["date"], "fixed_date": later[0]["date"]})
        rows.append({**row, "question": questions.get(tag, ""), "improved": list({f["id"]: f for f in fixed}.values())})
    return rows


def topic_summary(state, today):
    topics = {}
    for pid, rec in state.get("completed", {}).items():
        name = catalog.family(rec.get("topic"))
        row = topics.setdefault(name, {"name": name, "total": 0, "learned": 0, "needs_review": 0, "calibration": 0, "due": 0})
        status = coach.mastery_status(rec)
        row["total"] += 1
        row["learned"] += status == "learned"
        row["needs_review"] += status == "needs_review"
        row["calibration"] += status == "needs_calibration"
        row["due"] += coach.review_state(state, rec, today) in ("due", "overdue")
    order = {name: i for i, name in enumerate(catalog.MAIN_LINE)}
    return sorted(topics.values(), key=lambda t: (order.get(t["name"], 99), t["name"]))


def ability_report(state, today, log_path=None):
    events = coach.practice_events(state)
    week = window(events, today - timedelta(days=6), today)
    previous = window(events, today - timedelta(days=13), today - timedelta(days=7))
    month = window(events, today - timedelta(days=27), today)
    mocks = mock_rows(events)
    error_events = knowledge.error_events(state, log_path)
    plan = coach.build_plan(state, today, 120, coach.log_mentions(log_path) if log_path else None, error_events)
    workbench = [e for e in events if e.get("validation") and today - timedelta(days=27) <= coach.parse_date(e["date"])]
    explained = [e for e in workbench if all((e.get(k) or "").strip() for k in ("idea", "boundary", "time_complexity", "takeaway"))]
    errors = error_trends(state, today, error_events)
    report = {"date": today.isoformat(), "week": week, "previous_week": previous, "month": month,
              "mocks": mocks[-6:], "mock_total": len(mocks), "dimensions": dimension_summary(mocks),
              "expression": {"workbench": len(workbench), "complete": len(explained)},
              "errors": errors, "progress": progress_evidence(state), "topics": topic_summary(state, today),
              "backlog": plan["backlog"], "calibration": len(plan["calibration"]), "mock_candidates": plan["mock_candidates"],
              "last_mock": plan["last_mock"]}
    report["gaps"] = data_gaps(report)
    report["focus"] = next_focus(report, plan)
    return report


def data_gaps(report):
    gaps = []
    month = report["month"]
    if month["practices"] and not month["timed"]:
        gaps.append("近 4 周的练习都没有记录用时，平均用时暂时无法统计。")
    elif month["timed"] < month["practices"]:
        gaps.append(f"近 4 周 {month['practices']} 次练习中只有 {month['timed']} 次记录了用时，平均用时只代表这部分。")
    if month["inferred"]:
        gaps.append(f"{month['inferred']} 次是旧格式记录，没有逐次结果，完成情况按进度表状态推断。")
    if month["practices"] > month["graded"]:
        gaps.append(f"{month['practices'] - month['graded']} 次是历史补录，未注明是否独立完成，不计入独立完成率。")
    if not report["mock_total"]:
        gaps.append("还没有模拟面试记录，五个面试维度暂时无法评估。")
    elif not any(m["scores"] for m in report["mocks"]):
        gaps.append("已有的模拟记录没有分维度评分；用面板“模拟面试”完成一次即可开始追踪。")
    if not report["expression"]["workbench"]:
        gaps.append("近 4 周没有工作台练习记录，思路表达完整度暂时无法统计。")
    return gaps


def next_focus(report, plan):
    focus = []
    if report["errors"]:
        top = report["errors"][0]
        ids = "、".join("LC" + pid for pid in top["problem_ids"][:3])
        focus.append(f"复习时重点检查「{top['title']}」（近 4 周 {top['count']} 次，涉及 {ids}）：{top['question']}")
    if plan["mock_due"]:
        pick = report["mock_candidates"][0] if report["mock_candidates"] else None
        focus.append("本周安排 1 次限时模拟" + (f"，可选 LC{pick['id']} {pick['title']}（{pick['limit_minutes']} 分钟）" if pick else "") + "。")
    week = report["week"]
    if week["graded"] >= 3 and week["independent_rate"] is not None and week["independent_rate"] < 50:
        focus.append(f"本周独立完成率 {week['independent_rate']}%：新题先完成“讲题型、讲变量、走例子”三步再写代码，卡住时先看第 1 层提示。")
    backlog = report["backlog"]
    if backlog["count"] > 7:
        topics = "、".join(f"{k} {v}" for k, v in list(backlog["by_topic"].items())[:2])
        focus.append(f"复习积压 {backlog['count']} 道（{topics}），时间充足日选 180 分钟档，每天多清 1 道。")
    if report["calibration"]:
        focus.append(f"还有 {report['calibration']} 道旧题待校准，待学不足时会用空余名额逐步核对。")
    if week["practices"] and week["timed"] * 2 < week["practices"]:
        focus.append("多数练习没有记录用时；在工作台开始计时，逐步建立面试时间感。")
    return focus[:5]


def pct(value):
    return "—" if value is None else f"{value}%"


def to_markdown(report):
    week, previous = report["week"], report["previous_week"]
    lines = [f"# 算法能力周报｜{week['start']} ～ {week['end']}", "",
             "## 本周概览", "",
             "| 指标 | 本周 | 上周 |", "| --- | --- | --- |",
             f"| 学习日 | {week['active_days']} | {previous['active_days']} |",
             f"| 练习次数（涉及题目） | {week['practices']}（{week['problems']}） | {previous['practices']}（{previous['problems']}） |",
             f"| 独立完成率（有结果的练习） | {pct(week['independent_rate'])}（{week['graded']} 次） | {pct(previous['independent_rate'])}（{previous['graded']} 次） |",
             f"| 平均用时（有记录的练习） | {week['avg_minutes'] or '—'} 分钟（{week['timed']} 次） | {previous['avg_minutes'] or '—'} 分钟（{previous['timed']} 次） |",
             f"| 限时模拟 | {week['mocks']} | {previous['mocks']} |", ""]
    lines += ["## 下周重点", ""] + [f"- {item}" for item in report["focus"] or ["保持当前节奏，按复习队列推进。"]] + [""]
    if report["mocks"]:
        lines += ["## 模拟面试", "", "| 日期 | 题目 | 用时 / 限时 | " + " | ".join(DIMENSIONS.values()) + " |",
                  "| --- | --- | --- | " + " | ".join("---" for _ in DIMENSIONS) + " |"]
        for m in report["mocks"]:
            scores = " | ".join(str(m["scores"][k]) if m["scores"] else "—" for k in DIMENSIONS)
            lines.append(f"| {m['date']} | LC{m['id']} {m['title']} | {m['minutes'] or '—'} / {m['limit_minutes'] or '—'} 分钟 | {scores} |")
        lines.append("")
    if report["errors"]:
        lines += ["## 近期反复错因", ""]
        for e in report["errors"]:
            improved = "；之后已独立完成：" + "、".join(f"LC{f['id']}（{f['fixed_date']}）" for f in e["improved"]) if e["improved"] else ""
            lines.append(f"- **{e['title']}**：近 4 周 {e['count']} 次，最近 {e['last_seen']}，涉及 " + "、".join("LC" + p for p in e["problem_ids"]) + improved)
        lines.append("")
    if report["progress"]:
        lines += ["## 有记录支持的进步", ""]
        for p in report["progress"]:
            lines.append(f"- LC{p['id']} {p['title']}：{p['from']['date']} {coach.RESULTS[p['from']['result']]} → {p['to']['date']} 独立完成")
        lines.append("")
    lines += ["## 专题进度", "", "| 专题 | 已记录 | 已掌握 | 需巩固 | 待校准 | 到期复习 |", "| --- | --- | --- | --- | --- | --- |"]
    lines += [f"| {t['name']} | {t['total']} | {t['learned']} | {t['needs_review']} | {t['calibration']} | {t['due']} |" for t in report["topics"]]
    if report["gaps"]:
        lines += ["", "## 数据说明", ""] + [f"- {g}" for g in report["gaps"]]
    return "\n".join(lines) + "\n"
