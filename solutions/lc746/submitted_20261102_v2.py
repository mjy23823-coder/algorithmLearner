class Solution:
    def minCostClimbingStairs(self, cost: list[int]) -> int:
        dp = [float("inf")] * (len(cost) + 1)

        dp[0] = 0
        dp[1] = cost[0]

        for i in range(2, len(cost) + 1):
            # dp[i]代表包括本级的前i级的最小花费数
            dp[i] = min(dp[i - 1], dp[i - 2]) + cost[i - 1]

        return min(dp[-1], dp[-2])
