class Solution:
    def mergeTrees(self, root1, root2):
        # 先说明变量含义，再完成你的实现
                
        def dfs(p,q):
            if p is None and q is None:
                return None
            if p is None and q is not None:
                return q    
            if p and q is None:
                return p
            if p and q:
                p.val+=q.val
                p.left = dfs(p.left,q.left)
                p.right = dfs(p.right,q.right)
                return p


        return dfs(root1,root2)
