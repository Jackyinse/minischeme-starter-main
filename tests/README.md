# 自测说明

这里放的是**自查工具**，不属于交付的解释器（解释器全部在 `src/`）。

```bash
# 在仓库根目录执行；默认被测命令是 `python src/main.py`
python tests/run_tests.py
# 也可以指定别的解释器命令
python tests/run_tests.py "python src/main.py"
```

- `run_tests.py`：38 组用例，覆盖 spec 的每个特性与边界情况
  （可变参数算术、负数向零截断的除法、短路求值、`cond` 各形态、
  闭包与词法作用域、`let` 并行绑定、点对链、`eq?`/`equal?` 的类型陷阱、
  字符串转义、注释、多文件共享环境、深层递归等）。
  断言的是 **stdout 的逐行内容**，与评分器一样严格，能提前发现
  "多打一行 / 少打一行 / 浮点格式不对"这类问题。
- `data/shared_a.scm`、`data/shared_b.scm`：多文件共享全局环境的用例
  （`python src/main.py tests/data/shared_a.scm tests/data/shared_b.scm`）。

另外，官方评分器也可以直接跑：

```bash
python autograder.pyz python src/main.py            # 全部 12 组
python autograder.pyz python src/main.py --case=006 # 只跑一组
python src/main.py example/01_arithmetic.scm        # 单个示例
```
