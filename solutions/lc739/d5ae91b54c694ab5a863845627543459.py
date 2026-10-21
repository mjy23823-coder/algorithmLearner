class Solution:
    def dailyTemperatures(self, temperatures):
        # 先说明变量含义，再完成你的实现
                # 初始化和数组等长的0数组
        ans = [0]*len(temperatures)
        # 初始化栈
        stack =[]

        for i,temperature in enumerate(temperatures):
            # 当栈非空且当前数比栈顶元素大
            while stack and temperature>temperatures[stack[-1]]:
                # 移除栈顶的元素并记录
                prev=stack.pop()
                # 保存答案
                ans[prev]=i-prev
            # 栈存入元素的下标
            stack.append(i)


        return ans
