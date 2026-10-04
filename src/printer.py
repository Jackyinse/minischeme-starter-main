"""流水线第 3 步：打印（值 -> 文本）。

本模块只回答一个问题："这个值该显示成什么文字？"
与求值完全解耦，所以可以单独测试：给一个值，看输出是否符合 spec §8 的表格。

spec §8 的对应关系：
    整数 42 / 浮点 0.5 / 布尔 #t #f / 符号 foo / 字符串 "hello"（带引号、转义）
    真列表 (1 2 3) / 点对 (1 . 2) / 空表 () / 过程 #<procedure>
"""

from values import NIL, Closure, Pair, Primitive, String, Symbol

# 字符串里的特殊字符要打印成转义形式（spec §8）
_ESCAPES = (("\\", "\\\\"), ('"', '\\"'), ("\n", "\\n"), ("\t", "\\t"), ("\r", "\\r"))


def to_string(value):
    """把值转换成"可被读回"的文本，用于顶层打印结果。"""
    if value is True:
        return "#t"
    if value is False:
        return "#f"
    if value is NIL:
        return "()"
    if isinstance(value, String):
        return _quote_string(value.text)
    if isinstance(value, Symbol):
        return value.name
    if isinstance(value, Pair):
        return _pair_to_string(value)
    if isinstance(value, (Primitive, Closure)):
        # spec §8 注明：验收测试不依赖过程的确切格式。
        return "#<procedure>"
    if isinstance(value, (int, float)):
        return _number_to_string(value)
    return repr(value)  # 兜底：理论上不会走到这里


def to_display_string(value):
    """把值转换成 `display` 输出的文本：字符串不加引号。"""
    if isinstance(value, String):
        return value.text
    return to_string(value)


def _number_to_string(value):
    """数字的打印：整数原样（42），浮点用最短往返表示（0.5 / 1024.0）。"""
    if isinstance(value, int):
        return str(value)
    return repr(value)  # float：repr 保证 0.1+0.2 这类值不被美化


def _quote_string(text):
    """字符串字面量的打印形式：带双引号，并把换行/制表符等转义。"""
    result = text
    for raw, escaped in _ESCAPES:
        result = result.replace(raw, escaped)
    return '"' + result + '"'


def _pair_to_string(pair):
    """点对链的打印：`(1 2 3)`；链条结尾不是空表时打印成点对 `(1 . 2)`。"""
    parts = []
    current = pair
    while isinstance(current, Pair):
        parts.append(to_string(current.car))
        current = current.cdr
    if current is NIL:
        return "(" + " ".join(parts) + ")"
    # 非真列表（improper list）：最后一段用点号接上。
    return "(" + " ".join(parts) + " . " + to_string(current) + ")"
