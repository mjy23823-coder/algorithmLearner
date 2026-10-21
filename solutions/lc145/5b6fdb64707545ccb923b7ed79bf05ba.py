class Solution:
    def postorderTraversal(self, root):
        # 先说明变量含义，再完成你的实现
        ans=[]
        def dfs(node):
            if node is None:
                return 
            
            dfs(node.left)
            dfs(node.right)
            ans.append(node.val)

        dfs(root)
        return ans
