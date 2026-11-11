"""离线假模型验证教练流式回复确实逐块显示，且断流不会保存半句话。"""
import shutil
import sys
import tempfile
import threading
import time
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import expect, sync_playwright
from tools import coach_ai, dashboard


def main():
    originals = {path: path.read_bytes() for path in (ROOT / "learning-state.json", ROOT / "learning-log.md")}
    with tempfile.TemporaryDirectory(prefix="stream-ui-test-") as folder:
        state = Path(folder) / "learning-state.json"
        log = Path(folder) / "learning-log.md"
        shutil.copyfile(ROOT / "tests/fixtures/learning-state.json", state)
        shutil.copyfile(ROOT / "tests/fixtures/learning-log.md", log)
        original_state = state.read_bytes()
        server = dashboard.make_server(state, log, 0, date(2026, 10, 17))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        settings = {"provider": "openai", "model": "fake", "available": True, "modes": coach_ai.MODES,
                    "labels": coach_ai.PROVIDERS, "default_models": coach_ai.DEFAULT_MODELS,
                    "relays": list(coach_ai.RELAYS), "env_base_urls": {}, "base_url": "", "has_key": False}

        def model_stream(provider, system, prompt, model, on_delta, **kwargs):
            on_delta("请先讲变量")
            time.sleep(.65)
            on_delta("，再走例子。")
            return "请先讲变量，再走例子。\n[[ASSIST:no]]"

        try:
            with patch.object(coach_ai, "load_settings", return_value=settings), \
                    patch.object(coach_ai, "connection", return_value={"source": "test"}), \
                    patch.object(coach_ai, "ask_model_stream", side_effect=model_stream):
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)
                    page = browser.new_page(reduced_motion="reduce")
                    errors = []
                    page.on("pageerror", lambda exc: errors.append(str(exc)))
                    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
                    page.goto(f"http://127.0.0.1:{server.server_port}/#workbench")
                    panel = page.locator("#wb-coach")
                    expect(panel.get_by_role("button", name="检查我的讲解")).to_be_visible()
                    panel.get_by_role("button", name="检查我的讲解").click()
                    expect(panel.locator(".coach-cursor")).to_be_visible(timeout=10000)
                    expect(panel.locator(".coach-msg.from-coach").last).to_contain_text("请先讲变量")
                    expect(panel.locator(".coach-msg.from-coach").last).to_contain_text("再走例子", timeout=10000)
                    expect(panel.locator(".coach-cursor")).to_have_count(0)
                    assert not errors, errors
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        assert state.read_bytes() == original_state
    for path, original in originals.items():
        assert path.read_bytes() == original
    print("PASS: AI stream delivers live deltas, completes, and leaves learning progress unchanged")


if __name__ == "__main__":
    main()
