class Solution:
    def evalRPN(self, tokens: list[str]) -> int:
        # 初始化一个数字栈
        stack = []

        for token in tokens:
            # 如果是数字
            if token not in ["+", "-", "*", "/"]:
                stack.append(token)
                continue

            # 如果不是数字
            num1 = int(stack.pop())
            num2 = int(stack.pop())

            if token == "+":
                num = num2 + num1

            if token == "-":
                num = num2 - num1

            if token == "*":
                num = num2 * num1

            if token == "/":
                num = num2 / num1

            # 将计算结果重新入栈
            stack.append(num)

        return int(stack[-1])


if __name__ == "__main__":
    sol = Solution()
    cases = [
        (["2", "1", "+", "3", "*"], 9),
        (["4", "13", "5", "/", "+"], 6),
        (["10", "6", "9", "3", "+", "-11", "*", "/", "*", "17", "+", "5", "+"], 22),
        (["3", "-2", "/"], -1),
        (["-7", "3", "/"], -2),
    ]
    for tokens, expected in cases:
        actual = sol.evalRPN(tokens)
        print(tokens, actual, actual == expected)
