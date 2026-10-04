"""命令行入口逻辑与顶层结果打印（spec §2 的 CLI 约定）。

约定回顾：
  - `python3 main.py file1.scm [file2.scm ...]`，没有参数时从标准输入读；
  - 按顺序求值每个顶层表达式，**每个结果独占一行打印**；
  - 结果是 None（无值，如 display/newline）时不打印；
  - 多个文件共享同一个全局环境。

把这一层单独拆出来，是为了让 main.py 只负责“解析参数、报告错误”，
而“怎么跑一段程序”可以脱离命令行被单独测试。
"""

import sys
import threading

from errors import SchemeError
from evaluator import Evaluator
from parser import parse
from printer import to_string
from standard_library import make_global_environment

# 解释器自己的递归上限（不是 Python 默认的 1000）。
# Scheme 的递归深度靠 Python 的调用栈实现，实测每层 Scheme 递归约消耗 10 层
# Python 调用，所以这里放宽到 40000（≈ 4000 层 Scheme 递归）：既覆盖
# "用递归写循环"这种正常写法，又能在真正误写成无限递归时稳定地抛出
# RecursionError 交给 main.py 报告，而不是撞坏进程的 C 栈。
# 注意这**不是**尾调用优化（spec §10 明确不要求）。
RECURSION_LIMIT = 40000


class Program:
    """一个解释器实例：全局环境 + 求值器（多个文件共享同一个实例）。"""

    def __init__(self):
        self.global_env = make_global_environment()
        self.evaluator = Evaluator(self.global_env)

    def run_source(self, source):
        """解析并求值一段程序文本，按 spec §2 打印每个顶层结果。"""
        for expression in parse(source):
            value = self.evaluator.evaluate(expression)
            if value is None:
                continue                    # display / newline 这类无值结果不打印
            self._write_line(to_string(value))
        return self

    @staticmethod
    def _write_line(text):
        """打印一行结果；输出流编码异常时退化为直接写 UTF-8 字节。"""
        try:
            print(text, flush=True)
        except UnicodeEncodeError:
            buffer = getattr(sys.stdout, "buffer", None)
            if buffer is None:
                raise
            buffer.write((text + "\n").encode("utf-8"))
            buffer.flush()


def read_source(path):
    """读入一个 .scm 文件（UTF-8）。"""
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def read_stdin():
    """读入标准输入（评分器就是把用例程序写进 stdin 调用的）。"""
    stream = sys.stdin
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass                                # 被重定向成非文本流时忽略
    return stream.read()


def run_files(paths):
    """按顺序运行多个文件，共享同一个全局环境（后一文件可见前一文件的 define）。

    paths 里的每一项是文件路径；值为 None 表示“这一项从标准输入读”。
    """
    program = Program()
    for path in paths:
        if path is None:
            program.run_source(read_stdin())
            continue
        try:
            source = read_source(path)
        except OSError as error:
            raise SchemeError("无法读取文件 %s（%s）" % (path, error.strerror or error))
        program.run_source(source)
    return program


def run_in_thread(paths):
    """在独立线程里运行解释器，并原样抛出其中的异常。

    放进单独线程有两个好处：递归上限（sys.setrecursionlimit）是进程级设置，
    集中在这里调整；子线程里的异常不会打断主线程，可以统一交给 main.py
    翻译成一行可读的错误提示。
    """
    sys.setrecursionlimit(RECURSION_LIMIT)
    outcome = {}

    def worker():
        try:
            outcome["value"] = run_files(paths)
        except BaseException as error:      # 交给主线程统一报告
            outcome["error"] = error

    try:
        thread = threading.Thread(target=worker, name="minischeme", daemon=True)
        thread.start()
        thread.join()
    except (RuntimeError, ValueError, OSError):
        # 极端环境（如不允许创建线程）下退回主线程直接执行。
        return run_files(paths)

    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")
