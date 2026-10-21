# Definition for a binary tree node.
# class TreeNode:
#     def __init__(self, val=0, left=None, right=None):
#         self.val = val
#         self.left = left
#         self.right = right
class Solution:
    def sumOfLeftLeaves(self, root: Optional[TreeNode]) -> int:
        ans=0
        def dfs(node):
            nonlocal ans
            if node is None:
                return
            # 先左节点
            if node.left is not None:
                # 再叶子节点
                if node.left.left is None and node.left.right is None:
                    ans+=node.left.val  
            # 递归子树
            dfs(node.left)
            dfs(node.right)

        dfs(root)
        return ans
            