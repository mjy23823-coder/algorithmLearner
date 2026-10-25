class Solution:
    def evalRPN(self, tokens):
        # 先说明变量含义，再完成你的实现
        stack=[]        
        for token in tokens:
            # 如果是数字
            if token not in ["+","-","*","/"]:
                stack.append(int(token))
                continue
            # 碰到符号弹出两个数字
            num1 = stack.pop()
            num2 = stack.pop()

            # 进行表达式运算
            if token == "+":
                result = num2 + num1
            elif token == "-":
                result = num2 - num1
            elif token == "*":
                result = num2 * num1
            else:
                result = int(num2 / num1)  # 向 0 截断
            # 将结果重新压入栈中
            stack.append(result)
        
        return stack[-1]
