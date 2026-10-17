class Solution:
    def sortColors(self, nums: list[int]) -> None:
        """
        Do not return anything, modify nums in-place instead.
        """
        left = 0
        right = len(nums)-1

        while left<right:
            if nums[left]>nums[right]:
                nums[left],nums[right]=nums[right],nums[left]
                right-=1
            else:
                left+=1

        
