import io
import json
import os
import shutil
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from tools import catalog, coach, coach_ai, dashboard, learner, workbench
from reference_solutions import solution
from test_agent import FakeOpenAI, chat

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests/fixtures"
TODAY = date(2026, 10, 17)
ANY = lambda pid: True


def state_with(current="双指针与滑动窗口", next_new=None):
    return {"completed": {}, "next_new": list(next_new or []), "review_intervals_days": [3, 7, 21],
            "current_topic": current, "session": {}}


def practice(state, pid, title, topic, result, days_ago):
    return coach.record_result(state, pid, result, TODAY - timedelta(days=days_ago), title, topic)


def event(tag, pid, days_ago):
    return {"tag": tag, "problem_id": pid, "date": (TODAY - timedelta(days=days_ago)).isoformat()}


def ready_state(**kwargs):
    """双指针、滑动窗口都已较稳。"""
    state = state_with(**kwargs)
    for i, pid in enumerate(["26", "27", "283", "167"]):
        practice(state, pid, "t" + pid, "双指针", "independent", 2 + i)
    for i, pid in enumerate(["3", "209", "438"]):
        practice(state, pid, "t" + pid, "滑动窗口", "independent", 3 + i)
    return state


def recommend(state, events=(), **kwargs):
    profile = learner.build_profile(state, TODAY, list(events))
    return learner.recommend_new(state, profile, set(state["completed"]), has_exercise=ANY, **kwargs), profile


class ProfileTests(unittest.TestCase):
    def test_mastery_levels_recency_and_habits(self):
        state = state_with()
        for i, pid in enumerate(["26", "27", "283"]):
            practice(state, pid, "t" + pid, "双指针", "independent", 3 + i)
        practice(state, "206", "反转链表", "链表", "hinted", 2)
        practice(state, "20", "有效的括号", "栈与队列", "failed", 1)
        practice(state, "1047", "删除相邻重复项", "栈与队列", "failed", 2)
        practice(state, "1", "两数之和", "哈希", "independent", 120)
        practice(state, "217", "存在重复元素", "哈希", "failed", 1)
        practice(state, "242", "有效的字母异位词", "哈希", "failed", 2)
        profile = learner.build_profile(state, TODAY, [])
        topics = {t["name"]: t for t in profile["topics"]}
        self.assertEqual(topics["双指针"]["level"], "较稳")
        self.assertGreaterEqual(topics["双指针"]["mastery"], 75)
        self.assertEqual(topics["链表"]["level"], "起步")
        self.assertEqual(topics["栈与队列"]["level"], "需要加强")
        # 近期的失败比 4 个月前的独立完成更能说明现在的水平。
        self.assertLess(topics["哈希"]["mastery"], 40)
        habit = profile["habits"]
        self.assertEqual((habit["graded"], habit["independent"], habit["hinted"], habit["failed"]), (8, 3, 1, 4))
        self.assertEqual(habit["streak"], 5)
        self.assertIsNone(habit["avg_minutes"])
        self.assertEqual(profile["strengths"], ["双指针"])
        self.assertIn("栈与队列", profile["needs_work"])
        self.assertTrue(profile["summary"][0].startswith("当前专题「双指针与滑动窗口」掌握度"))

    def test_weaknesses_focus_and_coach_brief(self):
        state = state_with(current="二叉树")
        practice(state, "226", "翻转二叉树", "二叉树", "hinted", 5)
        practice(state, "112", "路径总和", "二叉树", "hinted", 4)
        events = [event("node_scope", "226", 5), event("node_scope", "112", 4)]
        profile = learner.build_profile(state, TODAY, events)
        top = profile["weaknesses"][0]
        self.assertEqual((top["id"], top["count"]), ("node_scope", 2))
        self.assertIn("tree_connect", top["patterns"])
        self.assertTrue(any("混淆 root 与当前节点" in f for f in profile["focus"]))
        brief = learner.coach_brief(state, TODAY, "105", events)
        self.assertEqual(brief["topic"], "二叉树")
        self.assertEqual([e["id"] for e in brief["relevant_errors"]], ["node_scope"])
        self.assertIn("可能在本题出现的常见错因：混淆 root 与当前节点", learner.brief_text(brief))
        other = learner.coach_brief(state, TODAY, "125", events)
        self.assertEqual(other["relevant_errors"], [])
        self.assertEqual(other["other_errors"], ["混淆 root 与当前节点"])

    def test_goal_countdown_and_settings_validation(self):
        state = state_with()
        learner.apply_settings(state, {"target_date": "2026-12-01", "daily_minutes": 90, "pace": "push"}, TODAY)
        target = learner.build_profile(state, TODAY, [])["goal"]
        self.assertEqual((target["days_left"], target["weeks_left"], target["urgent"]), (45, 7, True))
        self.assertEqual(target["remaining_topics"][0], "链表")
        for bad in ({"target_date": "2026-13-01"}, {"target_date": "2026-10-01"}, {"daily_minutes": 5},
                    {"daily_minutes": "90"}, {"pace": "fast"}):
            with self.assertRaises(ValueError, msg=bad):
                learner.validate_settings(bad, TODAY)
        self.assertEqual(learner.validate_settings({"target_date": ""}, TODAY), {"target_date": None})


class RecommendationTests(unittest.TestCase):
    def test_shaky_current_topic_gets_consolidation_without_hard(self):
        state = state_with()
        practice(state, "26", "t26", "双指针", "hinted", 3)
        practice(state, "27", "t27", "双指针", "failed", 2)
        picks, _ = recommend(state)
        self.assertEqual(len(picks), 4)
        self.assertIn("当前专题", picks[0]["tags"])
        self.assertIn("趁热巩固", picks[0]["reasons"][0])
        self.assertFalse([p["id"] for p in picks if p["difficulty"] == "Hard"])
        families = [catalog.family(p["topic"]) for p in picks]
        self.assertTrue(all(families.count(name) <= 2 for name in families))
        for p in picks:
            self.assertNotIn(catalog.CATALOG[p["id"]]["focus"], " ".join(p["reasons"]))

    def test_steady_topic_advances_the_main_line_and_targets_weak_patterns(self):
        state = ready_state()
        picks, profile = recommend(state)
        self.assertEqual(profile["next_topic"], "链表")
        advance = [p for p in picks if "推进主线" in p["tags"]]
        self.assertTrue(advance)
        self.assertTrue(all(p["topic"] == "链表" for p in advance))
        self.assertIn("推进到主线下一专题「链表」", advance[0]["reasons"][0])
        picks, _ = recommend(state, [event("window_condition", "209", 3), event("window_condition", "3", 6)])
        weak = [p for p in picks if "弱项巩固" in p["tags"]]
        self.assertTrue(weak)
        self.assertIn(weak[0]["id"], {"904", "1004", "424", "76"})
        self.assertTrue(any("窗口条件写错" in r for r in weak[0]["reasons"]))

    def test_pace_and_target_date_shape_the_picks(self):
        state = ready_state()
        learner.apply_settings(state, {"pace": "steady"}, TODAY)
        self.assertFalse([p for p in recommend(state)[0] if p["difficulty"] == "Hard"])
        learner.apply_settings(state, {"pace": "push"}, TODAY)
        self.assertTrue([p for p in recommend(state)[0] if p["difficulty"] == "Hard"])
        learner.apply_settings(state, {"pace": "normal", "target_date": (TODAY + timedelta(days=30)).isoformat()}, TODAY)
        picks, _ = recommend(state)
        self.assertTrue(any("优先大厂高频" in r for p in picks for r in p["reasons"]))
        self.assertTrue(all(p["frequency"] >= 2 for p in picks))


class PlanIntegrationTests(unittest.TestCase):
    def test_empty_slots_are_filled_by_recommendations_and_skips_hide_them(self):
        state = state_with()
        practice(state, "26", "删除有序数组中的重复项", "双指针", "independent", 5)
        plan = coach.build_plan(state, TODAY, 120, events=[])
        new = [t for t in plan["tasks"] if t["kind"] == "new"]
        self.assertEqual(len(new), 2)
        self.assertTrue(all(t["source"] == "recommended" and t["reasons"][0] == "为你推荐" for t in new))
        self.assertEqual(plan["new_shortage"], 0)
        self.assertTrue(plan["candidates"])
        self.assertFalse({t["id"] for t in new} & {c["id"] for c in plan["candidates"]})
        self.assertIn("summary", plan["profile"])
        skipped = new[0]["id"]
        learner.skip_recommendation(state, skipped, TODAY)
        after = coach.build_plan(state, TODAY, 120, events=[])
        self.assertNotIn(skipped, {t["id"] for t in after["tasks"]} | {c["id"] for c in after["candidates"]})
        later = coach.build_plan(state, TODAY + timedelta(days=7), 120, events=[])
        self.assertIn(skipped, {t["id"] for t in later["tasks"]} | {c["id"] for c in later["candidates"]})

    def test_calibration_keeps_one_slot_and_a_long_queue_needs_no_recommendations(self):
        state = state_with()
        practice(state, "26", "删除有序数组中的重复项", "双指针", "independent", 5)
        state["completed"]["209"] = {"title": "长度最小的子数组", "topic": "滑动窗口", "count": 1,
                                     "last_done": "2026-10-13", "status": "needs_calibration"}
        plan = coach.build_plan(state, TODAY, 120, events=[])
        self.assertEqual([(t["kind"], t.get("source")) for t in plan["tasks"]],
                         [("review", None), ("new", "recommended"), ("calibration", None)])
        state["next_new"] = ["42", "75", "125"]
        plan = coach.build_plan(state, TODAY, 120, events=[])
        self.assertFalse([t for t in plan["tasks"] if t.get("source") == "recommended"])
        self.assertEqual(plan["candidates"], [])


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            coach.main(list(args) + ["--state", str(self.path), "--date", TODAY.isoformat()])
        return output.getvalue()

    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="learner-cli-")
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "learning-state.json"
        state = ready_state()
        self.path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        self.path.with_name("learning-log.md").write_text("# 学习日志\n", encoding="utf-8")

    def test_profile_settings_today_minutes_and_skip(self):
        text = self.run_cli("profile", "--target-date", "2026-12-01", "--minutes", "90", "--pace", "push")
        self.assertIn("还有 45 天", text)
        self.assertIn("【专题掌握度】", text)
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(saved["profile"], {"target_date": "2026-12-01", "daily_minutes": 90, "pace": "push"})
        today = self.run_cli("today")
        self.assertIn("项目较忙日（90 分钟）", today)
        self.assertIn("推荐新题", today)
        self.run_cli("new", "skip", "75")
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["recommend_skips"], {"75": TODAY.isoformat()})


class EndpointCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="learner-http-")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.state = self.root / "learning-state.json"
        self.log = self.root / "learning-log.md"
        shutil.copyfile(FIXTURES / "learning-state.json", self.state)
        shutil.copyfile(FIXTURES / "learning-log.md", self.log)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_", "OPENAI_"))}
        patcher = patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.server = dashboard.make_server(self.state, self.log, 0, TODAY)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(self, path, payload=None, token=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=30)
        try:
            headers = {"Content-Type": "application/json", **({"X-Coach-Token": token} if token else {})}
            connection.request("POST" if payload is not None else "GET", path, json.dumps(payload).encode() if payload is not None else None, headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()


class ProfileEndpointTests(EndpointCase):
    def test_settings_skip_and_offline_advice(self):
        _, data = self.call("/api/dashboard")
        token = data["token"]
        self.assertEqual(data["plan"]["minutes"], 120)
        self.assertIsNone(data["advice"])
        self.assertIn("weaknesses", data["profile"])
        before = self.state.read_bytes()
        status, _ = self.call("/api/profile", {"daily_minutes": 5, "revision": data["revision"]}, token)
        self.assertEqual(status, 400)
        self.assertEqual(self.state.read_bytes(), before)
        status, saved = self.call("/api/profile", {"target_date": "2026-12-01", "daily_minutes": 90, "pace": "steady", "revision": data["revision"]}, token)
        self.assertEqual(status, 200, saved)
        _, data = self.call("/api/dashboard")
        self.assertEqual((data["plan"]["minutes"], data["profile"]["settings"]["pace"], data["profile"]["goal"]["days_left"]), (90, "steady", 45))
        self.assertEqual(self.call("/api/dashboard?minutes=180")[1]["plan"]["minutes"], 180)
        skipped = data["plan"]["candidates"][0]["id"]
        status, result = self.call("/api/recommend/skip", {"id": skipped, "revision": data["revision"]}, token)
        self.assertEqual(status, 200, result)
        _, data = self.call("/api/dashboard")
        self.assertNotIn(skipped, [c["id"] for c in data["plan"]["candidates"]])
        known = next(iter(json.loads(self.state.read_text(encoding="utf-8"))["completed"]))
        self.assertEqual(self.call("/api/recommend/skip", {"id": known, "revision": data["revision"]}, token)[0], 400)
        before = self.state.read_bytes()
        status, advice = self.call("/api/profile/advice", {}, token)
        self.assertEqual((status, advice["provider"]), (200, "offline"))
        self.assertTrue(advice["text"].startswith("当前状态"))
        self.assertEqual(self.state.read_bytes(), before)
        self.assertEqual(self.call("/api/dashboard")[1]["advice"]["text"], advice["text"])

    def test_model_advice_sends_the_profile_but_no_code(self):
        fake = ThreadingHTTPServer(("127.0.0.1", 0), FakeOpenAI)
        threading.Thread(target=fake.serve_forever, daemon=True).start()
        self.addCleanup(fake.server_close)
        self.addCleanup(fake.shutdown)
        FakeOpenAI.calls, FakeOpenAI.script = [], [chat("1. 本周先把链表的基础题做独立。")]
        coach_ai.save_settings(self.root, {"provider": "openai", "model": "gpt-5", "base_url": f"http://127.0.0.1:{fake.server_port}", "api_key": "sk-test"})
        token = self.call("/api/dashboard")[1]["token"]
        status, advice = self.call("/api/profile/advice", {}, token)
        self.assertEqual((status, advice["provider"], advice["model"]), (200, "openai", "gpt-5"))
        self.assertIn("链表的基础题", advice["text"])
        messages = FakeOpenAI.calls[-1]["body"]["messages"]
        self.assertEqual(messages[0], {"role": "system", "content": learner.ADVICE_SYSTEM})
        self.assertIn("各专题掌握度", messages[1]["content"])
        self.assertNotIn("class Solution", messages[1]["content"])
        FakeOpenAI.script = [(502, {"error": {"message": "upstream down"}})]
        status, fallback = self.call("/api/profile/advice", {}, token)
        self.assertEqual((status, fallback["provider"]), (200, "offline"))
        self.assertIn("改用离线版本", fallback["notice"])


class CoachPersonalizationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="learner-coach-")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        shutil.copyfile(FIXTURES / "learning-state.json", self.root / "learning-state.json")
        shutil.copyfile(FIXTURES / "learning-log.md", self.root / "learning-log.md")
        self.store = workbench.Workbench(self.root, self.root / "learning-log.md", TODAY)
        self.state = coach.load(self.root / "learning-state.json")
        self.payload = {"id": "42", "code": solution("42"), "extra_cases": [], "elapsed_seconds": 60, "idea": "双指针从两侧收缩",
                        "takeaway": "", "error_tags": []}

    def chat(self, mode="explain"):
        draft = self.store.read_draft("42")
        return self.store.coach_chat(self.state, {**self.payload, "draft_revision": draft["revision"], "mode": mode, "message": ""})

    def use_model(self):
        path = coach_ai.settings_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"provider": "openai", "model": "gpt-5"}), encoding="utf-8")

    def test_model_prompts_carry_the_profile_except_in_mock_interviews(self):
        self.assertEqual(self.store.describe(self.state, "42")["learner"]["topic"], "双指针")
        self.use_model()
        with patch.object(coach_ai, "ask_model", return_value="说说变量。\n[[ASSIST:no]]") as ask:
            self.chat()
        system, prompt = ask.call_args.args[1], ask.call_args.args[2]
        self.assertIn(coach_ai.PERSONALIZE, system)
        self.assertIn("学习者画像：", prompt)
        self.assertIn("本题专题「双指针」", prompt)
        self.store.start_mock(self.state, {"id": "42", "limit_minutes": 25}, TODAY)
        with patch.object(coach_ai, "ask_model", return_value="说说思路。\n[[ASSIST:no]]") as ask:
            self.chat()
        self.assertNotIn(coach_ai.PERSONALIZE, ask.call_args.args[1])
        self.assertNotIn("学习者画像", ask.call_args.args[2])

    def test_agent_context_and_offline_guidance_use_the_profile(self):
        info = self.store.describe(self.state, "209")
        snapshot = {"code": "class Solution: pass", "idea": "", "boundary": "", "time_complexity": "", "space_complexity": "", "takeaway": ""}
        self.assertIn("学习者画像：\n- 本题专题「滑动窗口」", self.store.agents.context(info, snapshot, None, info["draft"]))
        brief = {"topic": "双指针", "mastery": 60, "level": "巩固中", "graded": 3, "other_errors": [], "hint_rate": 30,
                 "independent_rate": 60, "pace": "正常推进", "days_left": None,
                 "relevant_errors": [{"id": "update_order", "title": "状态含义与更新顺序", "count": 3, "question": "变量保存的究竟是值、下标、距离还是计数？"}]}
        with patch.object(learner, "coach_brief", return_value=brief):
            reply = self.chat()
        self.assertIn("你近期常出现「状态含义与更新顺序」：变量保存的究竟是值、下标、距离还是计数？", reply["reply"])
        self.assertFalse(reply["counted"])


if __name__ == "__main__":
    unittest.main()
