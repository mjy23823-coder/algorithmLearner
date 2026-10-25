class Solution:
    def subarraySum(self, nums, k):
        # 先说明变量含义，再完成你的实现
        prev = {0:1}
        ans = 0
        total = 0

        for num in nums:
            total += num
            need = total-k
            ans += prev.get(need,0)
        
            prev[total] = prev.get(total,0)+1

        return ans
