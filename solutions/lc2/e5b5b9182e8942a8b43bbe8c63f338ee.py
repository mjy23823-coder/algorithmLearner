class Solution:
    def addTwoNumbers(self, l1, l2):
        # 先说明变量含义，再完成你的实现
        dummy = ListNode(0)
        cur = dummy
        # 进位标识
        carry = 0

        while l1 is not None or l2 is not None or carry != 0 :
            # l1非空
            if l1 is not None:
                num1 = l1.val
            else :
                num1 = 0
            # l2非空
            if l2 is not None:
                num2 = l2.val
            else :
                num2 = 0
            # 
            total = num1+num2+carry
            digit = total%10
            cur.next = ListNode(digit)
            cur = cur.next
            # 进位
            carry = total//10

            # l1,l2非空
            if l1 is not None:
                l1 = l1.next
            if l2 is not None:
                l2 = l2.next
            
        return dummy.next
