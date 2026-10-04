"""环境：变量绑定表 + 指向外层环境的指针。

这是"词法作用域"的关键：每次查找名字都先看本层，找不到就往外层走。
`lookup` 只从内向外**读**，写入永远发生在 `define` 指定的那一层，
因此闭包能正确捕获"定义时"的环境（spec §9）。
"""

from errors import SchemeError


class Environment:
    """一层作用域。内层通过 parent 指向外层，最外层的 parent 为 None。"""

    __slots__ = ("_bindings", "parent")

    def __init__(self, parent=None):
        self._bindings = {}
        self.parent = parent

    def define(self, name, value):
        """在当前层绑定（或覆盖）一个名字。`define` 用它。"""
        self._bindings[name] = value
        return value

    def lookup(self, name):
        """由内向外查找变量的值，找不到就报错。"""
        env = self
        while env is not None:
            bindings = env._bindings
            if name in bindings:
                return bindings[name]
            env = env.parent
        raise SchemeError("未定义的符号：%s" % name.name)

    def is_bound(self, name):
        """这个名字是否已经在某一层被绑定（供 cond 判断 else 是否被用户占用）。"""
        env = self
        while env is not None:
            if name in env._bindings:
                return True
            env = env.parent
        return False

    def child(self):
        """创建一层以内层身份出现的新作用域（函数调用、let 用）。"""
        return Environment(parent=self)
