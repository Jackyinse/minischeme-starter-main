"""流水线第 2 步：语法分析（词法单元列表 -> 表达式）。

本模块只回答一个问题："这些零件怎么组合成嵌套的表达式？"
它不做任何求值，也不认识 if/lambda 之类的关键字——
`if` 在这里只是一个普通符号，它的特殊含义由 evaluator.py 决定。

表达式与运行时数据共用 values.Pair 表示，所以 `'(1 2 3)` 解析出来就是
一条点对链，是"数据"还是"代码"完全取决于求值器怎么用它。
"""

from errors import SchemeError
from lexer import BOOLEAN, LPAREN, NUMBER, QUOTE, RPAREN, STRING, SYMBOL, tokenize
from values import Pair, String, Symbol, from_python_list

# 引用简写 'x 展开成 (quote x)
_QUOTE_SYMBOL = Symbol("quote")


class Parser:
    """递归下降分析器：把词法单元列表组装成表达式。

    表达式只有四种形态：
      - 原子：数字 / 布尔 / 字符串 / 符号
      - 点对链：(操作符 参数...) 也是一个 Pair
      - 空表：'() 或 ()
      - 引用简写展开后的 (quote 数据)
    """

    def __init__(self, tokens):
        self.tokens = tokens
        self.position = 0

    # ----- 对外的两个入口 -------------------------------------------------

    def parse_all(self):
        """解析出全部顶层表达式（一个 .scm 文件里可以有很多个）。"""
        expressions = []
        while self.position < len(self.tokens):
            expressions.append(self.parse_expression())
        return expressions

    def parse_expression(self):
        """解析一个表达式。"""
        token = self._peek()
        if token is None:
            raise SchemeError("程序意外结束：还缺少一个表达式")

        if token.kind == LPAREN:
            self.position += 1
            return self._parse_list(token)
        if token.kind == RPAREN:
            raise SchemeError("多出一个右括号 ')'", token.line, token.column)
        if token.kind == QUOTE:
            self.position += 1
            # 'x 是 (quote x) 的简写，直接在这里展开，求值器只需处理 quote。
            return from_python_list([_QUOTE_SYMBOL, self.parse_expression()])

        # 原子：数字 / 布尔 / 字符串 / 符号，词法阶段已经算出它的值。
        self.position += 1
        if token.kind == STRING:
            return String(token.text)
        if token.kind == SYMBOL:
            return Symbol(token.text)
        return token.text  # NUMBER / BOOLEAN 的词法值就是 Python 的 int/float/bool

    # ----- 内部工具 -------------------------------------------------------

    def _peek(self):
        """看一眼下一个词法单元，但不消费它。"""
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return None

    def _parse_list(self, open_token):
        """解析 `(` 之后的内容，直到匹配的 `)`。"""
        elements = []
        while True:
            token = self._peek()
            if token is None:
                raise SchemeError("括号没有闭合：缺少与 '(' 配对的 ')'",
                                  open_token.line, open_token.column)
            if token.kind == RPAREN:
                self.position += 1
                return from_python_list(elements)
            elements.append(self.parse_expression())


def parse(source):
    """便捷函数：一段程序文本 -> 顶层表达式列表。"""
    return Parser(tokenize(source)).parse_all()
