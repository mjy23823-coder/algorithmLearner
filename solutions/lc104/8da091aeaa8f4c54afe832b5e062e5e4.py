class Solution:
    def maxDepth(self, root):
        # 先说明变量含义，再完成你的实现
        def dfs(node):
            if node is None:
                return 0
            
            left_height = dfs(node.left)
            right_height = dfs(node.right)

            return max(left_height,right_height)+1

        return dfs(root)
