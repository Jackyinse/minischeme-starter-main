"""流水线第 1 步：词法分析（程序文本 -> 词法单元列表）。

本模块只回答一个问题："这段文本由哪些零件拼成？"
它不关心零件的含义，也绝不判断语法是否正确——
括号是否配对、`if` 后面跟几个表达式，都是下一层（parser.py）的事。
"""

import re

from errors import SchemeError

# 词法单元的种类
LPAREN = "("      # 左括号
RPAREN = ")"      # 右括号
QUOTE = "'"       # 引用简写 'x，等价于 (quote x)
STRING = "string"  # 字符串字面量，如 "hello world"
NUMBER = "number"  # 数字字面量，如 42 / -7 / 2.5
BOOLEAN = "bool"   # 布尔字面量，只能是 #t 或 #f
SYMBOL = "symbol"  # 符号，如 foo / + / null?

# 数字的严格写法：可选正负号 + 整数部分（可带小数部分 / 指数部分）。
# 不用 Python 的 float()/int() 直接试探，是因为它们还会接受 `1_0`、全角数字
# 这类 mini-Scheme 不允许的写法。
_INT_RE = re.compile(r"^[+-]?[0-9]+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:[0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)(?:[eE][+-]?[0-9]+)?$")

# 结束一个符号的字符：空白、括号、引号。`;` 由外层循环单独处理。
_DELIMITERS = "()'\";"

_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


class Token:
    """一个词法单元：种类 + 原文 + 在源文件中的位置（用于报错）。"""

    __slots__ = ("kind", "text", "line", "column")

    def __init__(self, kind, text, line, column):
        self.kind = kind
        self.text = text
        self.line = line
        self.column = column

    def __repr__(self):  # 调试用
        return "Token(%r, %r, %d:%d)" % (self.kind, self.text, self.line, self.column)


def tokenize(source):
    """把整段程序文本切成词法单元列表。

    - `;` 到行尾的内容、以及各种空白，都被跳过；
    - 字符串支持 \\n \\t \\" \\\\ 四种转义，转义在词法阶段就解开；
    - 遇到不认识的零件（如没闭合的字符串）立刻报错并给出行列。
    """
    tokens = []
    index = 0
    line = 1
    column = 1
    length = len(source)

    def advance(count):
        """推进 count 个字符，并维护当前行列号。"""
        nonlocal index, line, column
        for _ in range(count):
            if source[index] == "\n":
                line += 1
                column = 1
            else:
                column += 1
            index += 1

    def advance_to(target):
        """推进到指定的绝对位置（用于整段跳过字符串字面量）。"""
        assert target >= index, "扫描位置只能向前推进"
        advance(target - index)

    while index < length:
        char = source[index]

        if char.isspace():                      # 空白：空格 / 换行 / 制表符
            advance(1)
            continue
        if char == ";":                         # 注释：一直到行尾
            while index < length and source[index] != "\n":
                advance(1)
            continue
        if char == "(":
            tokens.append(Token(LPAREN, "(", line, column))
            advance(1)
            continue
        if char == ")":
            tokens.append(Token(RPAREN, ")", line, column))
            advance(1)
            continue
        if char == "'":
            tokens.append(Token(QUOTE, "'", line, column))
            advance(1)
            continue
        if char == '"':
            token, end = _read_string(source, index, line, column)
            tokens.append(token)
            advance_to(end)  # 跳到收尾双引号之后，行列号由 advance 统一维护
            continue

        # 其余情况都是一个"原子"：数字、布尔或符号。
        start, start_line, start_column = index, line, column
        while index < length and source[index] not in _DELIMITERS and not source[index].isspace():
            advance(1)
        tokens.append(_classify(source[start:index], start_line, start_column))

    return tokens


def _read_string(source, index, line, column):
    """从 `"` 开始解析一个字符串字面量。

    返回 (Token, 收尾双引号之后的扫描位置)，其中 Token 的值是解开转义后的字符串。
    """
    chars = []
    position = index + 1
    length = len(source)
    while True:
        if position >= length:
            raise SchemeError("字符串没有闭合（缺少结尾的双引号）", line, column)
        char = source[position]
        if char == '"':
            break
        if char == "\\":
            position += 1
            if position >= length:
                raise SchemeError("字符串在转义符处意外结束", line, column)
            escape = source[position]
            if escape not in _ESCAPES:
                raise SchemeError("不认识的转义符 \\%s" % escape, line, column)
            chars.append(_ESCAPES[escape])
        else:
            chars.append(char)
        position += 1
    return Token(STRING, "".join(chars), line, column), position + 1


def _classify(text, line, column):
    """判断一个原子是数字、布尔还是符号。"""
    if text == "#t":
        return Token(BOOLEAN, True, line, column)
    if text == "#f":
        return Token(BOOLEAN, False, line, column)
    if _INT_RE.match(text):
        return Token(NUMBER, int(text), line, column)
    if _FLOAT_RE.match(text):
        return Token(NUMBER, float(text), line, column)
    return Token(SYMBOL, text, line, column)
