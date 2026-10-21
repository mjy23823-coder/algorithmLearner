class Solution:
    def longestConsecutive(self, nums: list[int]) -> int:
        if not nums:
            return 0 
        # 用一个集合存储所有元素
        nums_set = set()
        max_count = 0
        for num in nums:
            if num not in nums_set:
                nums_set.add(num)
        
        for num in nums_set:
            # 如果当前元素的上一个元素不在集合中
            if num-1 not in nums_set:
                # 当前元素是起点
                current = num
                count = 1
                # 如果当前元素的下一元素在集合
                while current+1 in nums_set:
                    current+=1
                    count+=1
                max_count=max(max_count,count)


        return max_count
        
