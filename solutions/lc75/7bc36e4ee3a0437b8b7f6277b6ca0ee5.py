class Solution:
    def sortColors(self, nums: list[int]) -> None:
        """
        Do not return anything, modify nums in-place instead.
        """
        left = 0
        right = len(nums)-1
        
        for i in range(len(nums)):
            while i<=right:
                if nums[i]==0:
                    nums[left]=nums[i]
                 elif nums[i]==1:
                     continue
                 else:
                    nums[right]=nums[i]
                    right--

        


        
