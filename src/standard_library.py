"""流水线第 4 步：内置库（spec §5 的全部标准函数）。

这些过程与特殊形式不同：**参数先全部求值，再调用**（README §4）。
因此每个函数拿到的都是已经算好的"值"，只负责算结果。

按 spec §5 的分类组织：
    算术 / 比较 / 布尔 / 列表 / 谓词 / 输出

注册方式：用 @_primitive("名字") 装饰器把函数登记进 _BUILTINS，
make_global_environment() 再把整张表装进初始环境——
这样"有哪些内置过程"只有一处定义，不会出现漏装或多装。
"""

from environment import Environment
from errors import SchemeError
from printer import to_display_string
from values import (
    NIL,
    Closure,
    Pair,
    Primitive,
    String,
    Symbol,
    from_python_list,
    is_number,
    is_true,
    to_python_list,
)

# 内置过程的注册表：元素为 (Scheme 里的名字, 实现函数)
_BUILTINS = []


def _primitive(name):
    """装饰器：把一个 Python 函数注册为名为 name 的内置过程。"""
    def register(func):
        _BUILTINS.append((name, func))
        return func
    return register


# ---------------------------------------------------------------------------
# 参数校验小工具：出错信息统一，鲁棒性的第一道防线
# ---------------------------------------------------------------------------

def _check_arity(name, args, minimum, maximum=None):
    """检查参数个数是否在 [minimum, maximum] 内（maximum=None 表示不限）。"""
    count = len(args)
    if count < minimum or (maximum is not None and count > maximum):
        if maximum is None:
            expected = "至少 %d 个" % minimum
        elif minimum == maximum:
            expected = "%d 个" % minimum
        else:
            expected = "%d 到 %d 个" % (minimum, maximum)
        raise SchemeError("%s：需要%s参数，收到 %d 个" % (name, expected, count))


def _check_number(name, value):
    """参数必须是数字（布尔不算数字）。"""
    if not is_number(value):
        raise SchemeError("%s：参数必须是数字，得到 %s" % (name, to_display_string(value)))
    return value


def _check_integer(name, value):
    """参数必须是整数（modulo / quotient / even? 等用）。"""
    _check_number(name, value)
    if isinstance(value, float) and not value.is_integer():
        raise SchemeError("%s：参数必须是整数，得到 %s" % (name, to_display_string(value)))
    return value


def _check_pair(name, value):
    """参数必须是点对（car / cdr 用）。"""
    if not isinstance(value, Pair):
        raise SchemeError("%s：参数必须是点对，得到 %s" % (name, to_display_string(value)))
    return value


def _check_proper_list(name, value):
    """参数必须是真列表；返回其对应的 Python 列表。"""
    items = to_python_list(value)
    if items is None:
        raise SchemeError("%s：参数必须是真列表，得到 %s" % (name, to_display_string(value)))
    return items


# ---------------------------------------------------------------------------
# 算术
# ---------------------------------------------------------------------------

def _check_all_numbers(name, args):
    for value in args:
        _check_number(name, value)
    return args


def _sum(args):
    """(+) → 0；(+ 1 2 3) → 6。"""
    _check_arity("+", args, 0)
    total = 0
    for value in _check_all_numbers("+", args):
        total += value
    return total


def _difference(args):
    """(- 5) → -5；(- 10 4 1) → 5。"""
    _check_arity("-", args, 1)
    _check_all_numbers("-", args)
    if len(args) == 1:
        return -args[0]
    result = args[0]                        # 从左往右依次相减，首项是起点而非 0
    for value in args[1:]:
        result -= value
    return result


def _product(args):
    """(*) → 1；(* 2 3 4) → 24。"""
    _check_arity("*", args, 0)
    result = 1
    for value in _check_all_numbers("*", args):
        result *= value
    return result


def _safe_divisor(name, value):
    """除法前检查除数不为零（spec §10 说错误行为未定义，但给出清楚提示更友好）。"""
    if value == 0:
        raise SchemeError("%s：除数不能为 0" % name)
    return value


def _exact_quotient(left, right):
    """整数除法，商**向零截断**：(/ -7 2) → -3（不是 Python 向下取整的 -4）。"""
    quotient = abs(left) // abs(right)
    return -quotient if (left < 0) != (right < 0) else quotient


def _divide(left, right):
    """两个整数得整数商；只要有一个浮点就按浮点除。"""
    if isinstance(left, int) and isinstance(right, int):
        return _exact_quotient(left, right)
    return left / right


def _division(args):
    """(/ 2) → 0.5（单参数求倒数）；(/ 7 2) → 3（整数商）。"""
    _check_arity("/", args, 1)
    _check_all_numbers("/", args)
    if len(args) == 1:
        return 1 / _safe_divisor("/", args[0])
    result = args[0]
    for value in args[1:]:
        result = _divide(result, _safe_divisor("/", value))
    return result


def _power(base, exponent):
    """乘方：(expt 2 10) → 1024；出现浮点则按浮点算。"""
    if isinstance(base, int) and isinstance(exponent, int) and exponent >= 0:
        return base ** exponent
    return float(base) ** float(exponent)


# ---------------------------------------------------------------------------
# 比较：(< 2 3 4) 这种链式写法要求相邻两两都成立
# ---------------------------------------------------------------------------

def _ordering(left, right):
    """把两个值映射成可比较的键。

    数字比大小，符号按名字的字典序（spec §5 说比较"支持数字与符号"）；
    跨类型（数字 vs 符号）没有定义，明确报错而不是让 Python 抛 TypeError。
    """
    if is_number(left) and is_number(right):
        return left, right
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return left.name, right.name
    raise SchemeError("不能比较 %s 与 %s" % (to_display_string(left), to_display_string(right)))


def _compare(name, relation, args):
    """链式比较的公共实现：< > <= >= 用来比大小，= 用 _compare_equal。"""
    _check_arity(name, args, 2)
    for index in range(len(args) - 1):
        left, right = _ordering(args[index], args[index + 1])
        if not relation(left, right):
            return False                    # 有一对不成立，整条链就是假
    return True


def _compare_equal(name, args):
    """`=` 的链式比较：只在数字（或只在符号）之间进行。"""
    _check_arity(name, args, 2)
    for index in range(len(args) - 1):
        left, right = _ordering(args[index], args[index + 1])
        if left != right:
            return False
    return True


# ---------------------------------------------------------------------------
# 相等性：eq? 比同一性，equal? 比结构（spec §11 排错表）
# ---------------------------------------------------------------------------

def _eq_values(left, right):
    """eq? 的规则：符号 / 数字 / 布尔 / 字符串按值比较，复合数据按同一性。

    必须**先比类型再比值**，否则 Python 的 `True == 1`、符号与字符串相等
    会把 `(eq? #t 1)`、`(eq? 'a "a")` 判成真（spec §11）。
    """
    if left is right:                       # 同一对象（含空表单例、驻留符号）
        return True
    if isinstance(left, bool) or isinstance(right, bool):
        return False                        # 布尔只有 #t/#f 两种，已由上一行处理完
    if is_number(left) and is_number(right):
        return type(left) is type(right) and left == right
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return left.name == right.name
    if isinstance(left, String) and isinstance(right, String):
        return left.text == right.text
    return False                            # 列表等复合数据：不是同一对象就不 eq?


def _equal_values(left, right):
    """equal? 的规则：逐层比较结构。"""
    if left is right:
        return True
    if isinstance(left, Pair) and isinstance(right, Pair):
        # cdr 方向用循环推进，避免长列表把 Python 的递归深度吃光。
        while isinstance(left, Pair) and isinstance(right, Pair):
            if not _equal_values(left.car, right.car):
                return False
            left, right = left.cdr, right.cdr
        return _equal_values(left, right)
    return _eq_values(left, right)


# ---------------------------------------------------------------------------
# 算术（注册）
# ---------------------------------------------------------------------------

@_primitive("+")
def _builtin_add(args):
    return _sum(args)


@_primitive("-")
def _builtin_subtract(args):
    return _difference(args)


@_primitive("*")
def _builtin_multiply(args):
    return _product(args)


@_primitive("/")
def _builtin_divide(args):
    return _division(args)


@_primitive("modulo")
def _builtin_modulo(args):
    _check_arity("modulo", args, 2, 2)
    left, right = (_check_integer("modulo", value) for value in args)
    return left % _safe_divisor("modulo", right)     # 结果与除数同号（R7RS 语义）


@_primitive("quotient")
def _builtin_quotient(args):
    _check_arity("quotient", args, 2, 2)
    left, right = (_check_integer("quotient", value) for value in args)
    return _exact_quotient(left, _safe_divisor("quotient", right))


@_primitive("expt")
def _builtin_expt(args):
    _check_arity("expt", args, 2, 2)
    return _power(_check_number("expt", args[0]), _check_number("expt", args[1]))


@_primitive("abs")
def _builtin_abs(args):
    _check_arity("abs", args, 1, 1)
    return abs(_check_number("abs", args[0]))


# ---------------------------------------------------------------------------
# 比较（注册）
# ---------------------------------------------------------------------------

@_primitive("=")
def _builtin_num_eq(args):
    return _compare_equal("=", args)


@_primitive("<")
def _builtin_lt(args):
    return _compare("<", lambda left, right: left < right, args)


@_primitive(">")
def _builtin_gt(args):
    return _compare(">", lambda left, right: left > right, args)


@_primitive("<=")
def _builtin_le(args):
    return _compare("<=", lambda left, right: left <= right, args)


@_primitive(">=")
def _builtin_ge(args):
    return _compare(">=", lambda left, right: left >= right, args)


# ---------------------------------------------------------------------------
# 布尔
# ---------------------------------------------------------------------------

@_primitive("not")
def _builtin_not(args):
    _check_arity("not", args, 1, 1)
    return not is_true(args[0])             # 只有 #f 取反为 #t：(not 0) → #f


# ---------------------------------------------------------------------------
# 列表（点对链）
# ---------------------------------------------------------------------------

@_primitive("cons")
def _builtin_cons(args):
    _check_arity("cons", args, 2, 2)
    return Pair(args[0], args[1])


@_primitive("car")
def _builtin_car(args):
    _check_arity("car", args, 1, 1)
    return _check_pair("car", args[0]).car


@_primitive("cdr")
def _builtin_cdr(args):
    _check_arity("cdr", args, 1, 1)
    return _check_pair("cdr", args[0]).cdr


@_primitive("list")
def _builtin_list(args):
    return from_python_list(args)


@_primitive("length")
def _builtin_length(args):
    _check_arity("length", args, 1, 1)
    count = 0
    current = args[0]
    while isinstance(current, Pair):        # 迭代计数，避免深递归
        count += 1
        current = current.cdr
    if current is not NIL:
        raise SchemeError("length：参数必须是真列表，得到 %s" % to_display_string(args[0]))
    return count


@_primitive("append")
def _builtin_append(args):
    """(append '(1 2) '(3 4)) → (1 2 3 4)；最后一个参数可以是任意值。"""
    if not args:
        return NIL
    result = args[-1]
    for value in reversed(args[:-1]):
        result = from_python_list(_check_proper_list("append", value), tail=result)
    return result


@_primitive("null?")
def _builtin_null_p(args):
    _check_arity("null?", args, 1, 1)
    return args[0] is NIL


@_primitive("pair?")
def _builtin_pair_p(args):
    _check_arity("pair?", args, 1, 1)
    return isinstance(args[0], Pair)


@_primitive("list?")
def _builtin_list_p(args):
    """真列表：整条链以空表结尾。(list? (cons 1 2)) → #f"""
    _check_arity("list?", args, 1, 1)
    current = args[0]
    while isinstance(current, Pair):
        current = current.cdr
    return current is NIL


# ---------------------------------------------------------------------------
# 谓词
# ---------------------------------------------------------------------------

@_primitive("number?")
def _builtin_number_p(args):
    _check_arity("number?", args, 1, 1)
    return is_number(args[0])


@_primitive("boolean?")
def _builtin_boolean_p(args):
    _check_arity("boolean?", args, 1, 1)
    return isinstance(args[0], bool)


@_primitive("symbol?")
def _builtin_symbol_p(args):
    _check_arity("symbol?", args, 1, 1)
    return isinstance(args[0], Symbol)


@_primitive("string?")
def _builtin_string_p(args):
    _check_arity("string?", args, 1, 1)
    return isinstance(args[0], String)


@_primitive("procedure?")
def _builtin_procedure_p(args):
    _check_arity("procedure?", args, 1, 1)
    return isinstance(args[0], (Primitive, Closure))


@_primitive("zero?")
def _builtin_zero_p(args):
    _check_arity("zero?", args, 1, 1)
    return _check_number("zero?", args[0]) == 0


@_primitive("even?")
def _builtin_even_p(args):
    _check_arity("even?", args, 1, 1)
    return _check_integer("even?", args[0]) % 2 == 0


@_primitive("odd?")
def _builtin_odd_p(args):
    _check_arity("odd?", args, 1, 1)
    return _check_integer("odd?", args[0]) % 2 != 0


@_primitive("eq?")
def _builtin_eq_p(args):
    _check_arity("eq?", args, 2, 2)
    return _eq_values(args[0], args[1])


@_primitive("equal?")
def _builtin_equal_p(args):
    _check_arity("equal?", args, 2, 2)
    return _equal_values(args[0], args[1])


# ---------------------------------------------------------------------------
# 输出：结果是 None（无值），顶层不打印（spec §2）
# ---------------------------------------------------------------------------

@_primitive("display")
def _builtin_display(args):
    """打印一个值（字符串不带引号），不换行。"""
    _check_arity("display", args, 1, 1)
    print(to_display_string(args[0]), end="", flush=True)
    return None


@_primitive("newline")
def _builtin_newline(args):
    """输出一个换行。"""
    _check_arity("newline", args, 0, 0)
    print("", flush=True)
    return None


def make_global_environment():
    """创建初始环境：把 spec §5 的全部内置过程装进去。"""
    env = Environment()
    for name, func in _BUILTINS:
        env.define(Symbol(name), Primitive(name, func))
    return env
