class Solution:
    def longestConsecutive(self, nums: list[int]) -> int:
        sort_num = set(nums)
        count = 1
        max_count = 0
        for num in sort_num:
            cur = num
            while cur + 1 in sort_num:
                count += 1
        return max_count
