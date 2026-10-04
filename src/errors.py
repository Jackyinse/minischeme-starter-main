"""统一的错误类型。

解释器的任何一层（词法 / 语法 / 求值）发现程序有问题时，都抛出 SchemeError。
只有最外层的入口 src/main.py 负责把它变成一行可读的错误信息，
这样中间各层都不必关心"如何报告错误"，职责保持单一。
"""


class SchemeError(Exception):
    """mini-Scheme 程序本身出错（语法错、未定义变量、类型不符等）。"""

    def __init__(self, message, line=None, column=None):
        # 出错位置是可选的：求值期的错误往往只知道出错原因，不知道行列。
        self.message = message
        self.line = line
        self.column = column
        super().__init__(self.describe())

    def describe(self):
        """返回带位置的错误描述，供顶层打印。"""
        if self.line is None:
            return self.message
        if self.column is None:
            return "第 %d 行：%s" % (self.line, self.message)
        return "第 %d 行第 %d 列：%s" % (self.line, self.column, self.message)
