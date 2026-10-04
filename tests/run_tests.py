"""解释器自测。

用法（在仓库根目录执行）：

    python tests/run_tests.py                 # 用默认的 `python src/main.py`
    python tests/run_tests.py "python src/main.py"   # 指定被测解释器命令

用例覆盖 spec 的每个特性（含边界情况），断言的是 **stdout 的逐行内容**——
和评分器一样严格比对，因此能提前发现"多打一行/少打一行"这类问题。

这些用例是自查工具，不属于交付的解释器本身，故放在 tests/ 而不是 src/。
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(program, interpreter, *files):
    """调用解释器跑一段程序（无文件时走标准输入），返回 (退出码, 输出, 错误)。"""
    command = [sys.executable, interpreter] + list(files)
    completed = subprocess.run(command, input=program, capture_output=True,
                               text=True, encoding="utf-8", timeout=30)
    return completed.returncode, completed.stdout, completed.stderr


# 每个用例：名字 -> (程序文本, 期望输出行列表)
CASES = {
    # ----- 算术（spec §5）-------------------------------------------------
    "加法的各种参数个数": (
        "(+)\n(+ 5)\n(+ 1 2 3)\n(+ 1 2 3 4 5)", ["0", "5", "6", "15"]),
    "减法的单参数与多参数": (
        "(- 5)\n(- 10 4 1)\n(- 1 2 3)", ["-5", "5", "-4"]),
    "乘法的各种参数个数": (
        "(*)\n(* 5)\n(* 2 3 4)", ["1", "5", "24"]),
    "整数除法向零截断": (
        "(/ 7 2)\n(/ -7 2)\n(/ 7 -2)\n(/ -7 -2)\n(/ 1 2)\n(/ 100 5 2)",
        ["3", "-3", "-3", "3", "0", "10"]),
    "单参数除法得浮点": (
        "(/ 2)\n(/ 4)", ["0.5", "0.25"]),
    "expt 与 abs": (
        "(expt 2 10)\n(expt 2 0)\n(expt 0 5)\n(abs (- 5 9))\n(abs 7)",
        ["1024", "1", "0", "4", "7"]),
    "modulo 与 quotient": (
        "(modulo 17 5)\n(quotient 17 5)\n(quotient -7 2)\n(modulo -7 2)\n(quotient 7 -2)",
        ["2", "3", "-3", "1", "-3"]),
    "浮点参与运算保持浮点": (
        "(+ 1.5 2)\n(* 2 2.5)\n(/ 7.0 2)\n(/ 7 2.0)",
        ["3.5", "5.0", "3.5", "3.5"]),

    # ----- 比较（链式）----------------------------------------------------
    "链式比较": (
        "(< 2 3 4)\n(< 2 4 3)\n(> 5 5)\n(<= 1 1 2)\n(>= 3 3 2)\n(= 2 2 2)\n(= 1 2)",
        ["#t", "#f", "#f", "#t", "#t", "#t", "#f"]),
    "比较符号": (
        "(< 'a 'b)\n(= 'x 'x)\n(> 'c 'b)", ["#t", "#t", "#t"]),

    # ----- 布尔与短路 -----------------------------------------------------
    "and/or 的短路": (
        "(and #f (/ 1 0))\n(or #t (/ 1 0))\n(and)\n(or)\n(and 1 2 3)\n(or #f #f 7)",
        ["#f", "#t", "#t", "#f", "3", "7"]),
    "只有 #f 是假": (
        "(if 0 '真 '假)\n(if '() '真 '假)\n(if \"\" '真 '假)\n(not 0)\n(not #f)\n(not '())",
        ["真", "真", "真", "#f", "#t", "#f"]),

    # ----- 控制流 ---------------------------------------------------------
    "if 的真假分支与省略假分支": (
        "(if (> 3 2) 'yes 'no)\n(if #f 'yes 'no)\n(if #f 1)",
        ["yes", "no"]),
    "cond 的各种子句": (
        "(cond ((= 1 2) 'a) ((= 2 2) 'b) (else 'c))\n"
        "(cond (else 'd))\n"
        "(cond ((> 2 3)) (else 42))\n"
        "(cond (#f 1))\n"
        "(cond ((= 1 1) 1 2 3))",
        ["b", "d", "42", "3"]),

    # ----- define / lambda / 闭包 ----------------------------------------
    "define 的结果是符号名": (
        "(define pi 3)\n(+ pi 1)\n(define (square x) (* x x))\n(square 7)",
        ["pi", "4", "square", "49"]),
    "lambda 直接调用与闭包": (
        "((lambda (x) (* x 2)) 5)\n"
        "(define (make-adder n) (lambda (x) (+ x n)))\n"
        "((make-adder 100) 7)\n"
        "(define add5 (make-adder 5))\n(add5 10)",
        ["10", "make-adder", "107", "add5", "15"]),
    "闭包各自记住自己的环境": (
        "(define (make-counter-like n) (lambda () n))\n"
        "(define a (make-counter-like 1))\n"
        "(define b (make-counter-like 2))\n"
        "(a)\n(b)",
        ["make-counter-like", "a", "b", "1", "2"]),
    "递归": (
        "(define (fact n) (if (= n 0) 1 (* n (fact (- n 1)))))\n(fact 10)\n"
        "(define (fib n) (if (< n 2) n (+ (fib (- n 1)) (fib (- n 2)))))\n(fib 15)",
        ["fact", "3628800", "fib", "610"]),

    # ----- let / begin ----------------------------------------------------
    "let 是并行绑定": (
        "(let ((x 3) (y 4)) (+ x y))\n"
        "(let ((a 1)) (let ((b (+ a 1))) (* a b)))\n"
        "(define g 10)\n(let ((g 1) (h g)) h)",
        ["7", "2", "g", "10"]),
    "let 体内的 define 不影响外层": (
        "(let ((x 1)) (begin (define y 2) (+ x y)))\n(define y 5)\ny",
        ["3", "y", "5"]),
    "begin 顺序执行": (
        "(begin (define z 1) (+ z 41))\n(begin 1 2 3)", ["42", "3"]),

    # ----- 列表（点对链）-------------------------------------------------
    "点对与列表打印": (
        "(cons 1 2)\n(list 1 2 3)\n(cons 1 '(2 3))\n(cons 1 (cons 2 '()))\n'()\n"
        "(cons '(1 2) '(3))",
        ["(1 . 2)", "(1 2 3)", "(1 2 3)", "(1 2)", "()", "((1 2) 3)"]),
    "car/cdr 与嵌套": (
        "(car '(1 2 3))\n(cdr '(1 2 3))\n(car (cdr '(1 2 3)))\n(cdr '(1))\n(car '((1 2) 3))",
        ["1", "(2 3)", "2", "()", "(1 2)"]),
    "length/append": (
        "(length '())\n(length '(a b c d))\n(append '(1 2) '(3 4))\n(append)\n"
        "(append '(1) '(2) '(3) '(4))\n(append '() '(1))",
        ["0", "4", "(1 2 3 4)", "()", "(1 2 3 4)", "(1)"]),
    "list 谓词": (
        "(null? '())\n(null? '(1))\n(pair? '(1 2))\n(pair? '())\n"
        "(list? '(1 2))\n(list? (cons 1 2))\n(list? '())",
        ["#t", "#f", "#t", "#f", "#t", "#f", "#t"]),
    "用语言本身定义 map 与 filter": (
        "(define (map f xs) (if (null? xs) '() (cons (f (car xs)) (map f (cdr xs)))))\n"
        "(define (filter p xs)\n"
        "  (cond ((null? xs) '())\n"
        "        ((p (car xs)) (cons (car xs) (filter p (cdr xs))))\n"
        "        (else (filter p (cdr xs)))))\n"
        "(map (lambda (x) (* x x)) '(1 2 3 4))\n"
        "(filter odd? '(1 2 3 4 5))",
        ["map", "filter", "(1 4 9 16)", "(1 3 5)"]),

    # ----- 谓词与相等性 ---------------------------------------------------
    "类型谓词": (
        "(number? 5)\n(number? 'x)\n(boolean? #t)\n(boolean? 0)\n(symbol? 'x)\n"
        "(symbol? \"x\")\n(string? \"s\")\n(string? 's)\n(procedure? car)\n"
        "(procedure? 1)\n(procedure? (lambda (x) x))",
        ["#t", "#f", "#t", "#f", "#t", "#f", "#t", "#f", "#t", "#f", "#t"]),
    "数值谓词": (
        "(zero? 0)\n(zero? 1)\n(even? 8)\n(even? 7)\n(odd? 7)\n(odd? 0)",
        ["#t", "#f", "#t", "#f", "#t", "#f"]),
    "eq? 与 equal? 的区别": (
        "(eq? '() '())\n(eq? '(1) '(1))\n(equal? '(1 2 3) (list 1 2 3))\n"
        "(eq? 'a 'a)\n(eq? 1 1)\n(eq? #t 1)\n(eq? 'a \"a\")\n(eq? \"a\" \"a\")\n"
        "(equal? (cons 1 2) (cons 1 2))\n(equal? '(1 (2 3)) (list 1 (list 2 3)))\n"
        "(equal? 1 1.0)",
        ["#t", "#f", "#t", "#t", "#t", "#f", "#f", "#t", "#t", "#t", "#f"]),
    "字符串相等性": (
        "(equal? \"abc\" \"abc\")\n(equal? \"abc\" \"abd\")", ["#t", "#f"]),

    # ----- 输出与字符串 ---------------------------------------------------
    "display 与 newline": (
        "(display (+ 1 2))\n(newline)\n(display \"hello\")\n(newline)\n"
        "(display 'sym)\n(newline)\n(display '(1 2))\n(newline)",
        ["3", "hello", "sym", "(1 2)"]),
    "字符串的打印与转义": (
        "\"hello\"\n\"a\\nb\"\n\"tab\\there\"\n\"quote\\\"inside\"\n"
        "(display \"a\\nb\")\n(newline)\n(string? \"x\")",
        ["\"hello\"", "\"a\\nb\"", "\"tab\\there\"", "\"quote\\\"inside\"",
         "a", "b", "#t"]),

    # ----- quote ----------------------------------------------------------
    "quote 的形式": (
        "'x\n'(1 2 3)\n'()\n(quote (1 (2 3)))\n''x\n'(a (b c) \"d\")",
        ["x", "(1 2 3)", "()", "(1 (2 3))", "(quote x)", "(a (b c) \"d\")"]),

    # ----- 词法 -----------------------------------------------------------
    "注释与多行表达式": (
        "; 整行注释\n(+ 1 2) ; 行尾注释\n(+\n  1\n  2)\n; 末尾注释",
        ["3", "3"]),
    "大小写敏感": (
        "(define foo 1)\n(define FOO 2)\n(+ foo FOO)", ["foo", "FOO", "3"]),
    "负数字面量与负号": (
        "-7\n(- 0 7)\n(+ -1 -2)\n-1.5", ["-7", "-7", "-3", "-1.5"]),

    # ----- 综合：典型程序 ------------------------------------------------
    "累加与列表构造": (
        "(define (range n) (if (= n 0) '() (append (range (- n 1)) (list n))))\n"
        "(range 5)\n"
        "(define (sum xs) (if (null? xs) 0 (+ (car xs) (sum (cdr xs)))))\n"
        "(sum (range 10))",
        ["range", "(1 2 3 4 5)", "sum", "55"]),
    "深层递归不爆栈": (
        "(define (count n) (if (= n 0) 0 (+ 1 (count (- n 1)))))\n(count 1500)",
        ["count", "1500"]),
}


def main():
    interpreter = sys.argv[1] if len(sys.argv) > 1 else os.path.join("src", "main.py")
    interpreter_path = interpreter if os.path.isabs(interpreter) else os.path.join(ROOT, interpreter)
    if not os.path.exists(interpreter_path):
        print("找不到解释器：%s" % interpreter_path)
        return 2

    passed = 0
    failures = []
    for name, (program, expected) in CASES.items():
        try:
            code, out, err = run(program, interpreter_path)
        except subprocess.TimeoutExpired:
            failures.append((name, "超时（>30s）", expected, []))
            continue
        got = out.splitlines()
        if code == 0 and got == expected:
            passed += 1
            print("  ok   %s" % name)
        else:
            reason = "退出码 %d" % code if code != 0 else "输出不符"
            failures.append((name, reason + (("  stderr: " + err.strip()) if err.strip() else ""),
                             expected, got))
            print("  FAIL %s" % name)

    if failures:
        print("\n---- 失败详情 ----")
        for name, reason, expected, got in failures:
            print("\n[%s] %s" % (name, reason))
            print("  期望：%s" % expected)
            print("  实际：%s" % got)

    print("\n%d passed, %d failed" % (passed, len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
