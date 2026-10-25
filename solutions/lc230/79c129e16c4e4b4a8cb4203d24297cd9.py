class Solution:
    def kthSmallest(self, root, k):
        # 先说明变量含义，再完成你的实现
               
        ans=-1
        def dfs(node):
            nonlocal k,ans
            if node is None:
                return None

            dfs(node.left)
            k-=1
            if k == 0:
                ans = node.val
            dfs(node.right)

        dfs(root)
