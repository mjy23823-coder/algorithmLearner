---
name: algo-mock
description: 限时训练、模拟面试、"来一场 mock"时使用。按大厂面试官的方式出题并计时，结束后从题型识别、沟通、代码、复杂度、用时五个维度评分。
---

# 限时模拟面试

1. **选题**：运行 `python tools/coach.py status`，从已学专题中选 1 道用户没做过的高频 Medium
   （时间充足可以出 2 道：1 Easy + 1 Medium）。不要选今天刚做过的题。
   默认限时：Easy 15 分钟，Medium 25 分钟。
2. **开始计时**：运行 `python -c "from datetime import datetime; print(datetime.now().isoformat(timespec='seconds'))"` 记下开始时间，然后以面试官口吻给出题目描述和示例
   （不说题号、不说题型）。
3. **面试过程**：
   - 先请用户复述题意并说出思路和复杂度，再写代码；
   - 只做真实面试官会做的引导（"这个解法的复杂度是多少？""有没有更优的方法？""空数组怎么办？"），
     不给解题提示；用户明确求助时可以给一次方向性提示，评分时记为"需要提示"；
   - 用户提交后，追问 1 个边界情况和 1 个可能的 follow-up。
4. **结束计时**：再次运行上述 Python 时间命令，计算实际用时。按 algo-check 的方式保存到 `solutions/` 并运行测试。
5. **评分**（每项 1~5 分，并各写一句理由）：

```text
模拟面试复盘｜LCxx 题名｜用时 xx/xx 分钟
题型识别：
沟通表达：
代码正确性：
复杂度分析：
时间控制：
最该改进的一点：
```

6. **记录**：`python tools/coach.py done <题号> --result <...> --title <...> --topic <...> --mock --minutes <用时> --limit <限时> --scores <题型,沟通,代码,复杂度,用时> --note "<最该改进的一点>"`，
   例如 `--scores 4,3,4,4,5`。五维评分会进入面板的“能力周报”。选题可参考 `python tools/coach.py today --json` 的 `mock_candidates`
   （已学专题里没做过、本地有用例的题）；用户也可以在面板“模拟面试”页自己计时完成。
