"""本项目题目的本地练习契约。题意为简述，用例不是平台完整判题集。"""
from copy import deepcopy

try:
    from . import catalog, statements
except ImportError:
    import catalog
    import statements


def case(args, expected, name=""):
    return {"name": name, "args": args, "expected": expected}


def spec(method, params, description, cases, codecs=None, judge="value"):
    return {"method": method, "params": params.split(","), "description": description,
            "cases": [dict(c, name=c["name"] or f"用例 {i+1}") for i, c in enumerate(cases)],
            "codecs": codecs or ["json"] * len(params.split(",")), "judge": judge}


BANK = {
    "1": spec("twoSum", "nums,target", "在数组中找出两个不同位置，使对应数值之和等于 target，返回这两个下标。", [case([[2,7,11,15],9],[0,1]),case([[3,2,4],6],[1,2]),case([[3,3],6],[0,1])], judge="two_sum"),
    "3": spec("lengthOfLongestSubstring", "s", "返回字符串中不含重复字符的最长连续子串的长度。", [case(["abcabcbb"],3),case(["bbbbb"],1),case([""],0),case(["abba"],2)]),
    "11": spec("maxArea", "height", "选择两根竖线作为容器两侧，返回能容纳的最大面积。", [case([[1,8,6,2,5,4,8,3,7]],49),case([[1,1]],1),case([[4,3,2,1,4]],16)]),
    "15": spec("threeSum", "nums", "找出所有和为 0 的不重复三元组，三元组和结果的排列顺序不限。", [case([[-1,0,1,2,-1,-4]],[[-1,-1,2],[-1,0,1]]),case([[0,0,0,0]],[[0,0,0]]),case([[1,2,3]],[])], judge="triplets"),
    "16": spec("threeSumClosest", "nums,target", "选取三个不同下标，返回最接近 target 的三数之和；用例保证最优和唯一。", [case([[-1,2,1,-4],1],2),case([[0,0,0],1],0),case([[1,2,3],8],6)]),
    "20": spec("isValid", "s", "检查括号字符串是否正确配对并按嵌套顺序闭合。", [case(["()[]{}"],True),case(["([)]"],False),case(["("],False),case(["{[]}"],True)]),
    "26": spec("removeDuplicates", "nums", "原地去重有序数组，返回有效长度 k；检查修改后的 nums[:k]。", [case([[1,1,2]],{"k":2,"prefix":[1,2]}),case([[]],{"k":0,"prefix":[]}),case([[0,0,1,1,1,2,2,3,3,4]],{"k":5,"prefix":[0,1,2,3,4]})], judge="unique_prefix"),
    "27": spec("removeElement", "nums,val", "原地移除指定值并返回有效长度，前 k 个保留元素的顺序不限。", [case([[3,2,2,3],3],{"k":2,"prefix":[2,2]}),case([[],1],{"k":0,"prefix":[]}),case([[0,1,2,2,3,0,4,2],2],{"k":5,"prefix":[0,1,3,0,4]})], judge="remove_prefix"),
    "42": spec("trap", "height", "每列宽度为 1，返回这些柱子在下雨后能积存的总水量。", [case([[0,1,0,2,1,0,1,3,2,1,2,1]],6),case([[4,2,0,3,2,5]],9),case([[1]],0),case([[2,0,2]],2)]),
    "94": spec("inorderTraversal", "root", "返回二叉树的中序遍历值序列。输入树使用层序数组，null 表示空节点。", [case([[1,None,2,3]],[1,3,2]),case([[]],[]),case([[1]],[1])], ["tree"]),
    "98": spec("isValidBST", "root", "判断每个节点是否都满足严格的二叉搜索树上下界约束。", [case([[2,1,3]],True),case([[5,1,4,None,None,3,6]],False),case([[2,2,2]],False)], ["tree"]),
    "100": spec("isSameTree", "p,q", "判断两棵树的结构和对应节点值是否完全相同。", [case([[1,2,3],[1,2,3]],True),case([[1,2],[1,None,2]],False),case([[],[]],True)], ["tree","tree"]),
    "101": spec("isSymmetric", "root", "判断一棵二叉树是否关于根节点左右镜像对称。", [case([[1,2,2,3,4,4,3]],True),case([[1,2,2,None,3,None,3]],False),case([[1]],True)], ["tree"]),
    "102": spec("levelOrder", "root", "按层从左到右收集节点值，每层单独返回一个列表。", [case([[3,9,20,None,None,15,7]],[[3],[9,20],[15,7]]),case([[]],[]),case([[1]],[[1]])], ["tree"]),
    "104": spec("maxDepth", "root", "返回二叉树从根到叶子的最长路径上的节点数。", [case([[3,9,20,None,None,15,7]],3),case([[]],0),case([[1,None,2]],2)], ["tree"]),
    "108": spec("sortedArrayToBST", "nums", "将升序数组构造成高度平衡的 BST；接受任意满足条件的树。期望值描述验收条件。", [case([[-10,-3,0,5,9]],{"inorder":[-10,-3,0,5,9],"balanced":True}),case([[1,3]],{"inorder":[1,3],"balanced":True}),case([[1]],{"inorder":[1],"balanced":True})], judge="balanced_bst"),
    "110": spec("isBalanced", "root", "判断所有节点的左右子树高度差是否都不超过 1。", [case([[3,9,20,None,None,15,7]],True),case([[1,2,2,3,3,None,None,4,4]],False),case([[]],True)], ["tree"]),
    "112": spec("hasPathSum", "root,targetSum", "判断是否存在一条根到叶子的路径，其节点值之和等于 targetSum。", [case([[5,4,8,11,None,13,4,7,2,None,None,None,1],22],True),case([[1,2,3],5],False),case([[],0],False)], ["tree","json"]),
    "144": spec("preorderTraversal", "root", "返回二叉树的前序遍历值序列。", [case([[1,None,2,3]],[1,2,3]),case([[]],[]),case([[2,1,3]],[2,1,3])], ["tree"]),
    "145": spec("postorderTraversal", "root", "返回二叉树的后序遍历值序列。", [case([[1,None,2,3]],[3,2,1]),case([[]],[]),case([[2,1,3]],[1,3,2])], ["tree"]),
    "167": spec("twoSum", "numbers,target", "在升序数组中找到两数之和为 target 的两个位置，返回从 1 开始的下标。", [case([[2,7,11,15],9],[1,2]),case([[-1,0],-1],[1,2]),case([[2,3,4],6],[1,3])], judge="two_sum_1based"),
    "203": spec("removeElements", "head,val", "移除链表中所有值等于 val 的节点，返回新头节点。输入输出以数组显示。", [case([[1,2,6,3,4,5,6],6],[1,2,3,4,5]),case([[7,7,7],7],[]),case([[],1],[])], ["list","json"], "linked_list"),
    "206": spec("reverseList", "head", "反转单链表并返回新的头节点。输入输出以数组显示。", [case([[1,2,3,4,5]],[5,4,3,2,1]),case([[]],[]),case([[1]],[1])], ["list"], "linked_list"),
    "209": spec("minSubArrayLen", "target,nums", "正整数数组中，找出和至少为 target 的最短连续子数组长度；不存在则返回 0。", [case([7,[2,3,1,2,4,3]],2),case([4,[1,4,4]],1),case([11,[1,1,1,1]],0)]),
    "217": spec("containsDuplicate", "nums", "判断数组中是否存在重复元素。", [case([[1,2,3,1]],True),case([[1,2,3,4]],False),case([[1]],False)]),
    "226": spec("invertTree", "root", "交换每个节点的左右子树并返回根节点，输出按层序序列化。", [case([[4,2,7,1,3,6,9]],[4,7,2,9,6,3,1]),case([[]],[]),case([[1,2]],[1,None,2])], ["tree"], "tree"),
    "230": spec("kthSmallest", "root,k", "返回 BST 按升序排列的第 k 个值，k 从 1 开始。", [case([[3,1,4,None,2],1],1),case([[5,3,6,2,4,None,None,1],3],3),case([[1],1],1)], ["tree","json"]),
    "235": spec("lowestCommonAncestor", "root,p,q", "返回 BST 中 p 和 q 的最近公共祖先。输入 p、q 是树中唯一的节点值，运行时转换为原树节点。", [case([[6,2,8,0,4,7,9,None,None,3,5],2,8],6),case([[6,2,8,0,4,7,9,None,None,3,5],2,4],2),case([[2,1],2,1],2)], ["tree","node","node"], "ancestor"),
    "236": spec("lowestCommonAncestor", "root,p,q", "返回普通二叉树中 p 和 q 的最近公共祖先，p、q 均存在且节点值唯一。", [case([[3,5,1,6,2,0,8,None,None,7,4],5,1],3),case([[3,5,1,6,2,0,8,None,None,7,4],5,4],5),case([[1,2],1,2],1)], ["tree","node","node"], "ancestor"),
    "242": spec("isAnagram", "s,t", "判断两个字符串的字符及各字符出现次数是否一致。", [case(["anagram","nagaram"],True),case(["rat","car"],False),case(["a","aa"],False)]),
    "257": spec("binaryTreePaths", "root", "返回所有根到叶子路径，用 -> 连接节点值，结果顺序不限。", [case([[1,2,3,None,5]],["1->2->5","1->3"]),case([[1]],["1"]),case([[2,None,3]],["2->3"])], ["tree"], "unordered"),
    "283": spec("moveZeroes", "nums", "原地将所有 0 移到末尾，保留非零元素的相对顺序；检查修改后的数组。", [case([[0,1,0,3,12]],[1,3,12,0,0]),case([[0]],[0]),case([[1,2,3]],[1,2,3])], judge="mutated_array"),
    "344": spec("reverseString", "s", "原地反转字符数组；检查传入数组修改后的内容。", [case([["h","e","l","l","o"]],["o","l","l","e","h"]),case([["a"]],["a"]),case([["a","b"]],["b","a"])], judge="mutated_array"),
    "404": spec("sumOfLeftLeaves", "root", "累加所有既是左孩子又是叶子的节点值。", [case([[3,9,20,None,None,15,7]],24),case([[1]],0),case([[1,2,3,4,5]],4)], ["tree"]),
    "438": spec("findAnagrams", "s,p", "返回 s 中所有与 p 字符计数相同的固定长度窗口的起始下标。", [case(["cbaebabacd","abc"],[0,6]),case(["abab","ab"],[0,1,2]),case(["a","ab"],[])], judge="unordered"),
    "450": spec("deleteNode", "root,key", "在 BST 中删除 key，返回合法的 BST。验收检查中序结果，接受前驱或后继等不同删除策略。", [case([[5,3,6,2,4,None,7],3],{"inorder":[2,4,5,6,7]}),case([[5,3,6,2,4,None,7],0],{"inorder":[2,3,4,5,6,7]}),case([[],0],{"inorder":[]})], ["tree","json"], "bst"),
    "501": spec("findMode", "root", "返回允许重复值的 BST 中出现次数最多的所有值，顺序不限。", [case([[1,None,2,2]],[2]),case([[0]],[0]),case([[2,1,3]],[1,2,3])], ["tree"], "unordered"),
    "530": spec("getMinimumDifference", "root", "在至少含两个节点的 BST 中，返回任意两节点值的最小绝对差。", [case([[4,2,6,1,3]],1),case([[1,0,48,None,None,12,49]],1),case([[5,1,9]],4)], ["tree"]),
    "538": spec("convertBST", "root", "将 BST 中每个值改为原树中不小于它的所有值的和，保留树结构并返回根。", [case([[4,1,6,0,2,5,7,None,None,None,3,None,None,None,8]],[30,36,21,36,35,26,15,None,None,None,33,None,None,None,8]),case([[0,None,1]],[1,None,1]),case([[]],[])], ["tree"], "tree"),
    "543": spec("diameterOfBinaryTree", "root", "返回二叉树中任意两节点之间最长路径的边数。", [case([[1,2,3,4,5]],3),case([[1,2]],1),case([[1]],0)], ["tree"]),
    "567": spec("checkInclusion", "s1,s2", "判断 s2 是否包含一个字符计数与 s1 相同的连续窗口。", [case(["ab","eidbaooo"],True),case(["ab","eidboaoo"],False),case(["abc","ab"],False)]),
    "617": spec("mergeTrees", "root1,root2", "重叠节点的值相加，只有单侧节点时保留它，返回合并后的树。", [case([[1,3,2,5],[2,1,3,None,4,None,7]],[3,4,5,5,4,None,7]),case([[1],[1,2]],[2,2]),case([[],[1]],[1])], ["tree","tree"], "tree"),
    "669": spec("trimBST", "root,low,high", "修剪掉范围外的 BST 节点，保留范围内节点的相对结构，返回根。", [case([[1,0,2],1,2],[1,None,2]),case([[3,0,4,None,2,None,None,1],1,3],[3,2,None,1]),case([[1],2,3],[])], ["tree","json","json"], "tree"),
    "700": spec("searchBST", "root,val", "在 BST 中寻找值为 val 的节点，返回该节点作为根的子树，未找到返回 None。", [case([[4,2,7,1,3],2],[2,1,3]),case([[4,2,7,1,3],5],[]),case([[1],1],[1])], ["tree","json"], "tree"),
    "701": spec("insertIntoBST", "root,val", "将新值插入 BST，返回合法 BST。中序结果一致即可，不限定唯一结构。", [case([[4,2,7,1,3],5],{"inorder":[1,2,3,4,5,7]}),case([[],5],{"inorder":[5]}),case([[2,1,3],4],{"inorder":[1,2,3,4]})], ["tree","json"], "bst"),
    "977": spec("sortedSquares", "nums", "返回升序数组每个元素平方后仍按升序排列的数组。", [case([[-4,-1,0,3,10]],[0,1,9,16,100]),case([[-7,-3,2,3,11]],[4,9,9,49,121]),case([[-1]],[1])]),
    "1047": spec("removeDuplicates", "s", "反复消除相邻的两个相同字符，返回最终字符串。", [case(["abbaca"],"ca"),case(["azxxzy"],"ay"),case(["aaaa"],"")]),
}

# 候选新题与模拟面试题（见 catalog.py）。加入待学队列后即可在工作台练习。
BANK.update({
    "125": spec("isPalindrome", "s", "只考虑字母和数字并忽略大小写，判断字符串是否是回文串。", [case(["A man, a plan, a canal: Panama"],True),case(["race a car"],False),case([" "],True),case(["0P"],False)]),
    "75": spec("sortColors", "nums", "数组只含 0、1、2，原地排序使相同颜色相邻并按 0、1、2 排列；检查修改后的数组。", [case([[2,0,2,1,1,0]],[0,0,1,1,2,2]),case([[2,0,1]],[0,1,2]),case([[0]],[0])], judge="mutated_array"),
    "18": spec("fourSum", "nums,target", "找出所有和为 target 的不重复四元组，四元组和结果的排列顺序不限。", [case([[1,0,-1,0,-2,2],0],[[-2,-1,1,2],[-2,0,0,2],[-1,0,0,1]]),case([[2,2,2,2,2],8],[[2,2,2,2]]),case([[1,2,3],6],[])], judge="nested_unordered"),
    "904": spec("totalFruit", "fruits", "两个篮子各只能装一种水果，从任意位置开始连续采摘，返回最多能采的水果数。", [case([[1,2,1]],3),case([[0,1,2,2]],3),case([[1,2,3,2,2]],4),case([[3,3,3,1,2,1,1,2,3,3,4]],5)]),
    "1004": spec("longestOnes", "nums,k", "最多把 k 个 0 翻转成 1，返回只含 1 的最长连续子数组长度。", [case([[1,1,1,0,0,0,1,1,1,1,0],2],6),case([[0,0,1,1,0,0,1,1,1,0,1,1,0,0,0,1,1,1,1],3],10),case([[0,0],0],0)]),
    "424": spec("characterReplacement", "s,k", "最多替换 k 个字符，返回只含同一字母的最长子串长度。", [case(["ABAB",2],4),case(["AABABBA",1],4),case(["A",0],1)]),
    "76": spec("minWindow", "s,t", "返回 s 中涵盖 t 所有字符（含重复）的最短子串；不存在则返回空字符串，用例答案唯一。", [case(["ADOBECODEBANC","ABC"],"BANC"),case(["a","a"],"a"),case(["a","aa"],"")]),
    "21": spec("mergeTwoLists", "list1,list2", "合并两个升序链表为一个新的升序链表并返回头节点。输入输出以数组显示。", [case([[1,2,4],[1,3,4]],[1,1,2,3,4,4]),case([[],[]],[]),case([[],[0]],[0])], ["list","list"], "linked_list"),
    "876": spec("middleNode", "head", "返回链表的中间结点；有两个中间结点时返回第二个。输出为从该结点开始的链表。", [case([[1,2,3,4,5]],[3,4,5]),case([[1,2,3,4,5,6]],[4,5,6]),case([[1]],[1])], ["list"], "linked_list"),
    "234": spec("isPalindrome", "head", "判断单链表的值序列是否是回文。", [case([[1,2,2,1]],True),case([[1,2]],False),case([[1]],True)], ["list"]),
    "19": spec("removeNthFromEnd", "head,n", "删除链表的倒数第 n 个结点并返回头节点。输入输出以数组显示。", [case([[1,2,3,4,5],2],[1,2,3,5]),case([[1],1],[]),case([[1,2],1],[1]),case([[1,2],2],[2])], ["list","json"], "linked_list"),
    "24": spec("swapPairs", "head", "两两交换相邻结点（交换结点而不是只改值），返回新头节点。", [case([[1,2,3,4]],[2,1,4,3]),case([[]],[]),case([[1]],[1]),case([[1,2,3]],[2,1,3])], ["list"], "linked_list"),
    "2": spec("addTwoNumbers", "l1,l2", "两个链表逆序存储非负整数的各位数字，返回两数之和的逆序链表。", [case([[2,4,3],[5,6,4]],[7,0,8]),case([[0],[0]],[0]),case([[9,9,9,9,9,9,9],[9,9,9,9]],[8,9,9,9,0,0,0,1])], ["list","list"], "linked_list"),
    "92": spec("reverseBetween", "head,left,right", "反转链表中从第 left 个到第 right 个结点（从 1 开始计数）的部分，返回头节点。", [case([[1,2,3,4,5],2,4],[1,4,3,2,5]),case([[5],1,1],[5]),case([[3,5],1,2],[5,3])], ["list","json","json"], "linked_list"),
    "383": spec("canConstruct", "ransomNote,magazine", "判断 ransomNote 能否由 magazine 中的字符构成，每个字符只能用一次。", [case(["a","b"],False),case(["aa","ab"],False),case(["aa","aab"],True)]),
    "49": spec("groupAnagrams", "strs", "把字母异位词分到同一组，组内与组间顺序都不限。", [case([["eat","tea","tan","ate","nat","bat"]],[["bat"],["nat","tan"],["ate","eat","tea"]]),case([[""]],[[""]]),case([["a"]],[["a"]])], judge="nested_unordered"),
    "128": spec("longestConsecutive", "nums", "返回未排序数组中数字连续的最长序列长度，要求思考 O(n) 做法。", [case([[100,4,200,1,3,2]],4),case([[0,3,7,2,5,8,4,6,0,1]],9),case([[]],0),case([[1,0,1,2]],3)]),
    "560": spec("subarraySum", "nums,k", "返回和为 k 的连续子数组个数；数组可能含负数。", [case([[1,1,1],2],2),case([[1,2,3],3],2),case([[1,-1,0],0],3)]),
    "454": spec("fourSumCount", "nums1,nums2,nums3,nums4", "四个等长数组各取一个元素，统计和为 0 的下标组合数。", [case([[1,2],[-2,-1],[-1,2],[0,2]],2),case([[0],[0],[0],[0]],1),case([[1],[1],[1],[1]],0)]),
    "14": spec("longestCommonPrefix", "strs", "返回字符串数组的最长公共前缀，不存在则返回空字符串。", [case([["flower","flow","flight"]],"fl"),case([["dog","racecar","car"]],""),case([["a"]],"a")]),
    "151": spec("reverseWords", "s", "反转单词顺序，结果中单词之间只保留一个空格且没有首尾空格。", [case(["the sky is blue"],"blue is sky the"),case(["  hello world  "],"world hello"),case(["a good   example"],"example good a")]),
    "5": spec("longestPalindrome", "s", "返回 s 中最长的回文子串。可能有多个正确答案，期望值列出全部可接受的结果。", [case(["babad"],["bab","aba"]),case(["cbbd"],["bb"]),case(["a"],["a"])], judge="one_of"),
    "459": spec("repeatedSubstringPattern", "s", "判断字符串能否由它的某个子串重复多次构成。", [case(["abab"],True),case(["aba"],False),case(["abcabcabcabc"],True)]),
    "150": spec("evalRPN", "tokens", "计算逆波兰表达式；除法向零截断，表达式保证有效。", [case([["2","1","+","3","*"]],9),case([["4","13","5","/","+"]],6),case([["10","6","9","3","+","-11","*","/","*","17","+","5","+"]],22)]),
    "739": spec("dailyTemperatures", "temperatures", "对每一天，返回要等几天才会出现更高温度；之后都不会升温则为 0。", [case([[73,74,75,71,69,72,76,73]],[1,1,4,2,1,1,0,0]),case([[30,40,50,60]],[1,1,1,0]),case([[30,60,90]],[1,1,0])]),
    "239": spec("maxSlidingWindow", "nums,k", "大小为 k 的窗口从左向右滑动，返回每个窗口中的最大值。", [case([[1,3,-1,-3,5,3,6,7],3],[3,3,5,5,6,7]),case([[1],1],[1]),case([[9,8,7,6],2],[9,8,7])]),
    "347": spec("topKFrequent", "nums,k", "返回出现频率前 k 高的元素，顺序不限；用例答案唯一。", [case([[1,1,1,2,2,3],2],[1,2]),case([[1],1],[1]),case([[4,4,5,5,5,6],1],[5])], judge="unordered"),
    "199": spec("rightSideView", "root", "从右侧看二叉树，按从上到下返回每层能看到的节点值。", [case([[1,2,3,None,5,None,4]],[1,3,4]),case([[1,None,3]],[1,3]),case([[]],[])], ["tree"]),
    "513": spec("findBottomLeftValue", "root", "返回二叉树最底层最左边节点的值。", [case([[2,1,3]],1),case([[1,2,3,4,None,5,6,None,None,7]],7),case([[1]],1)], ["tree"]),
    "105": spec("buildTree", "preorder,inorder", "根据无重复值的前序与中序遍历构造二叉树并返回根，输出按层序序列化。", [case([[3,9,20,15,7],[9,3,15,20,7]],[3,9,20,None,None,15,7]),case([[-1],[-1]],[-1]),case([[1,2],[2,1]],[1,2])], judge="tree"),
    "437": spec("pathSum", "root,targetSum", "统计节点值之和等于 targetSum 的向下路径数，路径不必从根开始或在叶子结束。", [case([[10,5,-3,3,2,None,11,3,-2,None,1],8],3),case([[5,4,8,11,None,13,4,7,2,None,None,5,1],22],3),case([[],0],0)], ["tree","json"]),
    "222": spec("countNodes", "root", "返回完全二叉树的节点个数；可先写 O(n)，再思考利用完全二叉树性质。", [case([[1,2,3,4,5,6]],6),case([[]],0),case([[1]],1)], ["tree"]),
})


def get_exercise(pid):
    if pid not in BANK:
        return None
    value = deepcopy(BANK[pid])
    # description 用完整题意（页面、教练和智能体都读它），原来的一句话简述保留在 summary。
    value["summary"] = value["description"]
    value["description"] = statements.text(pid) or value["description"]
    args = ", ".join(value["params"])
    value["starter"] = f"class Solution:\n    def {value['method']}(self, {args}):\n        # 先说明变量含义，再完成你的实现\n        pass\n"
    value["hints"] = ["先用自己的话解释输入和输出，再判断属于哪种题型。",
                      "用最小的例子手动走一遍，写清每个变量在循环或递归中的含义。",
                      "先列出终止条件、状态更新和返回值；再用一个边界输入检查这三处。"]
    if pid == "42":
        value["hints"] = ["一列能装多少水，与它两侧的阻挡高度有什么关系？",
                          "尝试维护左右两侧遇到的最大高度，判断哪一侧的水位已经能确定。",
                          "把左右指针、两侧最大值和累计水量分开；每轮只结算能够确定的一侧，再移动对应指针。"]
    elif pid in catalog.CATALOG:
        value["hints"][2] = f"关键思路：{catalog.CATALOG[pid]['focus']}。先说清它为什么成立，再列出终止条件、状态更新和返回值。"
    return value
