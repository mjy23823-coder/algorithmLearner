"""工作台自动计时的浏览器验证：开始写就计时，10 分钟没有操作自动暂停且只多计 2 分钟，继续输入接着计时。用模拟时钟，不真的等待。"""
import os
import re
import shutil
import sys
import tempfile
import threading
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import expect, sync_playwright
from tools import dashboard

TODAY = date(2026, 10, 17)


def seconds(text):
    minutes, secs = text.split(":")
    return int(minutes) * 60 + int(secs)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="timer-ui-") as folder:
        path = Path(folder) / "learning-state.json"
        shutil.copyfile(ROOT / "tests/fixtures/learning-state.json", path)
        shutil.copyfile(ROOT / "tests/fixtures/learning-log.md", path.with_name("learning-log.md"))
        server = dashboard.make_server(path, path.with_name("learning-log.md"), 0, TODAY)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        errors = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                context.add_init_script("localStorage.setItem('algorithm-workbench-selected', '42')")
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.clock.install()
                page.goto(f"http://127.0.0.1:{server.server_port}/#workbench")
                clock = page.locator("#wb-clock")
                # 快进模拟时钟前先等真实的网络请求完成，否则请求的超时计时器会被一起快进。
                expect(page.get_by_label("我的核心思路", exact=True)).to_be_visible()
                expect(page.get_by_role("button", name="开始计时", exact=True)).to_be_enabled()
                page.clock.run_for(30_000)
                expect(clock).to_have_text("00:00")
                page.get_by_label("我的核心思路", exact=True).fill("两侧最大高度")
                expect(page.get_by_role("button", name="暂停计时", exact=True)).to_be_visible()
                page.clock.run_for(1_000)
                expect(page.locator("#wb-save-status")).to_have_text(re.compile("草稿已保存|有新修改待保存"))
                page.clock.run_for(59_000)
                page.get_by_label("一个边界情况", exact=True).fill("只有一根柱子")
                page.clock.run_for(60_000)
                expect(clock).to_have_text(re.compile(r"^02:0\d$"))
                # 离开 12 分钟：最后一次操作 10 分钟后自动暂停，只多计 2 分钟（共 1 + 2 分钟）。
                page.clock.run_for(720_000)
                expect(page.locator("#wb-save-status")).to_contain_text("计时已自动暂停")
                expect(page.get_by_role("button", name="继续计时", exact=True)).to_be_visible()
                paused = seconds(clock.inner_text())
                assert 179 <= paused <= 182, paused
                page.clock.run_for(600_000)
                assert seconds(clock.inner_text()) == paused
                page.get_by_label("Python 代码", exact=True).fill("class Solution:\n    def trap(self, height):\n        return 0\n")
                page.clock.run_for(10_000)
                assert seconds(clock.inner_text()) >= paused + 9, clock.inner_text()
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
        assert not errors, errors
    print("PASS: auto start on typing, idle auto-pause after 10 minutes with 2-minute grace, resume on input")


if __name__ == "__main__":
    main()
