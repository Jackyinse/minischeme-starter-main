"""流水线第 5 步：求值器（表达式 -> 值），整个解释器的心脏。

两个互相递归的函数（README §4）：

    evaluate(expr, env)  —— 求值一个表达式
        符号          → 去环境查值
        数字/布尔/字符串 → 原样返回
        括号表达式     → 特殊形式按各自的规则处理（spec §4）；
                        其余是函数调用：先求值操作符和全部实参，再交给 apply
    apply(proc, args)    —— 调用一个过程
        内置过程 → 直接调用
        闭包     → 新建一层环境把实参绑到形参上（外层指向函数**定义时**的环境），
                   再回到 evaluate 求值函数体

本模块只做求值，不负责打印、不负责读文件；特殊形式与函数调用在这里分流。
"""

from errors import SchemeError
from printer import to_display_string
from values import (
    Closure,
    Pair,
    Primitive,
    Symbol,
    is_true,
    to_python_list,
)

# 特殊形式的名字集合（spec §4）。它们长得像函数调用，但求值规则不同，
# 因此**不会**先求值参数，而是各自决定先算什么。
_SPECIAL_FORMS = (
    "quote", "if", "cond", "and", "or", "define", "lambda", "let", "begin",
)


class Evaluator:
    """mini-Scheme 求值器。全局环境里已经装好 spec §5 的内置过程。"""

    def __init__(self, global_env):
        self.global_env = global_env

    # ----- 对外入口 -------------------------------------------------------

    def evaluate(self, expr, env=None):
        """求值一个表达式并返回它的值。"""
        if env is None:
            env = self.global_env

        # 自求值的基本值：数字、布尔、字符串、空表
        if isinstance(expr, Symbol):
            return env.lookup(expr)
        if isinstance(expr, Pair):
            return self._evaluate_pair(expr, env)
        return expr

    # ----- 括号表达式：特殊形式 vs 函数调用 -------------------------------

    def _evaluate_pair(self, expression, env):
        operator = expression.car
        operands = expression.cdr

        if isinstance(operator, Symbol) and operator.name in _SPECIAL_FORMS:
            handler = getattr(self, "_special_" + operator.name)
            return handler(operands, env)

        # 普通函数调用：先求值操作符，再从左到右求值全部实参（应用序求值）。
        procedure = self.evaluate(operator, env)
        arguments = [self.evaluate(argument, env) for argument in _expression_list(operands)]
        return self.apply(procedure, arguments)

    # ----- 特殊形式（spec §4） -------------------------------------------

    def _special_quote(self, operands, env):
        """(quote 数据)：原样返回，不求值。"""
        args = _expression_list(operands)
        _require_arity("quote", args, 1, 1)
        return args[0]

    def _special_if(self, operands, env):
        """(if 测试 真分支 假分支?)：先求测试，只走一个分支；省略假分支时返回 None。"""
        args = _expression_list(operands)
        _require_arity("if", args, 2, 3)
        if is_true(self.evaluate(args[0], env)):
            return self.evaluate(args[1], env)
        if len(args) == 3:
            return self.evaluate(args[2], env)
        return None

    def _special_cond(self, operands, env):
        """(cond (测试 表达式...) ... (else 表达式...))：逐个测试，取第一个成立的子句。"""
        clauses = _expression_list(operands)
        for clause in clauses:
            parts = _expression_list(clause)
            if not parts:
                raise SchemeError("cond：子句不能为空，应为 (测试 表达式...)")
            test = parts[0]
            if isinstance(test, Symbol) and test.name == "else" and not env.is_bound(test):
                return self._evaluate_sequence(parts[1:], env)   # 兜底子句
            value = self.evaluate(test, env)
            if is_true(value):
                if len(parts) == 1:
                    return value          # 子句里没有表达式时，返回测试值本身
                return self._evaluate_sequence(parts[1:], env)
        return None                       # 全部不匹配

    def _special_and(self, operands, env):
        """(and e1 e2 ...)：遇到 #f 立刻返回 #f（短路）；全真返回最后一个值。"""
        args = _expression_list(operands)
        result = True
        for expression in args:
            result = self.evaluate(expression, env)
            if not is_true(result):
                return False              # 后面的表达式不再求值
        return result                     # (and) → #t

    def _special_or(self, operands, env):
        """(or e1 e2 ...)：遇到第一个非 #f 就返回它（短路）；全假返回 #f。"""
        args = _expression_list(operands)
        for expression in args:
            result = self.evaluate(expression, env)
            if is_true(result):
                return result             # 后面的表达式不再求值
        return False                      # (or) → #f

    def _special_define(self, operands, env):
        """(define 名 表达式) 或 (define (函数名 参数...) 体...)。

        求值顺序：**先求值右侧**，再在当前环境绑定；结果是符号名。
        """
        args = _expression_list(operands)
        if len(args) < 2:
            raise SchemeError("define：应为 (define 名 表达式) 或 (define (名 参数...) 体...)")
        target = args[0]

        if isinstance(target, Symbol):        # 定义普通变量
            value = self.evaluate(args[1], env)
            env.define(target, value)
            return target

        signature = _expression_list(target)  # 定义函数的简写
        if not signature:
            raise SchemeError("define：函数名不能为空")
        name = signature[0]
        if not isinstance(name, Symbol):
            raise SchemeError("define：函数名必须是符号，得到 %s" % to_display_string(name))
        procedure = Closure(_parameter_names("define", signature[1:]), args[1:], env, name.name)
        env.define(name, procedure)
        return name

    def _special_lambda(self, operands, env):
        """(lambda (参数...) 体...)：此时**不**求值函数体，只捕获定义处的环境。"""
        args = _expression_list(operands)
        if len(args) < 2:
            raise SchemeError("lambda：应为 (lambda (参数...) 体...)")
        params = _parameter_names("lambda", _expression_list(args[0]))
        return Closure(params, args[1:], env)

    def _special_let(self, operands, env):
        """(let ((名 表达式)...) 体...)：绑定表达式在**外层环境**求值（并行绑定）。"""
        args = _expression_list(operands)
        if len(args) < 2:
            raise SchemeError("let：应为 (let ((名 表达式)...) 体...)")

        bindings = _expression_list(args[0])
        names = []
        values = []
        for binding in bindings:
            parts = _expression_list(binding)
            if len(parts) != 2:
                raise SchemeError("let：每个绑定应为 (名 表达式)")
            name = parts[0]
            if not isinstance(name, Symbol):
                raise SchemeError("let：绑定的名字必须是符号，得到 %s" % to_display_string(name))
            names.append(name)
            values.append(self.evaluate(parts[1], env))   # 注意：在外层环境求值

        local_env = env.child()
        for bound_name, value in zip(names, values):
            local_env.define(bound_name, value)
        return self._evaluate_sequence(args[1:], local_env)

    def _special_begin(self, operands, env):
        """(begin e1 e2 ...)：从左到右依次求值，返回最后一个的结果；空 begin 无值。"""
        return self._evaluate_sequence(_expression_list(operands), env)

    # ----- apply：调用一个过程 -------------------------------------------

    def apply(self, procedure, arguments):
        """调用过程：内置过程直接调用；闭包则新建作用域并求值函数体。"""
        if isinstance(procedure, Primitive):
            return procedure.func(arguments)

        if isinstance(procedure, Closure):
            if len(arguments) != len(procedure.params):
                raise SchemeError("%s：需要 %d 个参数，收到 %d 个"
                                  % (_closure_name(procedure),
                                     len(procedure.params), len(arguments)))
            # 外层指向函数**定义时**的环境——词法作用域与闭包的关键。
            call_env = procedure.env.child()
            for parameter, value in zip(procedure.params, arguments):
                call_env.define(parameter, value)
            return self._evaluate_sequence(procedure.body, call_env)

        raise SchemeError("%s 不是过程，无法调用" % to_display_string(procedure))

    # ----- 内部工具 -------------------------------------------------------

    def _evaluate_sequence(self, expressions, env):
        """按 begin 语义依次求值，返回最后一个的结果（函数体也用它）。"""
        result = None
        for expression in expressions:
            result = self.evaluate(expression, env)
        return result


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _expression_list(value):
    """把点对链拆成 Python 列表。

    求值器内部之所以要先拆成列表，是因为要用 len()/索引判断参数个数，
    以及做 and/or 的短路——这比一层层 cdr 清楚得多。
    遇到非真列表（如 `(1 . 2)`）会报错。
    """
    items = to_python_list(value)
    if items is None:
        raise SchemeError("表达式不是合法的列表（可能是多余的点号）：%s"
                          % to_display_string(value))
    return items


def _require_arity(name, args, minimum, maximum=None):
    """检查特殊形式的参数个数（maximum=None 表示不设上限）。"""
    if len(args) < minimum or (maximum is not None and len(args) > maximum):
        if maximum is None:
            expected = "至少 %d 个" % minimum
        elif minimum == maximum:
            expected = "%d 个" % minimum
        else:
            expected = "%d 到 %d 个" % (minimum, maximum)
        raise SchemeError("%s：需要%s参数，收到 %d 个" % (name, expected, len(args)))


def _parameter_names(form, params):
    """校验并返回形参名列表。

    形参必须是符号且不重复；本语言不支持可变参数 lambda（spec §10），
    所以 `(lambda (x . y) ...)` 这种点对写法会被明确拒绝，而不是悄悄算错。
    """
    names = []
    seen = set()
    for param in params:
        if not isinstance(param, Symbol):
            raise SchemeError("%s：形参必须是符号，得到 %s" % (form, to_display_string(param)))
        if param.name in seen:
            raise SchemeError("%s：形参 %s 重复" % (form, param.name))
        seen.add(param.name)
        names.append(param)
    return names


def _closure_name(procedure):
    """闭包在错误信息里的显示名（具名函数用函数名，匿名 lambda 用 #<lambda>）。"""
    return procedure.name or "#<lambda>"
