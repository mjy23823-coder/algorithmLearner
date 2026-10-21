class Solution:
    def buildTree(self, preorder: List[int], inorder: List[int]) -> Optional[TreeNode]:
        # 空节点
        if not preorder:  
            return None
        # 左子树的大小(找出根节点的索引)
        left_size = inorder.index(preorder[0])  
        # 
        left = self.buildTree(preorder[1: 1 + left_size], inorder[:left_size])
        right = self.buildTree(preorder[1 + left_size:], inorder[1 + left_size:])
        
        return TreeNode(preorder[0], left, right)