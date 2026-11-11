import base64
import subprocess
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from tools import coach, notify

TODAY = date(2026, 10, 17)


def state_with():
    state = {"completed": {}, "next_new": ["42"], "review_intervals_days": [3, 7, 21], "current_topic": "二叉树", "session": {}}
    for pid, title, days in (("104", "二叉树的最大深度", 20), ("104", "二叉树的最大深度", 16), ("226", "翻转二叉树", 6)):
        coach.record_result(state, pid, "hinted" if pid == "226" else "independent", TODAY - timedelta(days=days), title, "二叉树")
    return state


class MessageTests(unittest.TestCase):
    def test_daily_message_lists_tasks_oral_and_focus_without_solutions(self):
        plan = coach.build_plan(state_with(), TODAY, 120, events=[])
        title, lines, attribution = notify.daily_message(plan)
        self.assertEqual(title, "今晚练什么 · 普通日 120 分钟")
        self.assertIn("复习 LC226 翻转二叉树", lines[0])
        self.assertIn("复习 LC104 二叉树的最大深度", lines[0])
        self.assertIn("新题 LC42", lines[0])
        self.assertTrue(any(text.startswith("推荐 LC") for text in lines[0].split("；")))
        self.assertTrue(attribution.startswith("重点："))

    def test_finished_day_and_weekly_summary(self):
        plan = {"mode": "普通日", "minutes": 120, "tasks": [{"id": "1", "title": "两数之和", "kind": "new", "recorded": True}],
                "oral": [], "short_recall": [], "profile": {"focus": ["推进链表"]}}
        self.assertEqual(notify.daily_message(plan)[1], ["今天的计划已经完成，记得点“结束并保存”。"])
        report = {"week": {"start": "2026-10-11", "end": "2026-10-17", "active_days": 4, "practices": 11, "independent_rate": 90},
                  "focus": ["复习时重点检查「混淆 root 与当前节点」"]}
        title, lines, attribution = notify.weekly_message(report, "已提交到本地 git")
        self.assertEqual(title, "本周算法周报 · 10-11 至 10-17")
        self.assertEqual(lines, ["学习 4 天，练习 11 次，独立完成率 90%", "下周重点：复习时重点检查「混淆 root 与当前节点」"])
        self.assertEqual(attribution, "已提交到本地 git")

    def test_toast_xml_escapes_text_and_keeps_three_lines(self):
        xml = notify.toast_xml("标题 <A&B>", ["一", "二", "三"], "底部 \"小字\"")
        self.assertIn("<text>标题 &lt;A&amp;B&gt;</text>", xml)
        self.assertEqual(xml.count("<text>"), 3)
        self.assertNotIn("<text>三</text>", xml)
        self.assertIn('placement="attribution">底部 "小字"</text>', xml)
        self.assertIn('launch="http://127.0.0.1:8765/#today"', xml)


class SystemTests(unittest.TestCase):
    def fake_run(self, captured, returncode=0, stdout=b""):
        def run(args, **kwargs):
            captured.append((args, kwargs))
            return subprocess.CompletedProcess(args, returncode, stdout, b"boom" if returncode else b"")
        return run

    def script_of(self, args):
        return base64.b64decode(args[args.index("-EncodedCommand") + 1]).decode("utf-16-le")

    def test_show_passes_the_toast_through_the_environment(self):
        calls = []
        with patch.object(notify.sys, "platform", "win32"), patch.object(notify.subprocess, "run", side_effect=self.fake_run(calls)):
            notify.show("今晚练什么", ["复习 LC11"], "重点：先讲思路")
        args, kwargs = calls[0]
        self.assertIn("ToastNotificationManager", self.script_of(args))
        self.assertIn("<text>复习 LC11</text>", kwargs["env"]["ALGO_TOAST_XML"])
        self.assertEqual(kwargs["env"]["ALGO_TOAST_APP"], notify.APP_ID)
        with patch.object(notify.sys, "platform", "win32"), patch.object(notify.subprocess, "run", side_effect=self.fake_run([], 1)):
            with self.assertRaisesRegex(OSError, "弹出通知失败"):
                notify.show("t", ["x"])

    def test_install_registers_two_local_tasks_and_uninstall_removes_them(self):
        calls = []
        with patch.object(notify.subprocess, "run", side_effect=self.fake_run(calls)):
            notify.manage("install")
            notify.manage("uninstall")
        install, uninstall = (self.script_of(args) for args, _ in calls)
        self.assertEqual(install.count("Register-ScheduledTask"), 2)
        self.assertIn("-Daily -At '19:25'", install)
        self.assertIn("-Weekly -DaysOfWeek Sunday -At '20:35'", install)
        self.assertIn("-StartWhenAvailable", install)
        self.assertIn("Unregister-ScheduledTask", uninstall)
        env = calls[0][1]["env"]
        self.assertTrue(env["ALGO_SCRIPT"].endswith("notify.py"))
        self.assertEqual((env["ALGO_FOLDER"], env["ALGO_DAILY"], env["ALGO_WEEKLY"]), ("\\算法学习\\", "今晚练什么", "周报与学习快照"))

    def test_weekly_commits_learning_data_and_daily_dry_run_shows_nothing(self):
        shown = []
        with patch.object(notify.coach, "commit_learning_data", return_value="已提交到本地 git") as commit, \
                patch.object(notify, "show", side_effect=lambda *a: shown.append(a)), patch.object(notify, "log"):
            title, lines, attribution = notify.run_weekly(TODAY)
        commit.assert_called_once_with(notify.ROOT, TODAY)
        self.assertEqual(attribution, "已提交到本地 git")
        self.assertEqual(shown[0][0], title)
        with patch.object(notify, "show") as show, patch.object(notify, "ensure_panel") as panel, patch("builtins.print"):
            notify.run_daily(TODAY, dry_run=True)
        show.assert_not_called()
        panel.assert_not_called()


if __name__ == "__main__":
    unittest.main()
