class Solution:
    def trap(self, height: list[int]) -> int:
        left = 0
        right = len(height)-1
        left_max = 0
        right_max = 0
        water = 0

        while left<right:
            # 当前高度如果比最高的边界大，更新最高边界
            if height[left]>=left_max:
                left_max = height[left]
            else:
                water=water+left_max-height[left]

            if height[right]>=right_max:
                right_max = height[right]
            else:
                water=water+right_max-height[right]

            if left_max<right_max:
                left+=1
            else:
                right-=1

        return water