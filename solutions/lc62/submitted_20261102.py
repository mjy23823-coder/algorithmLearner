class Solution:
    def uniquePaths(self, m: int, n: int) -> int:
        # 构建mxn的数组  dp[i]代表从左上角开始到i，j的路径数目
        dp = [[1] * n for _ in range(m)]
        # 推导出递推关系
        for i in range(1, m):
            for j in range(1, n):
                dp[i][j] = dp[i - 1][j] + dp[i][j - 1]

        return dp[-1][-1]
