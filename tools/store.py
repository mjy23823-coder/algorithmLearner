"""学习记录的存储层：带版本校验的读写、文件锁、原子写入、每日备份和本地 git 提交。

只依赖标准库，不引用其他教练模块，供 records / planner / coach 等上层模块共用。
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path


class State(dict):
    """保留读取时的版本，避免网页和聊天教练互相覆盖进度。"""
    source_hash = None


def digest(data):
    return hashlib.sha256(data).hexdigest()


# 正常持锁只有毫秒级，超过该时长的锁视为异常退出遗留。
# 按文件时间判断而不探测 PID：Windows 上 os.kill(pid, 0) 会结束目标进程。
STALE_LOCK_SECONDS = 30


def lock_is_stale(lock):
    try:
        return time.time() - lock.stat().st_mtime > STALE_LOCK_SECONDS
    except FileNotFoundError:
        return False


@contextmanager
def file_lock(path):
    lock = path.with_name(path.name + ".lock")
    deadline = time.monotonic() + 5
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if lock_is_stale(lock):
                try:
                    lock.unlink()
                except FileNotFoundError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise ValueError("记录正在被其他程序更新，请稍后重试；若程序异常退出，请检查 .lock 文件")
            time.sleep(0.05)
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def atomic_write(path, data):
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, str(path))
    finally:
        if os.path.exists(name):
            os.unlink(name)


# ---------- 读写 ----------

def load(path):
    raw = path.read_bytes()
    state = State(json.loads(raw.decode("utf-8-sig")))
    state.source_hash = digest(raw)
    return state


def save(path, state):
    data = (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with file_lock(path):
        expected = getattr(state, "source_hash", None)
        if expected and (not path.exists() or digest(path.read_bytes()) != expected):
            raise ValueError("学习记录已被其他会话更新，请刷新后重试")
        if path.exists():
            shutil.copyfile(path, path.with_name(path.name + ".bak"))
            rotate_backup(path)
        atomic_write(path, data)
    if isinstance(state, State):
        state.source_hash = digest(data)


BACKUP_DAYS = 14


def rotate_backup(path, today=None):
    """每天第一次写入前，把当天开始时的进度存到 backups/，只保留最近 14 天（.bak 只保留上一次写入前的版本）。"""
    folder = path.parent / "backups"
    folder.mkdir(exist_ok=True)
    target = folder / f"{path.stem}-{(today or date.today()).isoformat()}{path.suffix}"
    if not target.exists():
        shutil.copyfile(path, target)
    for old in sorted(folder.glob(f"{path.stem}-????-??-??{path.suffix}"))[:-BACKUP_DAYS]:
        old.unlink()



LEARNING_DATA = ("learning-state.json", "learning-log.md", "solutions")


def commit_learning_data(root, today):
    """在本地 git 仓库里提交当天的学习数据（进度、日志、运行过的代码）。只提交这几项，不动其他改动；
    没有仓库、没有变化或 git 出错时跳过，不影响保存。仓库不配置远程，数据不会上传。"""
    root = Path(root)
    if not (root / ".git").exists() or not shutil.which("git"):
        return None
    paths = [name for name in LEARNING_DATA if (root / name).exists()]

    def git(*args):
        return subprocess.run(["git", *args], cwd=str(root), capture_output=True, timeout=30,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        if git("add", "--", *paths).returncode:
            return None
        if not git("diff", "--cached", "--quiet", "--", *paths).returncode:
            return "学习数据没有新变化，无需提交"
        done = git("commit", "-q", "-m", f"学习记录 {today.isoformat()}", "--", *paths)
        return "已提交到本地 git" if done.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


