"""三项升级的浏览器验证：状态口径、关系图谱、计时/草稿/测试/保存。"""
import json
import shutil
import sys
import tempfile
import threading
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))

from playwright.sync_api import expect, sync_playwright
from tools import coach,dashboard
from reference_solutions import solution


def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,"reconfigure"): stream.reconfigure(encoding="utf-8")
    originals={p:p.read_bytes() for p in (ROOT/"learning-state.json",ROOT/"learning-log.md")}
    with tempfile.TemporaryDirectory(prefix="workbench-ui-tests-") as folder:
        path=Path(folder)/"learning-state.json"; log=path.with_name("learning-log.md")
        shutil.copyfile(ROOT/"tests/fixtures/learning-state.json",path)
        shutil.copyfile(ROOT/"tests/fixtures/learning-log.md",log)
        manifest=json.loads((ROOT/"data/history-review-2026-10-17.json").read_text(encoding="utf-8"))
        recovered,_=coach.prepare_history_import(coach.load(path),manifest,log,date(2026,10,17))
        coach.save(path,recovered)
        before=path.read_bytes()
        server=dashboard.make_server(path,log,0,date(2026,10,17))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        errors=[]
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True)
                context=browser.new_context(viewport={"width":1500,"height":1050},reduced_motion="reduce")
                page=context.new_page()
                page.on("pageerror",lambda error:errors.append(str(error)))
                page.on("console",lambda message:errors.append(message.text) if message.type=="error" else None)
                page.goto(f"http://127.0.0.1:{server.server_port}/#graph")
                expect(page.locator("#learning-graph")).to_have_attribute("data-ready","true")
                page.get_by_role("button",name="按模板",exact=True).click()
                page.get_by_label("搜索图谱节点",exact=True).fill("BST 中序状态维护")
                expect(page.locator(".node-problem")).to_have_count(4)
                page.get_by_label("搜索图谱节点",exact=True).fill("")
                ids=page.locator(".node-problem").evaluate_all("nodes=>nodes.map(n=>n.dataset.node)")
                assert len(ids)==len(set(ids))
                expect(page.locator('[data-to="problem:112"]')).to_have_count(2)
                page.locator('[data-node="patterns:inorder_state"] .graph-node-circle').click()
                expect(page.locator("#graph-detail")).to_contain_text("共享这个解题模板")
                page.screenshot(path=str(ROOT/"artifacts/pattern-graph.png"),full_page=True)

                page.get_by_role("button",name="按错因",exact=True).click()
                page.get_by_label("搜索图谱节点",exact=True).fill("遗漏递归返回值")
                expect(page.locator(".node-problem")).to_have_count(2)
                assert set(page.locator(".node-problem").evaluate_all("nodes=>nodes.map(n=>n.dataset.node)"))=={"problem:100","problem:235"}
                page.locator('[data-node="errors:return_loss"] .graph-node-circle').click()
                expect(page.locator("#graph-detail")).to_contain_text("记录依据")
                expect(page.locator(".graph-evidence")).to_have_count(2)
                page.screenshot(path=str(ROOT/"artifacts/error-graph.png"),full_page=True)

                page.get_by_role("button",name="按专题",exact=True).click()
                page.get_by_label("搜索图谱节点",exact=True).fill("LC42")
                page.locator('[data-node="problem:42"] .graph-node-circle').click()
                page.get_by_role("button",name="开始本题练习",exact=True).click()
                expect(page.get_by_label("Python 代码",exact=True)).to_have_value(solution_start := "class Solution:\n    def trap(self, height):\n        # 先说明变量含义，再完成你的实现\n        pass\n")
                expect(page.locator("[data-problem-statement]")).to_be_visible()
                expect(page.locator("[data-problem-statement]")).to_contain_text("下雨后")
                expect(page.locator("[data-problem-statement]")).to_contain_text("约束条件")
                expect(page.locator("[data-problem-statement]")).to_contain_text("示例 1")
                expect(page.locator(".wb-statement-link")).to_have_attribute("href", "https://leetcode.cn/problems/trapping-rain-water/")
                page.screenshot(path=str(ROOT/"artifacts/learning-workbench.png"),full_page=True)
                assert path.read_bytes()==before
                expect(page.get_by_role("button",name="开始计时",exact=True)).to_be_visible()
                page.get_by_label("我的核心思路",exact=True).fill("每列水量由两侧较低的最大高度决定")
                # 开始写思路就自动计时。
                expect(page.get_by_role("button",name="暂停计时",exact=True)).to_be_visible()
                page.get_by_label("一个边界情况",exact=True).fill("只有一根柱子时无法积水")
                page.get_by_label("Python 代码",exact=True).fill(solution("42"))
                expect(page.locator("#wb-clock")).not_to_have_text("00:00")
                page.get_by_text("追加自定义用例（JSON 数组）",exact=True).click()
                page.get_by_label("自定义测试用例",exact=True).fill('[{"name":"最小凹槽","args":[[3,0,3]],"expected":3}]')
                page.get_by_role("button",name="运行本地用例",exact=True).click()
                expect(page.locator(".wb-test-summary")).to_be_visible(timeout=15000)
                try:
                    expect(page.locator(".wb-test-summary")).to_contain_text("本地用例全部通过",timeout=1000)
                except AssertionError:
                    print(page.locator("#wb-test-results").inner_text())
                    print("CODE:",repr(page.get_by_label("Python 代码",exact=True).input_value()))
                    print("ERROR:",page.locator("#wb-error").inner_text())
                    raise
                expect(page.locator(".wb-test-summary")).to_contain_text("5 / 5")
                assert path.read_bytes()==before
                page.locator("#wb-content").get_by_label("一句话复盘",exact=True).fill("先计算当前列水量，再移动状态")
                page.get_by_label("边界与指针方向",exact=True).check()
                page.get_by_label("真实完成情况",exact=True).select_option("independent")
                page.get_by_role("button",name="保存结果并更新复习",exact=True).click()
                expect(page.locator("#learning-graph")).to_have_attribute("data-ready","true")
                saved=coach.load(path)["completed"]["42"]
                assert saved["count"]==1 and saved["next_due"]=="2026-10-20"
                assert saved["history"][-1]["validation"]["passed"]
                assert saved["history"][-1]["elapsed_seconds"]>0
                assert saved["history"][-1]["error_tags"]==["boundary"]
                assert len(list((Path(folder)/"solutions/lc42").glob("*.py")))==1

                page.get_by_role("button",name="练习工作台",exact=True).click()
                expect(page.get_by_label("Python 代码",exact=True)).to_have_value(solution("42"))
                page.get_by_role("button",name="从空白开始新一轮练习",exact=True).click()
                expect(page.get_by_label("Python 代码",exact=True)).to_have_value(solution_start)
                page.get_by_role("button",name="提示 1",exact=True).click()
                expect(page.locator("#wb-hint-note")).to_contain_text("已看 1 层提示")
                page.get_by_label("Python 代码",exact=True).fill(solution("42"))
                page.get_by_role("button",name="运行本地用例",exact=True).click()
                expect(page.locator(".wb-test-summary")).to_contain_text("本地用例全部通过",timeout=15000)
                expect(page.locator('#wb-result option[value="independent"]')).to_have_attribute("disabled", "")
                expect(page.locator("#wb-result")).to_have_value("hinted")
                page.get_by_label("Python 代码",exact=True).fill(solution("42")+"\n# new edit")
                expect(page.get_by_role("button",name="保存结果并更新复习",exact=True)).to_be_disabled()
                page.get_by_label("Python 代码",exact=True).fill(solution("42"))
                page.get_by_role("button",name="保存结果并更新复习",exact=True).click()
                expect(page.locator("#learning-graph")).to_have_attribute("data-ready","true")
                saved=coach.load(path)["completed"]["42"]
                assert saved["count"]==1 and saved["status"]=="needs_review"

                page.get_by_role("button",name="练习工作台",exact=True).click()
                expect(page.get_by_label("Python 代码",exact=True)).to_be_visible()
                page.get_by_label("我的核心思路",exact=True).fill("草稿刷新后应保留")
                page.get_by_role("button",name="保存草稿",exact=True).click()
                expect(page.locator("#wb-save-status")).to_contain_text("草稿已保存")
                page.reload()
                expect(page.get_by_label("我的核心思路",exact=True)).to_have_value("草稿刷新后应保留")
                page.set_viewport_size({"width":390,"height":844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=str(ROOT/"artifacts/learning-workbench-mobile.png"),full_page=True)
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)
    assert not errors,errors
    assert all(p.read_bytes()==value for p,value in originals.items())
    print("PASS: patterns/mistakes/evidence, unique graph nodes, workbench draft/timer/cases/save, hint grading, stale code, same-day counts, reload and mobile")


if __name__=="__main__": main()
