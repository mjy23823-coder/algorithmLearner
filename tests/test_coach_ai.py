import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from datetime import date, timedelta
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from tools import coach, coach_ai, dashboard, workbench
from reference_solutions import solution

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests/fixtures"
TODAY = date(2026, 10, 17)


class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="coach-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state_path = self.root / "learning-state.json"
        self.log_path = self.root / "learning-log.md"
        shutil.copyfile(FIXTURES / self.state_path.name, self.state_path)
        shutil.copyfile(FIXTURES / self.log_path.name, self.log_path)
        self.store = workbench.Workbench(self.root, self.log_path)
        self.state = coach.load(self.state_path)
        self.payload = {"id": "42", "code": solution("42"), "extra_cases": [], "draft_revision": None, "elapsed_seconds": 60,
                        "idea": "", "takeaway": "", "error_tags": []}

    def use_model(self, provider="claude_cli"):
        path = coach_ai.settings_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"provider": provider, "model": "claude-opus-5-5"}), encoding="utf-8")

    def chat(self, mode, message="", **fields):
        draft = self.store.read_draft("42")
        return self.store.coach_chat(self.state, {**self.payload, **fields, "draft_revision": draft["revision"], "mode": mode, "message": message})


class OfflineCoachTests(WorkspaceCase):
    def test_explain_asks_for_idea_first_and_never_counts(self):
        reply = self.chat("explain")
        self.assertIn("核心思路", reply["reply"])
        self.assertEqual((reply["provider"], reply["counted"]), ("offline", False))
        reply = self.chat("explain", idea="左右指针维护两侧最大值")
        self.assertIn("关键变量", reply["reply"])
        self.assertEqual(self.store.read_draft("42")["hints_used"], 0)

    def test_offline_hint_is_the_next_layered_hint_and_forces_hinted(self):
        reply = self.chat("hint")
        self.assertTrue(reply["counted"])
        self.assertTrue(reply["reply"].startswith("提示 1："))
        self.assertEqual(len(reply["hints"]), 1)
        draft = self.store.read_draft("42")
        self.assertEqual((draft["hints_used"], draft.get("coach_hints", 0)), (1, 0))
        run = self.store.run({**self.payload, "draft_revision": draft["revision"]}, TODAY)
        result = self.store.complete(self.state, {**self.payload, "run_id": run["run_id"], "result": "independent"}, TODAY)
        self.assertEqual(result["result"], "hinted")

    def test_review_restates_test_results_without_counting(self):
        self.assertIn("运行本地用例", self.chat("review")["reply"])
        draft = self.store.read_draft("42")
        bad = {**self.payload, "code": "class Solution:\n    def trap(self, height):\n        return 0\n", "draft_revision": draft["revision"]}
        self.store.run(bad, TODAY)
        reply = self.chat("review", code=bad["code"])
        self.assertIn("期望", reply["reply"])
        self.assertFalse(reply["counted"])

    def test_transcript_is_kept_per_round(self):
        self.chat("explain")
        self.chat("reflect")
        draft = self.store.read_draft("42")
        self.assertEqual(len(self.store.describe(self.state, "42")["coach"]["transcript"]), 4)
        self.store.start_round({"id": "42", "draft_revision": draft["revision"]})
        self.assertEqual(self.store.describe(self.state, "42")["coach"]["transcript"], [])

    def test_ask_requires_a_question_and_validates_mode(self):
        with self.assertRaises(ValueError):
            self.chat("ask")
        with self.assertRaises(ValueError):
            self.chat("solve")


class ModelCoachTests(WorkspaceCase):
    def test_model_hint_counts_and_strips_marker(self):
        self.use_model()
        with patch.object(coach_ai, "ask_model", return_value="想想左右两侧的最高柱子。\n[[ASSIST:yes]]") as ask:
            reply = self.chat("hint", idea="还没想好")
        system, prompt = ask.call_args.args[1], ask.call_args.args[2]
        self.assertIn("第 1 层提示", system)
        self.assertIn("还没想好", prompt)
        self.assertNotIn("[[ASSIST", reply["reply"])
        self.assertTrue(reply["counted"])
        draft = self.store.read_draft("42")
        self.assertEqual(draft["coach_hints"], 1)
        run = self.store.run({**self.payload, "draft_revision": draft["revision"]}, TODAY)
        result = self.store.complete(self.state, {**self.payload, "run_id": run["run_id"], "result": "independent"}, TODAY)
        self.assertEqual(result["result"], "hinted")
        self.assertEqual(self.state["completed"]["42"]["history"][-1]["coach_hints"], 1)

    def test_free_question_counts_only_when_model_gave_direction(self):
        self.use_model()
        with patch.object(coach_ai, "ask_model", return_value="deque 的 popleft 是 O(1)。\n[[ASSIST:no]]"):
            self.assertFalse(self.chat("ask", "popleft 复杂度？")["counted"])
        with patch.object(coach_ai, "ask_model", return_value="可以用双指针。\n[[ASSIST:yes]]"):
            self.assertTrue(self.chat("ask", "怎么做？")["counted"])
        self.assertEqual(self.store.read_draft("42")["coach_hints"], 1)

    def test_model_review_counts_only_before_tests_pass(self):
        self.use_model()
        with patch.object(coach_ai, "ask_model", return_value="第 3 行的循环条件有问题。\n[[ASSIST:yes]]"):
            self.assertTrue(self.chat("review")["counted"])
        draft = self.store.read_draft("42")
        self.store.run({**self.payload, "draft_revision": draft["revision"]}, TODAY)
        with patch.object(coach_ai, "ask_model", return_value="正确性：通过。\n[[ASSIST:yes]]"):
            self.assertFalse(self.chat("review")["counted"])

    def test_model_failure_falls_back_to_offline_with_notice(self):
        self.use_model()
        with patch.object(coach_ai, "ask_model", side_effect=coach_ai.CoachError("连接不到模型服务")):
            reply = self.chat("explain")
        self.assertEqual(reply["provider"], "offline")
        self.assertIn("改用离线引导", reply["notice"])
        self.assertFalse(reply["counted"])

    def test_mock_prompt_hides_problem_identity_and_history(self):
        self.use_model()
        started = self.store.start_mock(self.state, {"id": "42", "limit_minutes": 25}, TODAY)
        with patch.object(coach_ai, "ask_model", return_value="说说你的思路。\n[[ASSIST:no]]") as ask:
            self.store.coach_chat(self.state, {**self.payload, "draft_revision": started["draft"]["revision"], "mode": "explain", "message": ""})
        system, prompt = ask.call_args.args[1], ask.call_args.args[2]
        self.assertIn("模拟面试", system)
        self.assertNotIn("接雨水", prompt)
        self.assertNotIn("LC42", prompt)


class MockInterviewTests(WorkspaceCase):
    scores = {"recognition": 4, "communication": 3, "code": 4, "complexity": 4, "time": 5}

    def start(self, limit=25):
        started = self.store.start_mock(self.state, {"id": "42", "limit_minutes": limit}, TODAY)
        self.assertEqual(started["draft"]["mock"]["limit_minutes"], limit)
        return started["draft"]

    def test_server_clock_review_and_single_save(self):
        draft = self.start()
        run = self.store.run({**self.payload, "draft_revision": draft["revision"]}, TODAY)
        later = workbench.utc_now() + timedelta(minutes=30)
        with patch.object(workbench, "utc_now", return_value=later):
            result = self.store.complete(self.state, {**self.payload, "run_id": run["run_id"], "result": "independent",
                                                      "elapsed_seconds": 5, "scores": self.scores, "improve": "先讲变量"}, TODAY)
        review = result["mock_review"]
        self.assertGreaterEqual(review["elapsed_seconds"], 1800)
        self.assertTrue(review["overtime"])
        self.assertEqual(review["average"], 4.0)
        entry = self.state["completed"]["42"]["history"][-1]
        self.assertTrue(entry["mock"])
        self.assertGreaterEqual(entry["minutes"], 30)
        self.assertEqual(self.state["last_mock"], TODAY.isoformat())
        self.assertEqual(self.state["completed"]["42"]["history"][-1]["note"], "先讲变量")
        with self.assertRaises(ValueError):
            self.store.complete(self.state, {**self.payload, "run_id": run["run_id"], "result": "independent", "scores": self.scores}, TODAY)

    def test_scores_are_required_and_bounded(self):
        draft = self.start()
        run = self.store.run({**self.payload, "draft_revision": draft["revision"]}, TODAY)
        base = {**self.payload, "run_id": run["run_id"], "result": "independent"}
        for scores in (None, {**self.scores, "time": 6}, {k: v for k, v in self.scores.items() if k != "code"}):
            with self.assertRaises(ValueError):
                self.store.complete(self.state, {**base, "scores": scores}, TODAY)
        self.assertNotIn("42", self.state["completed"])

    def test_random_pick_and_limit_validation(self):
        with self.assertRaises(ValueError):
            self.store.start_mock(self.state, {"id": "42", "limit_minutes": 2}, TODAY)
        picked = self.store.start_mock(self.state, {"id": "random", "limit_minutes": 25}, TODAY)
        self.assertNotIn(picked["id"], self.state["completed"])
        self.assertTrue(picked["draft"]["mock"]["started_at"])

    def test_help_during_mock_is_recorded(self):
        draft = self.start()
        self.store.coach_chat(self.state, {**self.payload, "draft_revision": draft["revision"], "mode": "hint", "message": ""})
        draft = self.store.read_draft("42")
        run = self.store.run({**self.payload, "draft_revision": draft["revision"]}, TODAY)
        result = self.store.complete(self.state, {**self.payload, "run_id": run["run_id"], "result": "independent", "scores": self.scores}, TODAY)
        self.assertEqual(result["result"], "hinted")
        self.assertEqual(result["mock_review"]["help_used"], 1)


class FakeMessages(BaseHTTPRequestHandler):
    calls = []
    responses = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeMessages.calls.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
        status, data = FakeMessages.responses.pop(0)
        raw = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeMessages)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        FakeMessages.calls, FakeMessages.responses = [], []
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")}
        env.update(ANTHROPIC_API_KEY="test-key", ANTHROPIC_BASE_URL=f"http://127.0.0.1:{self.server.server_port}")
        patcher = patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_request_shape_and_fallback_retry(self):
        FakeMessages.responses = [(400, {"type": "error", "error": {"type": "invalid_request_error", "message": "fallbacks: unknown field"}}),
                                  (200, {"content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": "你好"}], "stop_reason": "end_turn"})]
        self.assertEqual(coach_ai.call_anthropic("系统", "问题", "claude-opus-5-5"), "你好")
        first, second = FakeMessages.calls
        self.assertEqual(first["path"], "/v1/messages")
        self.assertEqual(first["headers"]["x-api-key"], "test-key")
        self.assertEqual(first["headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(first["headers"]["anthropic-beta"], "server-side-fallback-2026-07-01")
        self.assertEqual(first["body"]["fallbacks"], "default")
        self.assertEqual(first["body"]["model"], "claude-opus-5-5")
        self.assertEqual(first["body"]["output_config"], {"effort": "low"})
        self.assertNotIn("thinking", first["body"])
        self.assertNotIn("fallbacks", second["body"])
        self.assertNotIn("anthropic-beta", second["headers"])

    def test_refusal_and_auth_errors_raise_coach_errors(self):
        FakeMessages.responses = [(200, {"content": [], "stop_reason": "refusal"}),
                                  (401, {"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})]
        with self.assertRaisesRegex(coach_ai.CoachError, "拒绝"):
            coach_ai.call_anthropic("系统", "问题", "claude-opus-5-5")
        with self.assertRaisesRegex(coach_ai.CoachError, "API Key"):
            coach_ai.call_anthropic("系统", "问题", "claude-opus-5-5")

    def test_cli_runs_without_tools_outside_the_project(self):
        seen = {}

        def fake_run(args, **kwargs):
            seen.update(args=args, **kwargs)
            return subprocess.CompletedProcess(args, 0, json.dumps({"type": "result", "is_error": False, "result": "继续说说变量"}).encode(), b"")

        with patch.object(coach_ai.shutil, "which", return_value="claude"), patch.object(coach_ai.subprocess, "run", side_effect=fake_run), \
                patch.dict(os.environ, {"CLAUDECODE": "1"}):
            self.assertEqual(coach_ai.call_cli("系统", "问题", "claude-opus-5-5"), "继续说说变量")
        args = seen["args"]
        self.assertEqual(args[args.index("--tools") + 1], "")
        self.assertIn("--no-session-persistence", args)
        self.assertEqual(seen["input"], "问题".encode("utf-8"))
        self.assertNotIn("CLAUDECODE", seen["env"])
        self.assertNotEqual(Path(seen["cwd"]).resolve(), ROOT)

    def test_split_assist_marker(self):
        self.assertEqual(coach_ai.split_assist("好\n[[ASSIST:yes]]"), ("好", True))
        self.assertEqual(coach_ai.split_assist("好\n[[assist:NO]]  "), ("好", False))
        self.assertEqual(coach_ai.split_assist("没有标记"), ("没有标记", None))


class CoachEndpointTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="coach-http-")
        self.addCleanup(self.directory.cleanup)
        self.state = Path(self.directory.name) / "learning-state.json"
        self.log = self.state.with_name("learning-log.md")
        shutil.copyfile(FIXTURES / "learning-state.json", self.state)
        shutil.copyfile(FIXTURES / "learning-log.md", self.log)
        self.server = dashboard.make_server(self.state, self.log, 0, TODAY)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.original = self.state.read_bytes()

    def request(self, path, payload=None, token=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        try:
            headers = {"Content-Type": "application/json", **({"X-Coach-Token": token} if token else {})}
            connection.request("POST" if payload is not None else "GET", path, json.dumps(payload).encode() if payload is not None else None, headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_coach_and_mock_endpoints_never_change_progress(self):
        _, data = self.request("/api/dashboard")
        token = data["token"]
        self.assertIn("insights", data)
        self.assertIn("# 算法能力周报", data["insights"]["markdown"])
        self.assertTrue(all("reasons" in t for t in data["plan"]["tasks"] if not t["recorded"]))
        body = {"id": "42", "code": solution("42"), "extra_cases": [], "draft_revision": None, "mode": "explain", "message": ""}
        self.assertEqual(self.request("/api/workbench/coach", body)[0], 403)
        status, reply = self.request("/api/workbench/coach", body, token)
        self.assertEqual((status, reply["provider"]), (200, "offline"))
        status, settings = self.request("/api/coach/settings")
        self.assertEqual((status, settings["provider"]), (200, "offline"))
        self.assertEqual(self.request("/api/coach/settings", {"provider": "bogus"}, token)[0], 400)
        self.assertEqual(self.request("/api/coach/test", {"provider": "offline"}, token)[0], 400)
        status, started = self.request("/api/mock/start", {"id": "105", "limit_minutes": 25}, token)
        self.assertEqual(status, 200)
        self.assertEqual(started["draft"]["mock"]["limit_minutes"], 25)
        self.assertEqual(self.state.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
