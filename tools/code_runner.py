"""有时间/内存预算的本地算法测试进程。"""
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

MEMORY_LIMIT = 384 * 1024 * 1024
DEBUG_TIMEOUT = 120  # 单次调试最长保留两分钟，包括停在断点等待用户。


class WindowsJob:
    def __init__(self, process):
        self.handle = None
        if sys.platform != "win32":
            return
        import ctypes
        from ctypes import wintypes
        size = ctypes.c_size_t

        class Basic(ctypes.Structure):
            _fields_ = [("ProcessTime", ctypes.c_longlong), ("JobTime", ctypes.c_longlong), ("Flags", wintypes.DWORD),
                        ("MinWorkingSet", size), ("MaxWorkingSet", size), ("ActiveProcesses", wintypes.DWORD),
                        ("Affinity", size), ("Priority", wintypes.DWORD), ("Scheduling", wintypes.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]

        class Extended(ctypes.Structure):
            _fields_ = [("Basic", Basic), ("IO", IO), ("ProcessMemory", size), ("JobMemory", size), ("PeakProcess", size), ("PeakJob", size)]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.SetInformationJobObject.restype = wintypes.BOOL
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel = kernel
        self.handle = kernel.CreateJobObjectW(None, None)
        limits = Extended()
        limits.Basic.Flags = 0x2000 | 0x100 | 0x8  # kill on close, process memory, one process
        limits.Basic.ActiveProcesses = 1
        limits.ProcessMemory = MEMORY_LIMIT
        if not self.handle or not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(process._handle))):
            error = ctypes.get_last_error()
            self.close()
            raise OSError(f"无法建立本地测试资源限制（Windows {error}）")

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class DebugSession:
    def __init__(self, code, exercise, breakpoints, timeout=None):
        if not isinstance(code, str) or not code.strip() or len(code.encode("utf-8")) > 48000:
            raise ValueError("请输入代码，长度不能超过 48 KB")
        if not isinstance(breakpoints, list) or len(breakpoints) > 100 or any(type(n) is not int or not 1 <= n <= 100000 for n in breakpoints):
            raise ValueError("断点应为不超过 100 个正整数行号")
        self.id = uuid.uuid4().hex
        self.events = queue.Queue()
        self.lock = threading.Lock()
        self.closed = False
        self.folder = tempfile.TemporaryDirectory(prefix="algorithm-debug-")
        self.process = None
        self.job = None
        self.timer = None
        try:
            worker = Path(__file__).with_name("debug_worker.py")
            self.process = subprocess.Popen([sys.executable, "-X", "utf8", "-I", "-S", "-B", str(worker)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, cwd=self.folder.name, env={k: v for k, v in os.environ.items() if k.upper() in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG")},
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), text=True, encoding="utf-8", errors="replace", bufsize=1)
            self.job = WindowsJob(self.process)
            payload = {"code": code, "exercise": exercise, "breakpoints": sorted(set(breakpoints))}
            self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
            threading.Thread(target=self._read, daemon=True).start()
            self.timer = threading.Timer(DEBUG_TIMEOUT if timeout is None else timeout, self._expire)
            self.timer.daemon = True
            self.timer.start()
        except BaseException:
            self.stop()
            raise

    def _expire(self):
        with self.lock:
            if self.closed:
                return
        # 先入队终态，避免轮询在 stop() 已标记 closed、事件尚未入队时丢失超时原因。
        self.events.put({"event": "error", "error": "调试超时，进程已终止，请重新开始"})
        self.stop()

    def _read(self):
        finished = False
        try:
            for line in self.process.stdout:
                try:
                    event = json.loads(line)
                    finished |= event.get("event") in ("done", "error")
                    self.events.put(event)
                except ValueError:
                    pass
        except (OSError, ValueError):
            pass  # 停止会话时关闭管道，读取线程随之退出。
        finally:
            with self.lock:
                if not self.closed and not finished:
                    self.events.put({"event": "error", "error": "调试进程已退出"})
            self.stop()

    def poll(self):
        items = []
        while True:
            try:
                items.append(self.events.get_nowait())
            except queue.Empty:
                break
        return items

    def command(self, command):
        with self.lock:
            if self.closed:
                raise ValueError("调试会话已结束")
            self.process.stdin.write(json.dumps({"command": command}) + "\n")
            self.process.stdin.flush()

    def stop(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
        if self.timer:
            self.timer.cancel()
        try:
            if self.process:
                try:
                    if self.process.poll() is None:
                        try:
                            self.process.kill()
                        except ProcessLookupError:
                            pass
                    self.process.wait(timeout=5)
                finally:
                    for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
                        if pipe:
                            try:
                                pipe.close()
                            except OSError:
                                pass
        finally:
            if self.job:
                self.job.close()
            self.folder.cleanup()


def run_code(code, exercise, extra_cases=None, timeout=5):
    if not isinstance(code, str) or not code.strip() or len(code.encode("utf-8")) > 48000:
        raise ValueError("请输入代码，长度不能超过 48 KB")
    extras = extra_cases or []
    if not isinstance(extras, list) or len(extras) > 20:
        raise ValueError("最多添加 20 组自定义用例")
    cases = exercise["cases"] + extras
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or not isinstance(case.get("args"), list) or len(case["args"]) != len(exercise["params"]) or "expected" not in case:
            raise ValueError(f"第 {index+1} 组用例需要 args（与参数数目一致）和 expected")
    payload = {"code": code, "method": exercise["method"], "codecs": exercise["codecs"], "judge": exercise["judge"],
               "cases": [dict(case, name=str(case.get("name") or f"自定义用例 {i+1}")[:100]) for i, case in enumerate(cases)]}
    started = time.monotonic()
    response = execute(payload, timeout)
    response.update(total=len(cases), passed_count=sum(bool(c.get("passed")) for c in response["cases"]),
                    elapsed_ms=round((time.monotonic()-started)*1000), builtin_count=len(exercise["cases"]))
    response["passed"] = not response.get("error") and response["passed_count"] == response["total"]
    return response


def checked_source(value, label):
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 24000:
        raise ValueError(f"{label}不能为空，且不超过 24 KB")
    return value


def compare_code(code, exercise, reference, generator, count=200, timeout=8):
    """智能体对拍：参考暴力解与随机输入生成器都在同一个受限进程里运行。"""
    if type(count) is not int or not 1 <= count <= 500:
        raise ValueError("随机用例数应为 1～500")
    payload = {"mode": "compare", "code": checked_source(code, "代码"), "reference": checked_source(reference, "参考解"),
               "generator": checked_source(generator, "输入生成器"), "count": count, "method": exercise["method"],
               "codecs": exercise["codecs"], "judge": exercise["judge"]}
    return execute(payload, timeout)


def benchmark_code(code, exercise, generator, sizes, timeout=8):
    if not isinstance(sizes, list) or not 1 <= len(sizes) <= 6 or any(type(n) is not int or not 1 <= n <= 1000000 for n in sizes):
        raise ValueError("输入规模需要 1～6 个 1～1000000 的整数")
    payload = {"mode": "benchmark", "code": checked_source(code, "代码"), "generator": checked_source(generator, "输入生成器"),
               "sizes": sorted(sizes), "method": exercise["method"], "codecs": exercise["codecs"], "judge": exercise["judge"]}
    return execute(payload, timeout)


def execute(payload, timeout):
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(encoded) > 160000:
        raise ValueError("代码与测试数据合计过大")
    env = {k: v for k, v in os.environ.items() if k.upper() in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG")}
    worker = Path(__file__).with_name("submission_worker.py")
    with tempfile.TemporaryDirectory(prefix="algorithm-run-") as folder:
        process = subprocess.Popen([sys.executable, "-I", "-S", "-B", str(worker)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, cwd=folder, env=env,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        job = None
        try:
            # 子进程等待 stdin，资源限制建立成功后才会收到用户代码。
            job = WindowsJob(process)
            stdout, stderr = process.communicate(encoded, timeout=timeout)
            if process.returncode:
                details = stderr.decode("utf-8", errors="replace").strip().splitlines()
                response = {"cases": [], "stdout": "", "error": "测试进程未正常结束" + ("：" + details[-1][:500] if details else "，可能超过内存限制或递归过深"),
                            "exit_code": process.returncode}
            else:
                try:
                    response = json.loads(stdout.decode("utf-8"))
                except (ValueError, UnicodeError):
                    response = {"cases": [], "stdout": "", "error": "测试进程没有返回有效结果"}
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            response = {"cases": [], "stdout": "", "error": f"运行超过 {timeout} 秒，已终止；请检查循环终止条件"}
        except Exception:
            process.kill(); process.communicate()
            raise
        finally:
            if job:
                job.close()
    return response
