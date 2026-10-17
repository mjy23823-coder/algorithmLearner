---
name: algo-check
description: 用户提交算法题代码、贴出题解、问"我这样写对吗""帮我看看代码"时使用。实际运行测试，检查正确性、复杂度、边界和 Python 写法，并记录结果。
---

# 代码检查

1. **确认题目**：题号不明确时先问。
2. **保存并运行**：把用户代码原样写入 `solutions/lc<题号>.py`（已存在就覆盖为最新一次提交），
   在文件末尾加验证用例，然后运行 `python solutions/lc<题号>.py`：

```python
import sys; sys.path.insert(0, "tools")
from lc_helpers import *   # ListNode / TreeNode / build_list / build_tree / check 等

# ↓ 用户代码原样粘贴（class Solution: ...）

if __name__ == "__main__":
    s = Solution()
    check("示例1", s.method(...), expected)
    check("空输入", ...)
    # 再加 2~4 个边界用例：单元素、全相同、重复值、负数、极端长度等
```

   期望值要自己推算清楚，不确定时另写一个暴力解对拍。只修改测试部分，不要改用户的代码。

3. **按固定格式反馈**（以运行结果为依据，FAIL 的用例要写出输入、实际输出和期望输出）：

```text
整体评价：
正确性：
主要问题：
复杂度：
最小修改建议：
复盘问题：
```

   - 优先给最小修改，指出具体是哪一行、为什么错；用户还没尝试修改前，不要直接给完整正确代码。
   - 用户已经尝试过、仍然卡住时，可以给修正版，并标出关键改动。
   - "复盘问题"要求用户用一句话总结模板或规律，或解释一个边界情况。

4. **记录**：这道题确认完成（全部通过，或今天确定放弃）后，立即运行
   `python tools/coach.py done <题号> --result <independent|hinted|failed> --note "<一句话错因>"`；
   新题要加 `--title` 和 `--topic`。判定标准见 CLAUDE.md。把脚本给出的下次复习日期告诉用户。
