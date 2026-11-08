class Solution:
    def topKFrequent(self, nums: list[int], k: int) -> list[int]:
        result = []
        count = {}
        for num in nums:
            count[num] = count.get(num, 0) + 1

        buckets = [[] for _ in range(len(nums) + 1)]
        for freq, num in count.items():
            buckets[freq] = num

        for freq in range(len(nums), 0, -1):
            for num in buckets[freq]:
                result.append(num)
                if len(result) == k:
                    return result
