class Solution:
    def maxSubArray(self, nums: list[int]) -> int:
        ans = float("-inf")
        cur = 0
        for num in nums:
            cur += num
            if cur < 0:
                cur = 0
            ans = max(ans, cur)
        return ans
