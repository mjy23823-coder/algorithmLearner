class Solution:
    def trap(self, height: list[int]) -> int:
        left = 0
        right = len(height)-1
        left_max = 0
        right_max = 0
        water = 0
        while left<right:
            # 左挡板
            if height[left]>left_max:
                left_max= height[left]
            # 右挡板
            if height[right]>right_max:
                right_max = height[right]
            # 比较两边那边挡板低往哪边移动
            if height[left]<height[right]:
                # 查看本格能存储的水量
                water += left_max-height[left]
                left+=1
            else:
                water += right_max-height[right]
                right-=1

        return water