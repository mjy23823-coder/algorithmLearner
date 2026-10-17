"""面板 AI 功能的浏览器验证：口述复习 AI 判断、问问 AI（时间建议按钮）、周报点评、画像分析。用本地假服务代替 CPA，不调用真实模型。"""
import json
import os
import re
import shutil
import sys
import tempfile
import threading
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from playwright.sync_api import expect, sync_playwright
from test_agent import FakeOpenAI, chat
from tools import coach, coach_ai, dashboard

TODAY = date(2026, 10, 17)
SPOKEN = "这是数组原地修改，用快慢指针。slow 指向下一个写入位置，fast 扫描，遇到和前一个不同的值就写到 slow 并后移。时间 O(n)，空间 O(1)。边界：空数组直接返回 0。"


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    for key in [k for k in os.environ if k.startswith(("ANTHROPIC_", "OPENAI_"))]:
        del os.environ[key]
    originals = {p: p.read_bytes() for p in (ROOT / "learning-state.json", ROOT / "learning-log.md")}
    FakeOpenAI.calls, FakeOpenAI.script = [], []
    fake = ThreadingHTTPServer(("127.0.0.1", 0), FakeOpenAI)
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix="ai-ui-") as folder:
        path = Path(folder) / "learning-state.json"
        shutil.copyfile(ROOT / "tests/fixtures/learning-state.json", path)
        shutil.copyfile(ROOT / "tests/fixtures/learning-log.md", path.with_name("learning-log.md"))
        coach_ai.save_settings(Path(folder), {"provider": "openai", "model": "gpt-5", "base_url": f"http://127.0.0.1:{fake.server_port}", "api_key": "sk-test"})
        server = dashboard.make_server(path, path.with_name("learning-log.md"), 0, TODAY)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        errors = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
                base = f"http://127.0.0.1:{server.server_port}"

                # 口述复习：写下讲解 → AI 四项判断 → 按建议记录。
                page.goto(base + "/#today")
                oral = page.locator(".oral-panel")
                item = oral.locator(".oral-item").first
                pid = item.locator(".task-id").inner_text().replace("LC", "").strip()
                item.get_by_role("button", name="写下讲解，让 AI 判断").click()
                item.get_by_label(f"LC{pid} 的口述讲解").fill(SPOKEN)
                FakeOpenAI.script = [chat('{"recognition": "ok", "idea": "ok", "complexity": "ok", "boundary": "partial", "feedback": "思路和复杂度都讲清楚了，边界可以再说说全部相同元素。"}')]
                item.get_by_role("button", name="让 AI 判断").click()
                judgment = item.locator(".oral-judgment")
                expect(judgment).to_contain_text("全部相同元素", timeout=20000)
                expect(judgment.locator(".mark")).to_have_count(4)
                expect(judgment.locator(".mark.partial")).to_contain_text("边界情况")
                expect(judgment.locator(".oral-suggest")).to_contain_text("讲清楚了")
                body = json.dumps(FakeOpenAI.calls[-1]["body"], ensure_ascii=False)
                assert SPOKEN in body and "recognition" in body, "判断请求应包含讲解与评分要求"
                page.screenshot(path=str(ROOT / "artifacts/ai-oral-judge.png"), full_page=True)
                judgment.get_by_role("button", name="按建议记录").click()
                expect(page.locator("#toast")).to_contain_text(f"LC{pid} 口述复习：讲清楚了")
                entry = coach.load(path)["completed"][pid]["oral"][-1]
                assert entry["explanation"] == SPOKEN and entry["judged_by"] == "openai" and entry["marks"]["boundary"] == "partial", entry

                # 问问 AI：回复里建议的时间变成按钮，点了才重新排。
                FakeOpenAI.script = [chat("先做正式复习，口述复习放在最后。\n[[MINUTES:60]]")]
                page.locator(".ask-panel").get_by_role("button", name="时间不够，先做哪道？").click()
                expect(page.locator(".ask-msg.coach").last).to_contain_text("先做正式复习", timeout=20000)
                expect(page.locator(".ask-msg.coach").last).not_to_contain_text("MINUTES")
                assert "今日任务" in json.dumps(FakeOpenAI.calls[-1]["body"], ensure_ascii=False)
                page.get_by_role("button", name="按 60 分钟重新排").click()
                expect(page.locator(".time-option.active")).to_have_text("60 分钟")
                FakeOpenAI.script = [chat("按 60 分钟的安排，先复习再口述。")]
                page.get_by_label("向 AI 提问今天的计划").fill("这样排可以吗？")
                page.get_by_label("向 AI 提问今天的计划").press("Enter")
                expect(page.locator(".ask-msg.coach").last).to_contain_text("按 60 分钟的安排", timeout=20000)
                page.screenshot(path=str(ROOT / "artifacts/ai-ask-plan.png"), full_page=True)
                page.reload()
                expect(page.locator(".ask-msg")).to_have_count(4)

                # 能力周报：AI 点评。
                page.get_by_role("navigation").get_by_role("button", name="能力周报").click()
                FakeOpenAI.script = [chat("1. 本周节奏稳定，口述复习开始发挥作用。\n2. 下周先补链表。")]
                page.get_by_role("button", name="生成点评").click()
                expect(page.locator("[data-weekly-advice]")).to_contain_text("本周节奏稳定", timeout=20000)
                expect(page.locator("[data-weekly-advice] .advice-meta")).to_contain_text("gpt-5")
                expect(page.get_by_role("button", name="重新点评")).to_be_visible()
                assert "class Solution" not in json.dumps(FakeOpenAI.calls[-1]["body"], ensure_ascii=False)

                # 画像页阶段分析仍然可用（改用了公共展示）。
                page.get_by_role("navigation").get_by_role("button", name="我的画像").click()
                FakeOpenAI.script = [chat("当前状态：双指针已经较稳，下周进入链表。")]
                page.get_by_role("button", name="让 AI 分析我的情况").click()
                expect(page.locator(".advice-text")).to_contain_text("下周进入链表", timeout=20000)

                page.set_viewport_size({"width": 390, "height": 844})
                page.get_by_role("navigation").get_by_role("button", name="今日学习").click()
                page.wait_for_timeout(300)
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            fake.shutdown()
            fake.server_close()
            thread.join(timeout=5)
        assert not errors, errors
    for original, content in originals.items():
        assert original.read_bytes() == content, f"{original.name} 被修改"
    print("PASS: oral AI judging with confirm-to-save, plan Q&A with minutes button and persistence, weekly AI review, profile analysis, mobile")
    print("Screenshots: artifacts/ai-oral-judge.png, artifacts/ai-ask-plan.png")


if __name__ == "__main__":
    main()
