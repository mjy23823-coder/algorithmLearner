"""学习画像页的浏览器验证：画像展示、设置目标、换一题、离线阶段分析、从推荐去练习、保存后提示下一题。不调用模型。"""
import json
import re
import os
import shutil
import sys
import tempfile
import threading
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from playwright.sync_api import expect, sync_playwright
from reference_solutions import solution
from tools import coach, dashboard

TODAY = date(2026, 10, 17)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    for key in [k for k in os.environ if k.startswith(("ANTHROPIC_", "OPENAI_"))]:
        del os.environ[key]
    originals = {p: p.read_bytes() for p in (ROOT / "learning-state.json", ROOT / "learning-log.md")}
    with tempfile.TemporaryDirectory(prefix="profile-ui-") as folder:
        path = Path(folder) / "learning-state.json"
        shutil.copyfile(ROOT / "tests/fixtures/learning-state.json", path)
        shutil.copyfile(ROOT / "tests/fixtures/learning-log.md", path.with_name("learning-log.md"))
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
                page.goto(base + "/#profile")
                expect(page.get_by_role("heading", name="先读懂你，再给你下一题。")).to_be_visible()
                profile = json.loads(page.evaluate("JSON.stringify(data.profile)"))
                expect(page.locator(".mastery-row")).to_have_count(len(profile["topics"]))
                assert page.evaluate("[...document.querySelectorAll('.mastery-fill')].every(el => parseFloat(el.style.width) > 0)")
                page.locator(".mastery-row").first.hover()
                expect(page.locator(".mastery-row").first.locator(".mastery-tip")).to_be_visible()
                expect(page.locator(".goal-hero")).to_contain_text("未设置")

                # 设置学习目标：面试日期、每天时间、节奏。
                page.get_by_role("button", name="设置学习目标").first.click()
                dialog = page.locator("dialog.profile-settings")
                dialog.get_by_label("目标面试日期").fill("2026-12-01")
                dialog.get_by_label("每天计划学习").select_option("90")
                dialog.locator("label").filter(has_text="冲刺加速").click()
                dialog.get_by_role("button", name="保存").click()
                expect(page.locator("#toast")).to_contain_text("学习目标已更新")
                expect(page.locator(".goal-hero")).to_contain_text("45")
                saved = coach.load(path)["profile"]
                assert saved == {"target_date": "2026-12-01", "daily_minutes": 90, "pace": "push"}, saved

                # 换一题：7 天内不再推荐。
                rows = page.locator(".rec-row")
                expect(rows.first).to_be_visible()
                skipped = rows.first.locator(".task-id").inner_text().replace("LC", "").strip()
                rows.first.get_by_role("button", name="换一题").click()
                expect(page.locator("#toast")).to_contain_text(f"已换掉 LC{skipped}")
                expect(page.locator(".rec-row .task-id").filter(has_text=re.compile(rf"^LC {skipped}$"))).to_have_count(0)

                # 离线阶段分析：结果保存在本机，刷新后保留。
                page.get_by_role("button", name="让 AI 分析我的情况").click()
                expect(page.locator(".advice-text")).to_contain_text("当前状态", timeout=20000)
                page.screenshot(path=str(ROOT / "artifacts/learner-profile.png"), full_page=True)
                page.reload()
                expect(page.locator(".advice-text")).to_contain_text("当前状态")
                assert (Path(folder) / ".runtime/profile-advice.json").exists()

                # 今日页：时间档跟随画像里的每日计划时间，并显示画像摘要。
                page.get_by_role("navigation").get_by_role("button", name="今日学习", exact=True).click()
                expect(page.locator(".time-option.active")).to_have_text("90 分钟")
                expect(page.get_by_role("heading", name="你的学习画像")).to_be_visible()

                # 从推荐去练习，保存后提示下一题。
                page.get_by_role("navigation").get_by_role("button", name="我的画像", exact=True).click()
                pick = page.locator(".rec-row").filter(has=page.get_by_role("button", name="去练习")).first
                pid = pick.locator(".task-id").inner_text().replace("LC", "").strip()
                pick.get_by_role("button", name="去练习").click()
                expect(page.locator("#wb-problem")).to_have_value(pid)
                page.get_by_label("Python 代码", exact=True).fill(solution(pid))
                page.get_by_role("button", name="运行本地用例", exact=True).click()
                expect(page.locator(".wb-test-summary")).to_contain_text("本地用例全部通过", timeout=15000)
                page.locator("#wb-result").select_option("independent")
                page.get_by_role("button", name="保存结果并更新复习").click()
                expect(page.locator("#toast")).to_contain_text("下一题：", timeout=15000)
                assert pid in coach.load(path)["completed"]
                next_id = page.locator("#toast").inner_text().split("下一题：LC")[1].split(" ")[0]
                page.locator("#toast").get_by_role("button", name="去练习").click()
                expect(page.locator("#wb-problem")).to_have_value(next_id)

                page.set_viewport_size({"width": 390, "height": 844})
                page.goto(base + "/#profile")
                expect(page.get_by_role("heading", name="先读懂你，再给你下一题。")).to_be_visible()
                page.wait_for_timeout(300)
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(ROOT / "artifacts/learner-profile-mobile.png"), full_page=True)
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        assert not errors, errors
    for original, content in originals.items():
        assert original.read_bytes() == content, f"{original.name} 被修改"
    print("PASS: profile view, mastery chart and tooltip, goal settings, skip recommendation, offline advice persistence, today minutes, practice from recommendation, next-up toast, mobile")
    print("Screenshots: artifacts/learner-profile.png, artifacts/learner-profile-mobile.png")


if __name__ == "__main__":
    main()
