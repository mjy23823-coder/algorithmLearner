import json
import shutil
import tempfile
import threading
import unittest
from datetime import date
from http.client import HTTPConnection
from pathlib import Path

from tools import coach, dashboard


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="algorithm-http-tests-")
        self.state = Path(self.directory.name) / "learning-state.json"
        self.log = self.state.with_name("learning-log.md")
        shutil.copyfile(dashboard.ROOT / "tests/fixtures/learning-state.json", self.state)
        shutil.copyfile(dashboard.ROOT / "tests/fixtures/learning-log.md", self.log)
        self.server = dashboard.make_server(self.state, self.log, 0, date(2026, 10, 16))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.original = self.state.read_bytes()
        self.original_log = self.log.read_bytes()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=5)
        self.directory.cleanup()

    def request(self, path="/api/dashboard", payload=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            body = json.dumps(payload).encode() if payload is not None else None
            connection.request("POST" if payload is not None else "GET", path, body,
                               {"Content-Type": "application/json", **(headers or {})})
            response = connection.getresponse()
            raw = response.read()
            data = json.loads(raw) if "application/json" in response.getheader("Content-Type", "") else raw
            return response.status, data
        finally:
            connection.close()

    def test_read_only_dashboard_does_not_touch_progress_or_log(self):
        status, data = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(data["stats"]["today_done"], 4)
        self.assertEqual(data["stats"]["due"], 3)
        self.assertEqual({r["id"] for r in data["plan"]["calibration"]}, {"209", "11"})
        self.assertTrue(all(r["recorded"] for r in data["plan"]["tasks"]))
        for asset in ("/", "/app.js", "/style.css", "/graph.js", "/graph.css", "/workbench.js", "/workbench.css", "/favicon.svg", "/api/log", "/api/export", "/api/health", "/api/workbench?id=42"):
            self.assertEqual(self.request(asset)[0], 200)
        self.assertEqual(self.state.read_bytes(), self.original)
        self.assertEqual(self.log.read_bytes(), self.original_log)

    def test_record_practice_persists_and_request_retry_is_idempotent(self):
        _, data = self.request()
        payload = {"id": "42", "title": "接雨水", "topic": "双指针", "result": "independent",
                   "minutes": 28, "note": "左右最大值", "revision": data["revision"], "request_id": "practice-1"}
        headers = {"X-Coach-Token": data["token"]}
        first = self.request("/api/practice", payload, headers)
        second = self.request("/api/practice", payload, headers)
        self.assertEqual(first, second)
        self.assertEqual(first[0], 200)
        rec = coach.load(self.state)["completed"]["42"]
        self.assertEqual((rec["count"], rec["next_due"]), (1, "2026-10-19"))
        self.assertEqual(len(rec["history"]), 1)
        self.assertEqual(self.log.read_bytes(), self.original_log)

    def test_stale_browser_cannot_overwrite_chat_coach(self):
        _, data = self.request()
        state = coach.load(self.state)
        state["current_topic"] = "链表"
        coach.save(self.state, state)
        status, _ = self.request("/api/session", {"topic": "哈希", "revision": data["revision"]}, {"X-Coach-Token": data["token"]})
        self.assertEqual(status, 409)
        self.assertEqual(coach.load(self.state)["current_topic"], "链表")

    def test_local_access_validation_and_static_allowlist(self):
        _, data = self.request()
        payload = {"revision": data["revision"], "ids": ["42"]}
        self.assertEqual(self.request("/api/queue", payload)[0], 403)
        self.assertEqual(self.request(headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request(headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request("/../learning-state.json")[0], 404)
        self.assertEqual(self.request("/learning-state.json")[0], 404)
        self.assertEqual(self.state.read_bytes(), self.original)

    def test_invalid_payload_does_not_write(self):
        _, data = self.request()
        headers = {"X-Coach-Token": data["token"]}
        for ids in ("42", ["../42"], ["0"]):
            self.assertEqual(self.request("/api/queue", {"ids": ids, "revision": data["revision"]}, headers)[0], 400)
        payload = {"id": "42", "title": "接雨水", "topic": "双指针", "result": "independent", "minutes": -1, "revision": data["revision"]}
        self.assertEqual(self.request("/api/practice", payload, headers)[0], 400)
        self.assertEqual(self.state.read_bytes(), self.original)

    def test_wrap_api_appends_existing_practices_without_faking_new_ones(self):
        _, data = self.request()
        payload = {"note": "今天的总结", "next_action": "继续到期复习", "revision": data["revision"], "request_id": "wrap-1"}
        headers = {"X-Coach-Token": data["token"]}
        response = self.request("/api/wrap", payload, headers)
        self.assertEqual(response[0], 200)
        self.assertEqual(self.request("/api/wrap", payload, headers), response)
        state = coach.load(self.state)
        self.assertEqual(state["completed"], json.loads(self.original)["completed"])
        content = self.log.read_bytes()
        self.assertTrue(content.startswith(self.original_log))
        self.assertEqual(content.count(b"<!-- algo-wrap:"), 1)

    def test_shutdown_requires_token_and_does_not_write_progress(self):
        _, data = self.request()
        self.assertEqual(self.request("/api/shutdown", {})[0], 403)
        self.assertEqual(self.request("/api/shutdown", {}, {"X-Coach-Token": data["token"]})[0], 200)
        self.worker.join(timeout=5)
        self.assertFalse(self.worker.is_alive())
        self.assertEqual(self.state.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
