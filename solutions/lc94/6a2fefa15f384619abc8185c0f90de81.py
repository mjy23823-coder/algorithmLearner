class Solution:
    def inorderTraversal(self, root: TreeNode) -> list[int]:
        ans=[]
        def dfs(node):
            if node is None:
                return 
            
            dfs(node.left)
            ans.append(node.val)
            dfs(node.right)

        dfs(root)
        return ans
