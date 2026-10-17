#!/usr/bin/env python3
"""本机系统通知：每晚的今日计划、每周日的周报摘要。只读本地进度，不联网、不调用任何模型。

用法：
  python tools/notify.py daily       弹出今日计划通知
  python tools/notify.py weekly      弹出周报摘要，并把当天的学习数据提交到本地 git
  python tools/notify.py install     在 Windows 任务计划程序登记两个任务：每晚 19:25、每周日 20:35
  python tools/notify.py uninstall   删除这两个任务
  python tools/notify.py status      查看两个任务的状态和下次运行时间
  加 --dry-run 只打印通知内容，不弹出。

通知用 Windows 自带的系统通知（显示来源为 Windows PowerShell），点击打开今日计划；弹出前会确认本地学习面板在运行。
错过的时间（关机、睡眠）会在开机后补发一次。运行记录写在 .runtime/notify.log。
"""
import argparse
import base64
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.request import urlopen
from xml.sax.saxutils import escape, quoteattr

try:
    from . import coach, insights, knowledge, learner
except ImportError:
    import coach, insights, knowledge, learner

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "learning-state.json"
LOG = ROOT / "learning-log.md"
PANEL = "http://127.0.0.1:8765"
TASK_FOLDER = "\\算法学习\\"
TASKS = {"daily": ("今晚练什么", "每晚 19:25"), "weekly": ("周报与学习快照", "每周日 20:35")}
# 借用 Windows PowerShell 的应用标识显示通知，不需要安装额外模块。
APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
KIND = {"review": "复习", "new": "新题", "calibration": "校准"}
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ---------- 通知内容 ----------

def daily_message(plan):
    """今日计划：正式任务、口述复习和短时回忆，加上画像里的第一条重点。不写解法。"""
    title = f"今晚练什么 · {plan['mode']} {plan['minutes']} 分钟"
    pending = [t for t in plan["tasks"] if not t.get("recorded")]
    focus = (plan.get("profile") or {}).get("focus") or []
    if not pending and not plan["oral"] and not plan["short_recall"]:
        return title, ["今天的计划已经完成，记得点“结束并保存”。"], focus[0] if focus else "明天按复习队列继续。"
    items = [f"{'推荐' if t.get('source') == 'recommended' else KIND.get(t['kind'], '练习')} LC{t['id']} {t['title']}" for t in pending]
    lines = ["；".join(items) if items else "正式任务已完成"]
    extra = []
    if plan["oral"]:
        extra.append("口述复习 " + "、".join("LC" + r["id"] for r in plan["oral"]) + "（每道约 2 分钟）")
    if plan["short_recall"]:
        extra.append("短时回忆 " + "、".join("LC" + r["id"] for r in plan["short_recall"]))
    if extra:
        lines.append("；".join(extra))
    return title, lines, ("重点：" + focus[0]) if focus else ""


def weekly_message(report, snapshot=None):
    week = report["week"]
    title = f"本周算法周报 · {week['start'][5:]} 至 {week['end'][5:]}"
    rate = f"独立完成率 {week['independent_rate']}%" if week["independent_rate"] is not None else "还没有结果明确的练习"
    lines = [f"学习 {week['active_days']} 天，练习 {week['practices']} 次，{rate}",
             "下周重点：" + (report["focus"][0] if report["focus"] else "按今日计划推进。")]
    return title, lines, snapshot or ""


def toast_xml(title, lines, attribution="", url=PANEL + "/#today"):
    # 系统通知最多显示标题和两行正文；补充信息放在底部的小字里。
    texts = "".join(f"<text>{escape(text)}</text>" for text in [title, *lines][:3])
    if attribution:
        texts += f'<text placement="attribution">{escape(attribution)}</text>'
    return (f'<toast activationType="protocol" launch={quoteattr(url)}><visual><binding template="ToastGeneric">{texts}</binding></visual>'
            f'<actions><action content="打开今日计划" activationType="protocol" arguments={quoteattr(url)}/></actions></toast>')


# ---------- 弹出与面板 ----------

def powershell(script, env=None, timeout=60):
    """用 -EncodedCommand 执行，参数经环境变量传入，中文和引号都不用转义。"""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
                          env={**os.environ, **(env or {})}, capture_output=True, timeout=timeout, creationflags=NO_WINDOW)


SHOW = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($env:ALGO_TOAST_XML)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:ALGO_TOAST_APP).Show([Windows.UI.Notifications.ToastNotification]::new($xml))
"""


def show(title, lines, attribution=""):
    if sys.platform != "win32":
        raise OSError("系统通知目前只支持 Windows")
    done = powershell(SHOW, {"ALGO_TOAST_XML": toast_xml(title, lines, attribution), "ALGO_TOAST_APP": APP_ID})
    if done.returncode:
        raise OSError("弹出通知失败：" + done.stderr.decode("utf-8", errors="replace").strip()[-300:])


def ensure_panel():
    """点通知要打开学习面板；面板没在运行时，在后台启动一个（只监听本机）。"""
    try:
        with urlopen(PANEL + "/api/health", timeout=2):
            return False
    except OSError:
        pass
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    with open(runtime / "dashboard.stdout.log", "ab") as out, open(runtime / "dashboard.stderr.log", "ab") as err:
        # 脱离计划任务的进程组，任务结束后面板继续运行。
        flags = NO_WINDOW | getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | 0x01000000
        try:
            subprocess.Popen([str(pythonw if pythonw.exists() else sys.executable), str(ROOT / "tools" / "dashboard.py")], cwd=str(ROOT),
                             stdout=out, stderr=err, stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)
        except OSError:
            subprocess.Popen([str(pythonw if pythonw.exists() else sys.executable), str(ROOT / "tools" / "dashboard.py")], cwd=str(ROOT),
                             stdout=out, stderr=err, stdin=subprocess.DEVNULL, creationflags=flags & ~0x01000000, close_fds=True)
    return True


def log(text):
    try:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with open(ROOT / ".runtime" / "notify.log", "a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now().isoformat(timespec='seconds')} {text}\n")
    except OSError:
        pass


# ---------- 两种通知 ----------

def run_daily(today, dry_run=False):
    state = coach.load(STATE)
    plan = coach.build_plan(state, today, learner.settings(state)["daily_minutes"], coach.log_mentions(LOG), knowledge.error_events(state, LOG))
    message = daily_message(plan)
    deliver(message, dry_run, panel=True)
    return message


def run_weekly(today, dry_run=False):
    state = coach.load(STATE)
    report = insights.ability_report(state, today, LOG)
    snapshot = None if dry_run else coach.commit_learning_data(ROOT, today)
    message = weekly_message(report, snapshot)
    deliver(message, dry_run, panel=False)
    return message


def deliver(message, dry_run, panel):
    title, lines, attribution = message
    if dry_run:
        print("\n".join([title, *lines] + ([attribution] if attribution else [])))
        return
    if panel:
        ensure_panel()
    show(title, lines, attribution)
    log("已弹出：" + title)


# ---------- 任务计划程序 ----------

INSTALL = r"""
$ErrorActionPreference = 'Stop'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
$daily = New-ScheduledTaskAction -Execute $env:ALGO_PYTHONW -Argument ('"' + $env:ALGO_SCRIPT + '" daily') -WorkingDirectory $env:ALGO_ROOT
$weekly = New-ScheduledTaskAction -Execute $env:ALGO_PYTHONW -Argument ('"' + $env:ALGO_SCRIPT + '" weekly') -WorkingDirectory $env:ALGO_ROOT
Register-ScheduledTask -TaskPath $env:ALGO_FOLDER -TaskName $env:ALGO_DAILY -Action $daily -Trigger (New-ScheduledTaskTrigger -Daily -At '19:25') -Settings $settings -Description '算法学习：弹出今日计划（本机通知，不联网）' -Force | Out-Null
Register-ScheduledTask -TaskPath $env:ALGO_FOLDER -TaskName $env:ALGO_WEEKLY -Action $weekly -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '20:35') -Settings $settings -Description '算法学习：周报摘要，并把学习数据提交到本地 git' -Force | Out-Null
"""
UNINSTALL = r"""
foreach ($name in @($env:ALGO_DAILY, $env:ALGO_WEEKLY)) {
  Unregister-ScheduledTask -TaskPath $env:ALGO_FOLDER -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
}
"""
STATUS = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Get-ScheduledTask -TaskPath $env:ALGO_FOLDER -ErrorAction SilentlyContinue | ForEach-Object {
  $info = $_ | Get-ScheduledTaskInfo
  $last = if ($info.LastRunTime -and $info.LastRunTime.Year -gt 2000) { '{0:yyyy-MM-dd HH:mm}（结果 {1}）' -f $info.LastRunTime, $info.LastTaskResult } else { '' }
  '{0}|{1}|{2:yyyy-MM-dd HH:mm}|{3}' -f $_.TaskName, $_.State, $info.NextRunTime, $last
}
"""


def task_env():
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return {"ALGO_PYTHONW": str(pythonw if pythonw.exists() else sys.executable), "ALGO_SCRIPT": str(Path(__file__).resolve()),
            "ALGO_ROOT": str(ROOT), "ALGO_FOLDER": TASK_FOLDER, "ALGO_DAILY": TASKS["daily"][0], "ALGO_WEEKLY": TASKS["weekly"][0]}


def manage(action):
    done = powershell({"install": INSTALL, "uninstall": UNINSTALL, "status": STATUS}[action], task_env())
    output = done.stdout.decode("utf-8", errors="replace").strip()
    if done.returncode:
        raise OSError(f"{action} 失败：" + (done.stderr.decode("utf-8", errors="replace").strip()[-400:] or output))
    return output


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="算法学习本机通知")
    parser.add_argument("action", choices=["daily", "weekly", "install", "uninstall", "status"])
    parser.add_argument("--dry-run", action="store_true", help="只打印通知内容，不弹出")
    args = parser.parse_args(argv)
    try:
        if args.action == "daily":
            run_daily(date.today(), args.dry_run)
        elif args.action == "weekly":
            run_weekly(date.today(), args.dry_run)
        elif args.action == "install":
            manage("install")
            print("已登记：" + "；".join(f"{name}（{when}）" for name, when in TASKS.values()) + "。可在“任务计划程序 → 算法学习”里查看。")
        elif args.action == "uninstall":
            manage("uninstall")
            print("已删除两个通知任务。")
        else:
            rows = [line.split("|") for line in manage("status").splitlines() if line.strip()]
            print("\n".join(f"{name}：{'已启用' if state == 'Ready' else state}，下次 {nxt or '—'}，上次 {last or '还没运行过'}"
                            for name, state, nxt, last in rows) or "还没有登记通知任务。")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        log(f"{args.action} 失败：{exc}")
        parser.exit(1, f"错误：{exc}\n")


if __name__ == "__main__":
    main()
