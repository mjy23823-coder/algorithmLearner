class Solution:
    def reverseList(self, head):
        # 先说明变量含义，再完成你的实现
        prev = None

        cur = head

        while cur !=None:
            temp = cur.next
            cur.next = prev
            prev = cur
            cur = temp

        return prev
