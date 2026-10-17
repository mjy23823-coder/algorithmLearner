class Solution:
    def maxArea(self, height):
        left = 0
        right = len(height)-1
        max_area = 0
        while left=<right:
            max_area = max(max_area,min(nums[left],nums[right])*right-left)
            if nums[left]<nums[right]:
                left+=1
            if nums[left]>nums[right]
                right-=1
        return max_area  
    