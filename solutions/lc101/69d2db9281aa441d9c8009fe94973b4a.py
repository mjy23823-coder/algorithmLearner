
class Solution:
    def isSymmetric(self, root: TreeNode | None) -> bool:
        # 空树
        if root is None:
            return True

        def mirror(left,right):
            # 两边节点都为空
            if left is None and right is None:
                return True
            # 两边有一边为空
            if left is None and right is not None:
                return False
            
            if left is not None and right is None:
                return False
            
            # 两边都不为空
            if left is not None and right is not None:
                if left.val != right.val:
                    return False
                # 继续递归子树
                return mirror(left.left,right.right) and mirror(right.left,left.right)
            
            return True

        return mirror(root.left,root.right)