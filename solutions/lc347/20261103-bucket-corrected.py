class Solution:
    def topKFrequent(self, nums: list[int], k: int) -> list[int]:
        result = []
        # 记录 nums 每个数出现的次数
        count = {}
        for num in nums:
            count[num] = count.get(num, 0) + 1

        # 初始化桶
        buckets = [[] for _ in range(len(nums) + 1)]
        # 下标表示出现次数，桶内保存数字列表
        for num, freq in count.items():
            buckets[freq].append(num)

        # 从右往左遍历桶
        for freq in range(len(nums), 0, -1):
            for num in buckets[freq]:
                result.append(num)
                if len(result) == k:
                    return result
