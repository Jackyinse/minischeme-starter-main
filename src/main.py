#!/usr/bin/env python3
"""mini-Scheme 解释器入口（spec §2：入口必须是 src/main.py）。

用法：
    python3 src/main.py file1.scm [file2.scm ...]   # 按顺序求值文件
    python3 src/main.py                             # 没有参数时从标准输入读
    python3 src/main.py -                           # 显式从标准输入读（同上一行）

本文件只做三件事：保证能 import 到同目录的模块、解析命令行参数、报告错误。
真正的流水线在各自的模块里：

    lexer.py            程序文本 → 词法单元列表
    parser.py           词法单元 → 表达式（点对链）
    values.py           运行时数据（点对链 / 符号 / 字符串 / 过程）
    environment.py      变量绑定表 + 指向外层环境的指针
    printer.py          值 → 文本
    standard_library.py spec §5 的全部内置函数
    evaluator.py        表达式 → 值（特殊形式 + apply）
    cli.py              顶层求值循环与逐行打印
    errors.py           统一的错误类型 SchemeError
"""

import os
import sys

# 直接以 `python3 src/main.py` 运行时，Python 会把 src/ 放进 sys.path；
# 但用 `python3 -m`、符号链接或从别处加载时不一定，这里显式补上，
# 让同目录的兄弟模块在任何调用方式下都能被 import。
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from cli import run_in_thread  # noqa: E402  (必须在 sys.path 调整之后)
from errors import SchemeError  # noqa: E402


def _configure_output():
    """让输出始终是 UTF-8，避免不同平台的默认编码导致乱码。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _parse_arguments(argv):
    """解析命令行参数，返回要运行的文件路径列表。

    没有参数、或参数是 `-` 时表示从标准输入读（用 None 代表 stdin）。
    """
    if not argv:
        return [None]
    paths = []
    for argument in argv:
        if argument == "-":
            paths.append(None)
        elif argument.startswith("-"):
            raise SchemeError("不认识的选项：%s\n用法：python3 main.py [file.scm ...]" % argument)
        else:
            paths.append(argument)
    return paths


def main(argv=None):
    """程序入口：解析参数 → 运行 → 统一报告错误。"""
    _configure_output()
    arguments = sys.argv[1:] if argv is None else list(argv)

    try:
        paths = _parse_arguments(arguments)
    except SchemeError as error:
        print("错误：%s" % error, file=sys.stderr)
        return 2

    try:
        run_in_thread(paths)          # 在工作线程里跑，栈更大、递归更深
    except SchemeError as error:
        print("错误：%s" % error, file=sys.stderr)
        return 1
    except RecursionError:
        print("错误：递归层数过深，已超出解释器上限", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    except (BrokenPipeError, ValueError):             # 输出被提前关闭（如 head）
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
