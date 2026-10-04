"""mini-Scheme 的运行时数据表示（值）。

设计要点（对应 spec §6 与 §11 排错表）：

- 列表不是"数组"，而是**点对链**：`(1 2 3)` 就是 `(1 . (2 . (3 . ())))`。
  因此语法树（代码）与引用数据（`quote` 的结果）共用同一套 Pair 表示，
  `quote` 不需要任何转换，`cons` 造出来的链与 `'(...)` 的链天然一致。
- 空表 Nil 是单例：`(eq? '() '())` → `#t`。
- Symbol 做了驻留（intern）：同名符号共享一个对象，`(eq? 'a 'a)` → `#t`。
- 字符串用专门的 String 类包装，而不是直接用 Python 的 str：
  否则"符号是 str 的子类 / str == str"会导致 `(eq? 'a "a")` 判成相等（spec §11）。
- 布尔与数字直接用 Python 的 bool / int / float，但比较时**先比类型再比值**，
  避免 Python 的 `True == 1`（spec §11）。
"""


class Symbol:
    """符号（变量名 / 操作符名）。同名符号由 intern 表保证唯一。"""

    __slots__ = ("name",)
    _interned = {}

    def __new__(cls, name):
        existing = cls._interned.get(name)
        if existing is not None:
            return existing
        symbol = super().__new__(cls)
        symbol.name = name
        cls._interned[name] = symbol
        return symbol

    def __init__(self, name):
        # 属性已在 __new__ 中设置；这里只需接受同名参数，
        # 否则 Python 会在 __new__ 返回实例后调用 __init__ 时报参数错误。
        pass

    def __repr__(self):
        return "Symbol(%s)" % self.name


class String:
    """字符串值。用独立类型与符号区分开。"""

    __slots__ = ("text",)

    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return "String(%r)" % self.text


class Nil:
    """空表 `()`，同时是列表链的终点。全局单例。"""

    __slots__ = ()
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "Nil()"


NIL = Nil()


class Pair:
    """点对：car 是第一项，cdr 是第二项（通常是链的下一段）。"""

    __slots__ = ("car", "cdr")

    def __init__(self, car, cdr):
        self.car = car
        self.cdr = cdr

    def __repr__(self):
        return "Pair(%r, %r)" % (self.car, self.cdr)


class Primitive:
    """内置过程（spec §5 的标准函数库）。"""

    __slots__ = ("name", "func")

    def __init__(self, name, func):
        self.name = name
        self.func = func

    def __repr__(self):
        return "#<primitive %s>" % self.name


class Closure:
    """用户函数（lambda 产生的闭包）：记住形参、函数体和**定义时**的环境。"""

    __slots__ = ("params", "body", "env", "name")

    def __init__(self, params, body, env, name=None):
        self.params = params          # 形参名列表（list of Symbol）
        self.body = body              # 函数体表达式列表（list of 表达式）
        self.env = env                # 定义处的环境，词法作用域的关键
        self.name = name              # 由 define 命名的函数，仅用于友好打印

    def __repr__(self):
        return "#<closure %s>" % (self.name or "lambda")


def to_python_list(value):
    """把一条点对链拆成 Python 列表；遇到非列表结尾（点对）返回 None。

    求值器内部操作表达式列表、内置的 length/append 等都会用到它。
    """
    items = []
    while isinstance(value, Pair):
        items.append(value.car)
        value = value.cdr
    if value is NIL:
        return items
    return None


def from_python_list(items, tail=NIL):
    """把 Python 列表串成点对链，tail 是链的结尾（默认空表）。"""
    result = tail
    for item in reversed(items):
        result = Pair(item, result)
    return result


def is_true(value):
    """mini-Scheme 的真值判断：**只有 #f 是假**（0、()、"" 都是真）。"""
    return value is not False


def is_number(value):
    """是否为数字。注意 bool 是 int 的子类，必须排除掉。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)
