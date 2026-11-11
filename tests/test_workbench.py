import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

from tools import coach, dashboard, knowledge, problem_bank, code_runner, workbench
from reference_solutions import solution

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests/fixtures"
TODAY = date(2026,10,17)


class StatusAndKnowledgeTests(unittest.TestCase):
    def test_cli_and_dashboard_share_the_same_mastery_totals(self):
        path=FIXTURES / "learning-state.json"
        state=coach.load(path)
        before=path.read_bytes()
        panel=dashboard.dashboard_data(state,FIXTURES/"learning-log.md",TODAY,120)
        result=subprocess.run([sys.executable,str(ROOT/"tools/coach.py"),"status","--state",str(path),"--date",str(TODAY),"--json"],capture_output=True,encoding="utf-8",check=True)
        summary=json.loads(result.stdout)
        self.assertEqual(summary["learned"],panel["stats"]["learned"])
        self.assertEqual(summary["learned"],7)
        self.assertEqual(coach.mastery_status(state["completed"]["15"]),"learning")
        self.assertEqual(state["completed"]["15"]["status"],"learned")
        self.assertEqual(path.read_bytes(),before)

    def test_error_relations_require_evidence_not_keyword_mentions(self):
        state=coach.load(FIXTURES/"learning-state.json")
        manifest=json.loads((ROOT/"data/history-review-2026-10-17.json").read_text(encoding="utf-8"))
        state,_=coach.prepare_history_import(state,manifest,FIXTURES/"learning-log.md",TODAY)
        data=knowledge.build_knowledge(state,FIXTURES/"learning-log.md")
        returns=next(e for e in data["errors"] if e["id"]=="return_loss")
        self.assertEqual(set(returns["problem_ids"]),{"100","235"})
        self.assertNotIn("538",returns["problem_ids"])
        self.assertTrue(all(e["text"] for e in returns["evidence"]))
        self.assertTrue(any("230" in p["problem_ids"] and "530" in p["problem_ids"] for p in data["patterns"]))


class RunnerTests(unittest.TestCase):
    def test_every_builtin_exercise_accepts_a_correct_reference(self):
        self.assertEqual(len(problem_bank.BANK),79)
        for pid in problem_bank.BANK:
            with self.subTest(pid=pid):
                result=code_runner.run_code(solution(pid),problem_bank.get_exercise(pid))
                self.assertTrue(result["passed"],result)

    def test_wrong_answer_exception_and_infinite_loop_are_reported(self):
        exercise=problem_bank.get_exercise("217")
        for body in ["return False","return 1/0"]:
            result=code_runner.run_code("class Solution:\n    def containsDuplicate(self,nums):\n        "+body,exercise)
            self.assertFalse(result["passed"])
        result=code_runner.run_code("class Solution:\n    def containsDuplicate(self,nums):\n        while True: pass",exercise,timeout=.4)
        self.assertIn("已终止",result["error"])

    def test_syntax_error_returns_structured_location_for_the_editor(self):
        code="class Solution:\n    def containsDuplicate(self,nums):\n        if True\n            return False"
        result=code_runner.run_code(code,problem_bank.get_exercise("217"))
        self.assertFalse(result["passed"])
        self.assertEqual(result["error_detail"]["kind"],"syntax")
        self.assertEqual(result["error_detail"]["line"],3)
        # 报错措辞随 Python 版本变化（3.10+ 多为 "expected ':'"），只校验错误类型
        self.assertIn("syntaxerror",result["error"].lower())

    def test_user_code_cannot_use_file_import_or_reflection_helpers(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/"should-not-exist.txt"
            code=f"class Solution:\n    def containsDuplicate(self,nums):\n        open({str(target)!r},'w').write('oops')\n        return False"
            result=code_runner.run_code(code,problem_bank.get_exercise("217"))
            self.assertFalse(result["passed"])
            self.assertFalse(target.exists())
        for prefix in ["import os", "import socket", "x = (1).__class__", "from operator import attrgetter\nx=attrgetter('__class__')(1)"]:
            result=code_runner.run_code(prefix+"\n"+solution("217"),problem_bank.get_exercise("217"))
            self.assertFalse(result["passed"])

    def test_output_is_bounded_and_memory_limit_does_not_hang_server(self):
        code=solution("217").replace("return len", "print('x'*20000)\n        return len")
        result=code_runner.run_code(code,problem_bank.get_exercise("217"))
        self.assertTrue(result["passed"])
        self.assertLessEqual(len(result["stdout"]),12000)
        code="class Solution:\n    def containsDuplicate(self,nums):\n        huge=[0]*200000000\n        return False"
        result=code_runner.run_code(code,problem_bank.get_exercise("217"))
        self.assertFalse(result["passed"])

    def test_in_place_and_node_contracts_detect_false_results(self):
        for pid,code in [("26","class Solution:\n    def removeDuplicates(self,nums):\n        return len(set(nums))"),
                         ("206","class Solution:\n    def reverseList(self,head):\n        if head: head.next=head\n        return head"),
                         ("235","class Solution:\n    def lowestCommonAncestor(self,root,p,q):\n        return TreeNode(6)")]:
            self.assertFalse(code_runner.run_code(code,problem_bank.get_exercise(pid))["passed"])

    def test_unicode_code_cases_and_output_are_utf8(self):
        code=solution("42").replace("return sum", "# 检查水位边界\n        print('中文调试：凹槽')\n        return sum")
        result=code_runner.run_code(code,problem_bank.get_exercise("42"),[{"name":"最小凹槽","args":[[3,0,3]],"expected":3}])
        self.assertTrue(result["passed"],result)
        self.assertEqual(result["cases"][-1]["name"],"最小凹槽")
        self.assertIn("中文调试：凹槽",result["stdout"])


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="workbench-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.state_path=self.root/"learning-state.json"
        self.log_path=self.root/"learning-log.md"
        shutil.copyfile(FIXTURES/self.state_path.name,self.state_path)
        shutil.copyfile(FIXTURES/self.log_path.name,self.log_path)
        self.store=workbench.Workbench(self.root,self.log_path)
        self.state=coach.load(self.state_path)
        self.payload={"id":"42","code":solution("42"),"extra_cases":[],"draft_revision":None,
                      "elapsed_seconds":93,"idea":"先明确每列水位","takeaway":"更新两侧最大高度","error_tags":["boundary"]}

    def test_reading_and_testing_do_not_change_learning_progress(self):
        original=self.state_path.read_bytes()
        data=self.store.describe(self.state,"42")
        self.assertIsNone(data["draft"]["revision"])
        self.assertFalse((self.root/"solutions").exists())
        run=self.store.run(self.payload,TODAY)
        self.assertTrue(run["result"]["passed"])
        self.assertEqual(self.state_path.read_bytes(),original)
        self.assertTrue((self.root/"solutions/lc42"/(run["run_id"]+".py")).exists())

    def test_workbench_description_contains_readable_problem_statement(self):
        data=self.store.describe(self.state,"42")
        statement=data["statement"]
        self.assertIn("下雨后",statement["text"])
        self.assertEqual(len(statement["constraints"]),2)
        self.assertEqual(len(statement["examples"]),4)
        self.assertTrue(statement["url"].endswith("trapping-rain-water/"))
        self.assertEqual(statement["method"],"trap(height)")
        self.assertTrue(any(figure["kind"] == "bars" for figure in statement["examples"][0]["figures"]))
        self.assertTrue(any(figure["kind"] == "tree" for figure in self.store.describe(self.state,"94")["statement"]["examples"][0]["figures"]))
        self.assertTrue(any(figure["kind"] == "list" for figure in self.store.describe(self.state,"206")["statement"]["examples"][0]["figures"]))

    def test_complete_uses_verified_run_and_saves_review_metadata(self):
        run=self.store.run(self.payload,TODAY)
        result=self.store.complete(self.state,{**self.payload,"run_id":run["run_id"],"result":"independent"},TODAY)
        record=self.state["completed"]["42"]
        self.assertEqual(result["next_due"],"2026-10-20")
        self.assertEqual(record["count"],1)
        self.assertEqual(record["history"][-1]["validation"]["kind"],"local_cases")
        self.assertEqual(record["history"][-1]["error_tags"],["boundary"])
        self.assertEqual(record["history"][-1]["minutes"],2)
        self.assertEqual(coach.weekly_report(self.state,TODAY)["minutes"],1.6)
        links=knowledge.build_knowledge(self.state,self.log_path)
        self.assertIn("42",next(e for e in links["errors"] if e["id"]=="boundary")["problem_ids"])

    def test_hint_usage_cannot_be_recorded_as_independent(self):
        response=self.store.reveal({**self.payload,"level":2})
        run=self.store.run({**self.payload,"draft_revision":response["draft"]["revision"]},TODAY)
        result=self.store.complete(self.state,{**self.payload,"run_id":run["run_id"],"result":"independent"},TODAY)
        self.assertEqual(result["result"],"hinted")
        self.assertEqual(self.state["completed"]["42"]["history"][-1]["hints_used"],2)

    def test_changed_code_changed_cases_failed_tests_or_old_run_are_rejected(self):
        run=self.store.run(self.payload,TODAY)
        base={**self.payload,"run_id":run["run_id"],"result":"independent"}
        original=deepcopy(self.state)
        for changed in ({"code":self.payload["code"]+"\n# modified"},{"extra_cases":[{"args":[[1]],"expected":0}]}):
            with self.assertRaises(ValueError): self.store.complete(self.state,{**base,**changed},TODAY)
        with self.assertRaises(ValueError): self.store.complete(self.state,base,TODAY+timedelta(days=1))
        self.assertEqual(self.state,original)
        draft=self.store.read_draft("42")
        bad={**self.payload,"code":"class Solution:\n    def trap(self,height): return -1","draft_revision":draft["revision"]}
        failure=self.store.run(bad,TODAY)
        with self.assertRaises(ValueError): self.store.complete(self.state,{**bad,"run_id":failure["run_id"],"result":"independent"},TODAY)
        self.store.complete(self.state,{**bad,"run_id":failure["run_id"],"result":"failed"},TODAY)
        self.assertEqual(self.state["completed"]["42"]["count"],0)

    def test_draft_conflicts_and_new_round_preserve_previous_code(self):
        draft=self.store.save_draft(self.payload)
        with self.assertRaises(ValueError): self.store.save_draft(self.payload)
        hint=self.store.reveal({**self.payload,"draft_revision":draft["revision"],"level":1})
        fresh=self.store.start_round({"id":"42","draft_revision":hint["draft"]["revision"]})
        self.assertEqual(fresh["hints_used"],0)
        self.assertNotEqual(fresh["session_id"],hint["draft"]["session_id"])
        archives=list((self.root/"solutions/.drafts/archive").glob("*.json"))
        self.assertEqual(len(archives),1)
        self.assertEqual(json.loads(archives[0].read_text(encoding="utf-8"))["code"],self.payload["code"])


if __name__ == "__main__":
    unittest.main()
