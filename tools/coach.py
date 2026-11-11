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
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

# 实现按层拆分：store（存储）→ records（记录与复习状态）→ planner（排题）。
# 本文件只保留命令行，并重新导出原有函数，外部仍可用 coach.xxx 调用。
try:
    from . import insights, learner
    from .store import *  # noqa: F401,F403
    from .records import *  # noqa: F401,F403
    from .planner import *  # noqa: F401,F403
except ImportError:
    import insights, learner
    from store import *  # noqa: F401,F403
    from records import *  # noqa: F401,F403
    from planner import *  # noqa: F401,F403

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE = ROOT / "learning-state.json"


def cmd_today(state, args):
    # 没有指定时，用学习画像里设定的每日计划时间。
    args.minutes = args.minutes or learner.settings(state)["daily_minutes"]
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
            learner.skip_recommendation(state, pid, args.date)
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



def cmd_import_history(state, args):
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    updated, report = prepare_history_import(state, manifest, args.log, args.date)
    if args.apply and report["added"]:
        save(args.state, updated)
    print("已补录历史记录" if args.apply else "历史补录预览（未写入）")
    print(json.dumps(report, ensure_ascii=False, indent=2))




def cmd_wrap(state, args):
    result = wrap_session(state, args.state, args.log, args.date, args.note, args.next_action)
    print(result["message"])
    print(result["text"])


def cmd_weekly(state, args):
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

