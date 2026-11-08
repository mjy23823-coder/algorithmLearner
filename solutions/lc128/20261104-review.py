class Solution:
    def longestConsecutive(self, nums: list[int]) -> int:
        sort_num = set(nums)
        count = 1
        max_count = 0
        for num in nums:
            if num - 1 not in sort_num:
                current = num
                count = 1
                while current + 1 in sort_num:
                    count += 1
                    current += 1
                max_count = max(max_count, count)
        return max_count
