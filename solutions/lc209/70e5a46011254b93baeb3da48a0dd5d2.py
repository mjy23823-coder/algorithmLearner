class Solution:
    def minSubArrayLen(self, target, nums):
        min_window_size = float("inf")
        sum=0
        left =0
        for right in range(0,len(nums)):
            sum+=nums[right]
            if sum == target:
                min_window_size=min(min_window_size,right-left+1)
            while sum>target:
                sum-=nums[left]
                left+=1
           
        return min_window_size

