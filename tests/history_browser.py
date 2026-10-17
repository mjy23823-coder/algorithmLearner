"""验证补录前后的图谱和计数；从固定测试快照导入，绝不修改真实进度。"""
import json
import shutil
import sys
import tempfile
import threading
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import expect, sync_playwright
from tools import coach, dashboard


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    originals = {p: p.read_bytes() for p in [ROOT / "learning-state.json", ROOT / "learning-log.md"]}
    with tempfile.TemporaryDirectory(prefix="history-ui-tests-") as folder:
        state = Path(folder) / "learning-state.json"
        log = Path(folder) / "learning-log.md"
        shutil.copyfile(ROOT / "tests/fixtures" / state.name, state)
        shutil.copyfile(ROOT / "tests/fixtures" / log.name, log)
        server = dashboard.make_server(state, log, 0, date(2026, 10, 17))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        errors = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1500, "height": 1050}, reduced_motion="reduce")
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}/#graph")
                expect(page.locator(".graph-overview-stats strong").last).to_have_text("13")
                manifest = json.loads((ROOT / "data/history-review-2026-10-17.json").read_text(encoding="utf-8"))
                recovered, _ = coach.prepare_history_import(coach.load(state), manifest, log, date(2026, 10, 17))
                coach.save(state, recovered)
                page.get_by_role("button", name="刷新进度", exact=True).click()
                expect(page.locator(".graph-overview-stats strong").last).to_have_text("46")
                expect(page.locator(".graph-source-note")).to_contain_text("另有 1 道待学")
                expect(page.locator("#graph-count")).to_contain_text("/ 47")
                expect(page.locator(".node-topic")).to_have_count(8)
                page.screenshot(path=str(ROOT / "artifacts/learning-history-recovered.png"), full_page=True)
                page.get_by_label("图谱专题", exact=True).select_option("链表")
                expect(page.locator(".node-problem")).to_have_count(2)
                page.locator('[data-node="problem:206"] .graph-node-circle').click()
                expect(page.locator("#graph-detail")).to_contain_text("至少 2 次")
                expect(page.locator("#graph-detail")).to_contain_text("历史学习日志补回")
                page.get_by_label("图谱专题", exact=True).select_option("")
                page.get_by_label("搜索图谱节点", exact=True).fill("LC977")
                expect(page.locator("#graph-detail .graph-facts")).to_contain_text("待核对")
                page.get_by_label("搜索图谱节点", exact=True).fill("")
                page.get_by_role("button", name="折叠专题", exact=True).click()
                page.get_by_role("button", name="展开专题", exact=True).click()
                expect(page.locator(".node-problem")).to_have_count(47)
                ids = page.locator(".node-problem").evaluate_all("nodes => nodes.map(node => node.dataset.node)")
                assert len(set(ids)) == 47
                page.get_by_role("button", name="题目档案", exact=True).click()
                expect(page.locator("#problem-rows tr")).to_have_count(46)
                page.get_by_label("搜索题目", exact=True).fill("LC206")
                expect(page.locator("#problem-rows")).to_contain_text("至少 2 次")
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
    assert not errors, errors
    assert all(path.read_bytes() == original for path, original in originals.items())
    print("PASS: live refresh 13 -> 46, 8 topics, 47 unique graph nodes including one unpracticed problem, source labels and conservative counts")


if __name__ == "__main__":
    main()
