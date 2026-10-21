class Solution:
    def invertTree(self, root: Optional[TreeNode]) -> Optional[TreeNode]:
        # 当前节点为空
        if root == None:
            return None
        # 递归左右子树
        self.invertTree(root.left)
        self.invertTree(root.right)
        # 交换左右子树节点
        root.left,root.right = root.right,root.left

        return root