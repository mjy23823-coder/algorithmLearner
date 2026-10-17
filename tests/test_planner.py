import unittest
from copy import deepcopy
from datetime import date, timedelta

from tools import catalog, coach, insights

TODAY = date(2026, 10, 17)


def state_with(current="双指针与滑动窗口", next_new=None):
    return {"completed": {}, "next_new": list(next_new or []), "review_intervals_days": [3, 7, 21],
            "current_topic": current, "session": {}}


def practice(state, pid, title, topic, result, days_ago, **kwargs):
    return coach.record_result(state, pid, result, TODAY - timedelta(days=days_ago), title, topic, **kwargs)


class ReviewPriorityTests(unittest.TestCase):
    def test_current_topic_hinted_review_beats_older_unrelated_backlog(self):
        state = state_with()
        practice(state, "226", "翻转二叉树", "二叉树", "independent", 25)
        practice(state, "11", "盛最多水的容器", "双指针", "hinted", 6)
        plan = coach.build_plan(state, TODAY, 120, events=[])
        review = next(t for t in plan["tasks"] if t["kind"] == "review")
        self.assertEqual(review["id"], "11")
        self.assertIn("上次需要提示，先确认能否独立写出", review["reasons"])
        self.assertTrue(any("衔接" in r for r in review["reasons"]))
        deferred = plan["deferred"][0]
        self.assertEqual(deferred["id"], "226")
        self.assertTrue(any("轮换" in r for r in deferred["reasons"]), deferred["reasons"])
        self.assertEqual(plan["backlog"], {"count": 1, "per_day": 1, "oral_per_day": 2, "clear_days": 1, "oral_ready": 0,
                                           "by_topic": {"二叉树": 1}})
        # 时间充足日多出的复习名额会轮换到积压专题。
        rich = coach.build_plan(state, TODAY, 180, events=[])
        self.assertEqual([t["id"] for t in rich["tasks"] if t["kind"] == "review"], ["11", "226"])

    def test_recent_repeated_error_raises_priority(self):
        state = state_with(current="链表")
        practice(state, "100", "相同的树", "二叉树", "independent", 12)
        practice(state, "104", "二叉树的最大深度", "二叉树", "independent", 12)
        events = [{"tag": "return_loss", "problem_id": "100", "date": (TODAY - timedelta(days=d)).isoformat()} for d in (5, 15)]
        plan = coach.build_plan(state, TODAY, 120, events=events)
        self.assertEqual(plan["tasks"][0]["id"], "100")
        self.assertTrue(any("遗漏递归返回值" in r for r in plan["tasks"][0]["reasons"]))
        self.assertEqual(plan["weak_errors"][0]["count"], 2)

    def test_weak_errors_use_recent_window(self):
        state = state_with()
        old = (TODAY - timedelta(days=20)).isoformat()
        events = [{"tag": "boundary", "problem_id": "1", "date": old},
                  {"tag": "pointer_link", "problem_id": "2", "date": (TODAY - timedelta(days=3)).isoformat()},
                  {"tag": "return_loss", "problem_id": "3", "date": (TODAY - timedelta(days=40)).isoformat()},
                  {"tag": "return_loss", "problem_id": "4", "date": (TODAY - timedelta(days=45)).isoformat()}]
        self.assertEqual(set(coach.weak_errors(state, TODAY, events)), {"pointer_link"})


class SlotAccountingTests(unittest.TestCase):
    def test_calibration_fills_short_new_queue_without_stealing_slots(self):
        state = state_with(next_new=["42"])
        practice(state, "26", "删除有序数组中的重复项", "双指针", "independent", 5)
        state["completed"]["209"] = {"title": "长度最小的子数组", "topic": "滑动窗口", "count": 1,
                                     "last_done": "2026-10-13", "status": "needs_calibration"}
        plan = coach.build_plan(state, TODAY, 120, events=[])
        self.assertEqual([(t["kind"], t["id"]) for t in plan["tasks"]], [("review", "26"), ("new", "42"), ("calibration", "209")])
        self.assertTrue(all(t["reasons"] for t in plan["tasks"]))
        self.assertEqual(plan["new_shortage"], 0)
        coach.record_result(state, "209", "independent", TODAY)
        after = coach.build_plan(state, TODAY, 120, events=[])
        self.assertEqual([t["id"] for t in after["tasks"] if not t["recorded"]], ["26", "42"])
        coach.record_result(state, "42", "hinted", TODAY, "接雨水", "双指针")
        final = coach.build_plan(state, TODAY, 120, events=[])
        self.assertEqual([t["id"] for t in final["tasks"] if not t["recorded"]], ["26"])

    def test_calibration_counts_as_review_when_new_queue_is_full(self):
        state = state_with(next_new=["42", "75"])
        practice(state, "26", "删除有序数组中的重复项", "双指针", "independent", 5)
        state["completed"]["209"] = {"title": "长度最小的子数组", "topic": "滑动窗口", "count": 1,
                                     "last_done": "2026-10-13", "status": "needs_calibration"}
        coach.record_result(state, "209", "hinted", TODAY)
        plan = coach.build_plan(state, TODAY, 120, events=[])
        self.assertEqual([t["id"] for t in plan["tasks"] if not t["recorded"]], ["42", "75"])


class CandidateTests(unittest.TestCase):
    def test_candidates_skip_known_problems_and_follow_the_main_line(self):
        state = state_with(next_new=["125"])
        practice(state, "75", "颜色分类", "双指针", "independent", 4)
        plan = coach.build_plan(state, TODAY, 120, mentioned={"21"}, events=[])
        ids = [c["id"] for c in plan["candidates"]]
        self.assertEqual(len(ids), 4)
        self.assertFalse({"75", "125", "21"} & set(ids))
        current = [c for c in plan["candidates"] if c["reason"][0] == "收尾当前专题"]
        self.assertLessEqual(len(current), 2)
        self.assertTrue(all(catalog.related(c["topic"], state["current_topic"]) for c in current))
        self.assertTrue(any("链表" in c["reason"][0] for c in plan["candidates"]))
        # 推荐理由不包含解法要点。
        for c in plan["candidates"]:
            self.assertNotIn(catalog.CATALOG[c["id"]]["focus"], " ".join(c["reason"]))

    def test_no_candidates_when_queue_is_long_enough(self):
        state = state_with(next_new=["42", "75", "125"])
        self.assertEqual(coach.build_plan(state, TODAY, 120, events=[])["candidates"], [])

    def test_catalog_titles_fill_unknown_problems(self):
        state = state_with(next_new=["21"])
        self.assertEqual(coach.problem(state, "21")["title"], "合并两个有序链表")
        self.assertEqual(coach.problem(state, "21")["topic"], "链表")

    def test_mock_candidates_come_from_studied_families_with_local_cases(self):
        state = state_with()
        for pid, title in (("104", "二叉树的最大深度"), ("100", "相同的树"), ("701", "二叉搜索树中的插入操作")):
            practice(state, pid, title, "BST" if pid == "701" else "二叉树", "independent", 9)
        picks = coach.build_plan(state, TODAY, 120, events=[])["mock_candidates"]
        self.assertTrue(picks)
        for pick in picks:
            self.assertEqual(catalog.family(pick["topic"]), "二叉树")
            self.assertTrue(coach.has_exercise(pick["id"]))
            self.assertNotIn(pick["id"], state["completed"])
        self.assertEqual(picks[0]["difficulty"], "Medium")
        self.assertEqual(picks[0]["limit_minutes"], 25)


class AbilityReportTests(unittest.TestCase):
    def test_legacy_records_are_inferred_and_marked(self):
        state = state_with()
        state["completed"]["15"] = {"title": "三数之和", "topic": "双指针", "count": 1, "status": "learned",
                                    "last_done": (TODAY - timedelta(days=1)).isoformat()}
        practice(state, "11", "盛最多水的容器", "双指针", "hinted", 2)
        report = insights.ability_report(state, TODAY)
        week = report["week"]
        self.assertEqual((week["graded"], week["inferred"], week["independent_rate"]), (2, 1, 50))
        self.assertTrue(any("旧格式记录" in g for g in report["gaps"]))
        self.assertTrue(any("没有记录用时" in g for g in report["gaps"]))
        self.assertTrue(any("模拟面试" in g for g in report["gaps"]))

    def test_progress_needs_spaced_independent_after_help(self):
        state = state_with()
        practice(state, "11", "盛最多水的容器", "双指针", "hinted", 6)
        practice(state, "11", "盛最多水的容器", "双指针", "independent", 5)
        self.assertEqual(insights.progress_evidence(state), [])
        practice(state, "11", "盛最多水的容器", "双指针", "independent", 2)
        evidence = insights.progress_evidence(state)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["from"]["result"], "hinted")

    def test_mock_scores_and_markdown(self):
        state = state_with()
        rec = practice(state, "199", "二叉树的右视图", "二叉树", "independent", 1, minutes=22, mock=True)
        rec["history"][-1]["mock_review"] = {"limit_minutes": 25, "elapsed_seconds": 1320, "overtime": False,
                                             "scores": {"recognition": 4, "communication": 3, "code": 4, "complexity": 5, "time": 4},
                                             "average": 4.0, "scored_by": "self", "improve": "先讲变量"}
        report = insights.ability_report(state, TODAY)
        self.assertEqual(report["week"]["mocks"], 1)
        self.assertEqual(report["dimensions"][1], {"id": "communication", "title": "沟通表达", "latest": 3, "previous": None, "average": 3.0})
        text = insights.to_markdown(report)
        for heading in ("# 算法能力周报", "## 本周概览", "## 模拟面试", "## 专题进度"):
            self.assertIn(heading, text)
        self.assertIn("LC199 二叉树的右视图", text)


class OralReviewTests(unittest.TestCase):
    def setUp(self):
        self.state = state_with(current="二叉树")
        # LC104 已独立写对两次（可口述），LC226 上次需要提示（要完整重写），LC101 只写对过一次。
        practice(self.state, "104", "二叉树的最大深度", "二叉树", "independent", 20)
        practice(self.state, "104", "二叉树的最大深度", "二叉树", "independent", 16)
        practice(self.state, "226", "翻转二叉树", "二叉树", "hinted", 6)
        practice(self.state, "101", "对称二叉树", "二叉树", "independent", 6)
        practice(self.state, "100", "相同的树", "二叉树", "independent", 30)
        practice(self.state, "100", "相同的树", "二叉树", "independent", 26)

    def test_speakable_reviews_get_oral_slots_and_written_ones_keep_the_formal_slot(self):
        self.assertTrue(coach.oral_eligible(self.state["completed"]["104"]))
        self.assertFalse(coach.oral_eligible(self.state["completed"]["226"]))
        self.assertFalse(coach.oral_eligible(self.state["completed"]["101"]))
        plan = coach.build_plan(self.state, TODAY, 120, events=[])
        self.assertEqual([t["id"] for t in plan["tasks"] if t["kind"] == "review"], ["226"])
        self.assertEqual({r["id"] for r in plan["oral"]}, {"104", "100"})
        self.assertTrue(all(r["kind"] == "oral" and "口述" not in r["title"] for r in plan["oral"]))
        self.assertEqual([r["id"] for r in plan["deferred"]], ["101"])
        self.assertEqual((plan["oral_slots"], plan["backlog"]["clear_days"]), (2, 1))
        self.assertEqual([len(coach.build_plan(self.state, TODAY, m, events=[])["oral"]) for m in (45, 90, 180)], [1, 1, 2])

    def test_oral_results_move_the_due_date_without_touching_counts_or_status(self):
        before = deepcopy(self.state["completed"]["104"])
        rec = coach.record_oral(self.state, "104", "independent", TODAY)
        self.assertEqual((rec["count"], rec["status"], rec["history"]), (before["count"], before["status"], before["history"]))
        self.assertEqual(rec["stage"], coach.stage_of(before) + 1)
        self.assertEqual(rec["next_due"], (TODAY + timedelta(days=coach.interval(self.state, rec["stage"]))).isoformat())
        plan = coach.build_plan(self.state, TODAY, 120, events=[])
        self.assertEqual([(r["id"], r["result"]) for r in plan["oral_done"]], [("104", "independent")])
        self.assertEqual([r["id"] for r in plan["oral"]], ["100"])
        # 同一天更正：恢复口述前的状态后重新计算。
        rec = coach.record_oral(self.state, "104", "hinted", TODAY)
        self.assertEqual(rec["next_due"], (TODAY + timedelta(days=2)).isoformat())
        self.assertEqual(rec.get("stage"), before.get("stage"))
        self.assertEqual(len(rec["oral"]), 1)
        self.assertFalse(coach.oral_eligible(rec))
        later = coach.build_plan(self.state, TODAY + timedelta(days=2), 120, events=[])
        rewrite = next(r for r in later["reviews"] if r["id"] == "104")
        self.assertNotIn("104", [r["id"] for r in later["oral"]])
        self.assertIn("口述复习时有卡顿，完整重写一遍", rewrite["reasons"])
        coach.record_oral(self.state, "100", "failed", TODAY)
        self.assertEqual(self.state["completed"]["100"]["next_due"], (TODAY + timedelta(days=1)).isoformat())
        # 完整重写独立完成后，又可以口述。
        coach.record_result(self.state, "104", "independent", TODAY + timedelta(days=2))
        self.assertTrue(coach.oral_eligible(self.state["completed"]["104"]))
        with self.assertRaises(ValueError):
            coach.record_oral(self.state, "226", "independent", TODAY)
        with self.assertRaises(ValueError):
            coach.record_oral(self.state, "9999", "independent", TODAY)
        with self.assertRaises(ValueError):
            coach.record_oral(self.state, "100", "great", TODAY + timedelta(days=1))

    def test_oral_cli_records_and_today_lists_the_section(self):
        import io
        import json
        import tempfile
        from contextlib import redirect_stdout
        from pathlib import Path
        with tempfile.TemporaryDirectory(prefix="oral-cli-") as folder:
            path = Path(folder) / "learning-state.json"
            path.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
            path.with_name("learning-log.md").write_text("# 学习日志\n", encoding="utf-8")
            common = ["--state", str(path), "--date", TODAY.isoformat()]
            output = io.StringIO()
            with redirect_stdout(output):
                coach.main(["today", "--minutes", "120"] + common)
                coach.main(["oral", "104", "--result", "failed"] + common)
            text = output.getvalue()
            self.assertIn("【口述复习】", text)
            self.assertIn("LC104 口述复习：讲不出", text)
            self.assertEqual(coach.load(path)["completed"]["104"]["next_due"], (TODAY + timedelta(days=1)).isoformat())


class ChatMockCliTests(unittest.TestCase):
    def test_done_with_scores_feeds_the_ability_report(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory(prefix="mock-cli-") as folder:
            path = Path(folder) / "learning-state.json"
            path.write_text(json.dumps(state_with(), ensure_ascii=False), encoding="utf-8")
            args = ["done", "199", "--result", "hinted", "--title", "二叉树的右视图", "--topic", "二叉树", "--mock",
                    "--minutes", "28", "--limit", "25", "--scores", "4,3,4,4,2", "--note", "先讲层序", "--state", str(path),
                    "--date", TODAY.isoformat()]
            coach.main(args)
            state = coach.load(path)
            review = state["completed"]["199"]["history"][-1]["mock_review"]
            self.assertEqual((review["scores"]["time"], review["overtime"], review["scored_by"]), (2, True, "chat_coach"))
            self.assertEqual(state["last_mock"], TODAY.isoformat())
            self.assertEqual(insights.ability_report(state, TODAY)["dimensions"][4]["latest"], 2)
            with self.assertRaises(SystemExit):
                coach.main(args[:-6] + ["--scores", "4,3,9,4,2", "--state", str(path), "--date", TODAY.isoformat()])
            with self.assertRaises(SystemExit):
                coach.main(["done", "1", "--result", "independent", "--title", "两数之和", "--topic", "哈希", "--scores", "4,4,4,4,4",
                            "--state", str(path)])


if __name__ == "__main__":
    unittest.main()
