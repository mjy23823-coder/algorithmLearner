class Solution:
    def fourSum(self, nums: list[int], target: int) -> list[list[int]]:

        nums.sort()
        result = []
        for i in range(len(nums) - 3):
            for j in range(i + 1, len(nums) - 2):
                if i > 0 and nums[i] == nums[i + 1]:
                    continue
                if j > i and nums[j] == nums[j + 1]:
                    continue
                left = i + j + 1
                right = len(nums) - 1

                while left < right:
                    total = nums[i] + nums[j] + nums[left] + nums[right]
                    if total < target:
                        left += 1
                    elif total > target:
                        right -= 1
                    else:
                        result.append([nums[i], nums[j], nums[left], nums[right]])

                        while left < right and nums[left] == nums[left + 1]:
                            left += 1

                        while left < right and nums[right] == nums[right - 1]:
                            right -= 1

                        left += 1
                        right -= 1

            return result
