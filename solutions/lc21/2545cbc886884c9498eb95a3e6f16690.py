class Solution:
    def mergeTwoLists(self, list1, list2):
        # 先说明变量含义，再完成你的实现
              # 虚拟头节点
        dummy = ListNode(0)
        cur = dummy

        # 遍历两个链表
        while list1 and list2:
            # 谁小让谁连接上
            if list1.val<=list2.val:
                cur.next = list1
                # 用过的链表向后移动
                list1 = list1.next
            
            else:
                cur.next = list2
                list2 =list2.next

            cur = cur.next
        
        # 如果两个链表有一个空了，直接将另外一个有序链表直接进行拼接
        if list1:
            cur.next =list1
        else:
            cur.next = list2
        # 返回虚拟节点的下一个节点
        return dummy.next
