class Solution:
    def rightSideView(self, root):
        # 先说明变量含义，再完成你的实现
        ans=[]
        def dfs(node,depth):
            if node is None:
                return None
            # 如果这一层还没有节点，就记录当前节点
            if depth == len(ans):
                ans.append(node.val)

            dfs(node.right,depth+1)
            dfs(node.left,depth+1)
            
        dfs(root,0)

        return ans
