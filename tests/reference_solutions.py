"""开发验证用的参考实现，不由网页提供，用于核对内置用例和输入输出契约。"""
from textwrap import indent
from tools.problem_bank import BANK

INORDER = """def visit(n):
    return visit(n.left) + [n.val] + visit(n.right) if n else []
values = visit(root)
"""

BODIES = {
"1": """for i in range(len(nums)):
    for j in range(i+1, len(nums)):
        if nums[i]+nums[j] == target: return [i,j]
""",
"3": """best = 0
for i in range(len(s)):
    seen = set()
    for c in s[i:]:
        if c in seen: break
        seen.add(c)
        best = max(best,len(seen))
return best
""",
"11": "return max(min(height[i],height[j])*(j-i) for i in range(len(height)) for j in range(i+1,len(height)))",
"15": """out = set()
for i in range(len(nums)):
    for j in range(i+1,len(nums)):
        for k in range(j+1,len(nums)):
            if nums[i]+nums[j]+nums[k] == 0: out.add(tuple(sorted([nums[i],nums[j],nums[k]])))
return [list(t) for t in out]
""",
"16": "return min((nums[i]+nums[j]+nums[k] for i in range(len(nums)) for j in range(i+1,len(nums)) for k in range(j+1,len(nums))),key=lambda s:abs(s-target))",
"20": """stack=[]
for c in s:
    if c in '([{': stack.append(c)
    elif not stack or stack.pop() != {')':'(',']':'[','}':'{'}[c]: return False
return not stack
""",
"26": "values=sorted(set(nums))\nnums[:len(values)]=values\nreturn len(values)",
"27": "values=[n for n in nums if n != val]\nnums[:len(values)]=values\nreturn len(values)",
"42": "return sum(max(0,min(max(height[:i+1]),max(height[i:]))-height[i]) for i in range(len(height)))",
"94": INORDER+"return values",
"98": """def valid(n,low,high):
    return not n or (low<n.val<high and valid(n.left,low,n.val) and valid(n.right,n.val,high))
return valid(root,float('-inf'),float('inf'))
""",
"100": """def same(a,b):
    if not a or not b: return a is b
    return a.val == b.val and same(a.left,b.left) and same(a.right,b.right)
return same(p,q)
""",
"101": """def mirror(a,b):
    if not a or not b: return a is b
    return a.val == b.val and mirror(a.left,b.right) and mirror(a.right,b.left)
return not root or mirror(root.left,root.right)
""",
"102": """queue=[root] if root else []
answer=[]
while queue:
    answer.append([n.val for n in queue])
    queue=[c for n in queue for c in [n.left,n.right] if c]
return answer
""",
"104": """def height(n):
    return 1+max(height(n.left),height(n.right)) if n else 0
return height(root)
""",
"108": """def make(values):
    if not values: return None
    i=len(values)//2
    return TreeNode(values[i],make(values[:i]),make(values[i+1:]))
return make(nums)
""",
"110": """def height(n):
    if not n: return 0
    l,r=height(n.left),height(n.right)
    return -1 if l<0 or r<0 or abs(l-r)>1 else 1+max(l,r)
return height(root)>=0
""",
"112": """def visit(n,total):
    if not n: return False
    if not n.left and not n.right: return total==n.val
    return visit(n.left,total-n.val) or visit(n.right,total-n.val)
return visit(root,targetSum)
""",
"144": """def visit(n):
    return [n.val]+visit(n.left)+visit(n.right) if n else []
return visit(root)
""",
"145": """def visit(n):
    return visit(n.left)+visit(n.right)+[n.val] if n else []
return visit(root)
""",
"167": """for i in range(len(numbers)):
    for j in range(i+1,len(numbers)):
        if numbers[i]+numbers[j]==target: return [i+1,j+1]
""",
"203": """dummy=ListNode(0,head)
p=dummy
while p.next:
    if p.next.val==val: p.next=p.next.next
    else: p=p.next
return dummy.next
""",
"206": """prev=None
while head:
    nxt=head.next
    head.next=prev
    prev,head=head,nxt
return prev
""",
"209": """answer=len(nums)+1
for i in range(len(nums)):
    total=0
    for j in range(i,len(nums)):
        total+=nums[j]
        if total>=target:
            answer=min(answer,j-i+1)
            break
return 0 if answer>len(nums) else answer
""",
"217": "return len(set(nums))!=len(nums)",
"226": """def invert(n):
    if n: n.left,n.right=invert(n.right),invert(n.left)
    return n
return invert(root)
""",
"230": INORDER+"return values[k-1]",
"235": """def lca(n):
    if n is None or n is p or n is q: return n
    a,b=lca(n.left),lca(n.right)
    return n if a and b else a or b
return lca(root)
""",
"242": "from collections import Counter\nreturn Counter(s)==Counter(t)",
"257": """def visit(n,path):
    if not n: return []
    path=path+[str(n.val)]
    if not n.left and not n.right: return ['->'.join(path)]
    return visit(n.left,path)+visit(n.right,path)
return visit(root,[])
""",
"283": "nums[:]=[v for v in nums if v!=0]+[0]*nums.count(0)",
"344": "s.reverse()",
"404": """def visit(n,left=False):
    if not n: return 0
    if not n.left and not n.right: return n.val if left else 0
    return visit(n.left,True)+visit(n.right,False)
return visit(root)
""",
"438": "return [i for i in range(len(s)-len(p)+1) if sorted(s[i:i+len(p)])==sorted(p)]",
"450": INORDER+"""def make(v):
    if not v: return None
    i=len(v)//2
    return TreeNode(v[i],make(v[:i]),make(v[i+1:]))
return make([v for v in values if v!=key])
""",
"501": INORDER+"from collections import Counter\nc=Counter(values)\nreturn [v for v,n in c.items() if n==max(c.values())]",
"530": INORDER+"return min(b-a for a,b in zip(values,values[1:]))",
"538": """total=0
def visit(n):
    nonlocal total
    if n:
        visit(n.right)
        total+=n.val
        n.val=total
        visit(n.left)
visit(root)
return root
""",
"543": """answer=0
def height(n):
    nonlocal answer
    if not n: return 0
    a,b=height(n.left),height(n.right)
    answer=max(answer,a+b)
    return 1+max(a,b)
height(root)
return answer
""",
"567": "return any(sorted(s2[i:i+len(s1)])==sorted(s1) for i in range(len(s2)-len(s1)+1))",
"617": """def merge(a,b):
    if not a: return b
    if not b: return a
    return TreeNode(a.val+b.val,merge(a.left,b.left),merge(a.right,b.right))
return merge(root1,root2)
""",
"669": """def trim(n):
    if not n: return None
    if n.val<low: return trim(n.right)
    if n.val>high: return trim(n.left)
    n.left,n.right=trim(n.left),trim(n.right)
    return n
return trim(root)
""",
"700": """while root and root.val!=val:
    root=root.left if val<root.val else root.right
return root
""",
"701": INORDER+"""def make(v):
    if not v: return None
    i=len(v)//2
    return TreeNode(v[i],make(v[:i]),make(v[i+1:]))
return make(sorted(values+[val]))
""",
"977": "return sorted(v*v for v in nums)",
"1047": """stack=[]
for c in s:
    if stack and stack[-1]==c: stack.pop()
    else: stack.append(c)
return ''.join(stack)
""",
"125": "t=[c.lower() for c in s if c.isalnum()]\nreturn t==t[::-1]",
"75": "nums.sort()",
"18": """out=set()
n=len(nums)
for a in range(n):
    for b in range(a+1,n):
        for c in range(b+1,n):
            for d in range(c+1,n):
                if nums[a]+nums[b]+nums[c]+nums[d]==target: out.add(tuple(sorted([nums[a],nums[b],nums[c],nums[d]])))
return [list(t) for t in out]
""",
"904": """best=0
for i in range(len(fruits)):
    for j in range(i,len(fruits)):
        if len(set(fruits[i:j+1]))<=2: best=max(best,j-i+1)
return best
""",
"1004": """best=0
for i in range(len(nums)):
    for j in range(i,len(nums)):
        if nums[i:j+1].count(0)<=k: best=max(best,j-i+1)
return best
""",
"424": """best=0
for i in range(len(s)):
    for j in range(i,len(s)):
        part=s[i:j+1]
        if len(part)-max(part.count(c) for c in set(part))<=k: best=max(best,len(part))
return best
""",
"76": """from collections import Counter
need=Counter(t)
best=''
for i in range(len(s)):
    for j in range(i,len(s)):
        part=s[i:j+1]
        if not need-Counter(part) and (not best or len(part)<len(best)): best=part
return best
""",
"21": """values=[]
for head in (list1,list2):
    while head: values.append(head.val); head=head.next
dummy=tail=ListNode()
for v in sorted(values): tail.next=ListNode(v); tail=tail.next
return dummy.next
""",
"876": """nodes=[]
while head: nodes.append(head); head=head.next
return nodes[len(nodes)//2]
""",
"234": """values=[]
while head: values.append(head.val); head=head.next
return values==values[::-1]
""",
"19": """nodes=[]
cur=head
while cur: nodes.append(cur); cur=cur.next
i=len(nodes)-n
if i==0: return head.next
nodes[i-1].next=nodes[i].next
return head
""",
"24": """nodes=[]
while head: nodes.append(head); head=head.next
for i in range(0,len(nodes)-1,2): nodes[i],nodes[i+1]=nodes[i+1],nodes[i]
dummy=tail=ListNode()
for node in nodes: tail.next=node; tail=node
tail.next=None
return dummy.next
""",
"2": """def number(node):
    digits=[]
    while node: digits.append(str(node.val)); node=node.next
    return int(''.join(reversed(digits)))
dummy=tail=ListNode()
for c in reversed(str(number(l1)+number(l2))): tail.next=ListNode(int(c)); tail=tail.next
return dummy.next
""",
"92": """values=[]
while head: values.append(head.val); head=head.next
values[left-1:right]=values[left-1:right][::-1]
dummy=tail=ListNode()
for v in values: tail.next=ListNode(v); tail=tail.next
return dummy.next
""",
"383": "return all(ransomNote.count(c)<=magazine.count(c) for c in set(ransomNote))",
"49": """groups={}
for w in strs: groups.setdefault(''.join(sorted(w)),[]).append(w)
return list(groups.values())
""",
"128": """values=sorted(set(nums))
best=run=0
for i,v in enumerate(values):
    run=run+1 if i and values[i-1]==v-1 else 1
    best=max(best,run)
return best
""",
"560": "return sum(sum(nums[i:j+1])==k for i in range(len(nums)) for j in range(i,len(nums)))",
"454": "return sum(a+b+c+d==0 for a in nums1 for b in nums2 for c in nums3 for d in nums4)",
"14": """prefix=''
for chars in zip(*strs):
    if len(set(chars))>1: break
    prefix+=chars[0]
return prefix
""",
"151": "return ' '.join(reversed(s.split()))",
"5": """best=''
for i in range(len(s)):
    for j in range(i,len(s)):
        part=s[i:j+1]
        if part==part[::-1] and len(part)>len(best): best=part
return best
""",
"459": "return any(len(s)%n==0 and s[:n]*(len(s)//n)==s for n in range(1,len(s)//2+1))",
"150": """stack=[]
for t in tokens:
    if t in '+-*/':
        b,a=stack.pop(),stack.pop()
        stack.append(a+b if t=='+' else a-b if t=='-' else a*b if t=='*' else int(a/b))
    else: stack.append(int(t))
return stack[0]
""",
"739": "return [next((j-i for j in range(i+1,len(temperatures)) if temperatures[j]>t),0) for i,t in enumerate(temperatures)]",
"239": "return [max(nums[i:i+k]) for i in range(len(nums)-k+1)]",
"347": """from collections import Counter
return [v for v,_ in Counter(nums).most_common(k)]
""",
"199": """out,level=[],[root] if root else []
while level:
    out.append(level[-1].val)
    level=[c for n in level for c in (n.left,n.right) if c]
return out
""",
"513": """level=[root]
while True:
    nxt=[c for n in level for c in (n.left,n.right) if c]
    if not nxt: return level[0].val
    level=nxt
""",
"105": """def build(pre,ino):
    if not pre: return None
    i=ino.index(pre[0])
    return TreeNode(pre[0],build(pre[1:i+1],ino[:i]),build(pre[i+1:],ino[i+1:]))
return build(preorder,inorder)
""",
"437": """def down(n,rest):
    return 0 if not n else (n.val==rest)+down(n.left,rest-n.val)+down(n.right,rest-n.val)
def walk(n):
    return 0 if not n else down(n,targetSum)+walk(n.left)+walk(n.right)
return walk(root)
""",
"222": """def count(n):
    return 0 if not n else 1+count(n.left)+count(n.right)
return count(root)
""",
}
BODIES["236"] = BODIES["235"]


def solution(pid):
    entry=BANK[pid]
    return f"class Solution:\n    def {entry['method']}(self, {', '.join(entry['params'])}):\n" + indent(BODIES[pid], "        ") + "\n"
