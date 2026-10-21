class Solution:
    def findMode(self, root: TreeNode) -> list[int]:
        result = []
        prev = None
        count = 0
        maxCount = 0

        def dfs(node):
            nonlocal prev,count,maxCount,result
            if node is None:
                return None

            dfs(node.left)

            cur = node.val

            # 前后指针一致
            if prev == cur:
                count+=1
            else:
                # 不一致时更新prev，count置为0
                prev = cur
                count = 0

            if count>maxCount:
                maxCount = count
                result = [cur]
            elif count == maxCount:
                result.append(cur)
            
            dfs(node.right)
        
        dfs(root)

        return result