# -*- coding: utf-8 -*-
"""推荐题（尚无本地用例）的题面。用自己的话改写，完整原题以力扣链接为准。"""

EXTRA = {
    # ---------------- 链表 ----------------
    "141": {
        "slug": "linked-list-cycle",
        "method": "hasCycle(head)",
        "text": "给你单链表的头结点 head，判断链表里有没有环：如果顺着 next 一直往后走，会再次走到之前经过的某个结点，就说明有环。"
                "示例里的 pos 只是用来说明尾结点连回哪个下标（-1 表示没有环），它不会作为参数传给你。"
                "有环返回 true，否则返回 false；进阶：能否只用 O(1) 的额外空间。",
        "constraints": ["链表结点数在 [0, 10⁴] 范围内", "-10⁵ ≤ Node.val ≤ 10⁵", "pos 为 -1 或链表中的有效下标"],
        "examples": [
            {"input": "head = [3,2,0,-4], pos = 1", "output": "true", "note": "尾结点 -4 的 next 指回下标 1 的结点 2，形成环。"},
            {"input": "head = [1], pos = -1", "output": "false", "note": "只有一个结点且 next 为空，没有环。"},
        ],
        "figure": {"kind": "list", "value": [3, 2, 0, -4]},
    },
    "142": {
        "slug": "linked-list-cycle-ii",
        "method": "detectCycle(head)",
        "text": "给你单链表的头结点 head，如果链表有环，返回环的第一个结点（从头往后走时最先进入环的那个结点）；没有环则返回 null。"
                "pos 只用于描述尾结点连回哪个下标，不会作为参数传入。"
                "不允许修改链表结构；进阶：能否只用 O(1) 的额外空间。",
        "constraints": ["链表结点数在 [0, 10⁴] 范围内", "-10⁵ ≤ Node.val ≤ 10⁵", "pos 为 -1 或链表中的有效下标"],
        "examples": [
            {"input": "head = [3,2,0,-4], pos = 1", "output": "下标为 1 的结点（值 2）", "note": "尾结点连回下标 1，从头走第一次进入环的就是值为 2 的结点。"},
            {"input": "head = [1,2], pos = 0", "output": "下标为 0 的结点（值 1）", "note": "尾结点 2 连回头结点，整条链表都在环上。"},
        ],
        "figure": {"kind": "list", "value": [3, 2, 0, -4]},
    },
    "160": {
        "slug": "intersection-of-two-linked-lists",
        "method": "getIntersectionNode(headA, headB)",
        "text": "给你两个单链表的头结点 headA 和 headB，如果两条链表从某个结点开始共用同一段结点（是同一个结点对象，而不只是值相等），返回这个起始的公共结点；没有公共结点则返回 null。"
                "保证整个结构中没有环，函数返回后两条链表必须保持原来的结构。"
                "示例中的 intersectVal、skipA、skipB 只用来描述测试数据如何构造，不会传给你。",
        "constraints": ["listA 长度为 m，listB 长度为 n，1 ≤ m, n ≤ 3 × 10⁴", "1 ≤ Node.val ≤ 10⁵"],
        "examples": [
            {"input": "intersectVal = 8, listA = [4,1,8,4,5], listB = [5,6,1,8,4,5], skipA = 2, skipB = 3", "output": "值为 8 的结点",
             "note": "A 跳过 2 个结点、B 跳过 3 个结点后进入同一段 [8,4,5]；两边的 1 值相同但不是同一个结点。"},
            {"input": "intersectVal = 0, listA = [2,6,4], listB = [1,5], skipA = 3, skipB = 2", "output": "null", "note": "两条链表没有任何公共结点。"},
        ],
        "figure": {"kind": "list", "value": [4, 1, 8, 4, 5]},
    },
    "23": {
        "slug": "merge-k-sorted-lists",
        "method": "mergeKLists(lists)",
        "text": "给你一个数组 lists，里面有 k 个链表的头结点，每个链表都已经按升序排好。"
                "把它们合并成一个整体升序的链表，返回合并后链表的头结点；lists 为空或其中链表为空时也要正确处理。",
        "constraints": ["k == lists.length，0 ≤ k ≤ 10⁴", "0 ≤ lists[i].length ≤ 500", "-10⁴ ≤ lists[i][j] ≤ 10⁴，结点总数不超过 10⁴"],
        "examples": [
            {"input": "lists = [[1,4,5],[1,3,4],[2,6]]", "output": "[1,1,2,3,4,4,5,6]", "note": "三条链表的全部结点按升序串成一条。"},
            {"input": "lists = [[]]", "output": "[]", "note": "唯一的链表是空链表，结果也为空。"},
        ],
    },

    # ---------------- 栈与队列 / 设计 ----------------
    "155": {
        "slug": "min-stack",
        "method": "MinStack: push(val), pop(), top(), getMin()",
        "text": "设计一个栈类 MinStack，除了普通的 push(val) 入栈、pop() 删除栈顶、top() 读取栈顶之外，还要支持 getMin() 返回当前栈中的最小值。"
                "要求这四个操作的时间复杂度都是 O(1)。",
        "constraints": ["-2³¹ ≤ val ≤ 2³¹ - 1", "pop、top、getMin 只会在栈非空时调用", "各操作总调用次数 ≤ 3 × 10⁴"],
        "examples": [
            {"input": "ops = [\"MinStack\",\"push\",\"push\",\"push\",\"getMin\",\"pop\",\"top\",\"getMin\"], args = [[],[-2],[0],[-3],[],[],[],[]]",
             "output": "[null,null,null,null,-3,null,0,-2]",
             "note": "压入 -2、0、-3 后最小值是 -3；弹出 -3 后栈顶为 0，最小值变回 -2。"},
        ],
    },
    "232": {
        "slug": "implement-queue-using-stacks",
        "method": "MyQueue: push(x), pop(), peek(), empty()",
        "text": "只用两个栈实现一个先进先出的队列 MyQueue：push(x) 把元素放到队尾，pop() 移除并返回队首，peek() 返回队首但不移除，empty() 判断队列是否为空。"
                "栈只能使用标准操作：压入栈顶、查看或弹出栈顶、获取大小、判断是否为空（Python 中用 list 的 append / pop() / [-1] / len 模拟）。"
                "进阶：能否让每个操作的均摊时间复杂度为 O(1)。",
        "constraints": ["1 ≤ x ≤ 9", "最多调用 100 次 push、pop、peek 和 empty", "pop 和 peek 只会在队列非空时调用"],
        "examples": [
            {"input": "ops = [\"MyQueue\",\"push\",\"push\",\"peek\",\"pop\",\"empty\"], args = [[],[1],[2],[],[],[]]",
             "output": "[null,null,null,1,1,false]",
             "note": "依次放入 1、2，队首是先进来的 1；取走 1 后还剩 2，所以不为空。"},
        ],
    },
    "84": {
        "slug": "largest-rectangle-in-histogram",
        "method": "largestRectangleArea(heights)",
        "text": "给定非负整数数组 heights，表示柱状图中每根柱子的高度，每根柱子宽度都是 1，相邻柱子紧挨着。"
                "在图中能画出的矩形必须完全落在柱子内部，求这样的矩形的最大面积。",
        "constraints": ["1 ≤ heights.length ≤ 10⁵", "0 ≤ heights[i] ≤ 10⁴"],
        "examples": [
            {"input": "heights = [2,1,5,6,2,3]", "output": "10", "note": "高为 5 和 6 的两根相邻柱子能撑起高 5、宽 2 的矩形，面积 10。"},
            {"input": "heights = [2,4]", "output": "4", "note": "单独用高 4 的柱子，或两根柱子取高 2、宽 2，面积都是 4。"},
        ],
        "figure": {"kind": "bars", "value": [2, 1, 5, 6, 2, 3]},
    },
    "215": {
        "slug": "kth-largest-element-in-an-array",
        "method": "findKthLargest(nums, k)",
        "text": "给定整数数组 nums 和整数 k，返回数组中第 k 大的元素。"
                "这里指把数组从大到小排好后排在第 k 位的数，重复的数各自占一个位置（不是第 k 个不同的数）。"
                "力扣希望不靠对整个数组排序来完成（中文站要求 O(n) 时间）。",
        "constraints": ["1 ≤ k ≤ nums.length ≤ 10⁵", "-10⁴ ≤ nums[i] ≤ 10⁴"],
        "examples": [
            {"input": "nums = [3,2,1,5,6,4], k = 2", "output": "5", "note": "从大到小为 6,5,4,3,2,1，第 2 个是 5。"},
            {"input": "nums = [3,2,3,1,2,4,5,5,6], k = 4", "output": "4", "note": "从大到小为 6,5,5,4,…，两个 5 各算一位，第 4 个是 4。"},
        ],
    },
    "295": {
        "slug": "find-median-from-data-stream",
        "method": "MedianFinder: addNum(num), findMedian()",
        "text": "设计类 MedianFinder 接收一串不断到来的整数：addNum(num) 加入一个数，findMedian() 返回目前所有已加入数字的中位数。"
                "中位数指排好序后位于正中间的数；数字个数为偶数时取中间两个数的平均值。与正确答案误差在 10⁻⁵ 以内即可。",
        "constraints": ["-10⁵ ≤ num ≤ 10⁵", "调用 findMedian 之前至少已加入一个数", "addNum 与 findMedian 总调用次数 ≤ 5 × 10⁴"],
        "examples": [
            {"input": "ops = [\"MedianFinder\",\"addNum\",\"addNum\",\"findMedian\",\"addNum\",\"findMedian\"], args = [[],[1],[2],[],[3],[]]",
             "output": "[null,null,null,1.5,null,2.0]",
             "note": "有 1、2 时中位数是 (1+2)/2 = 1.5；再加入 3 后中间的数是 2。"},
        ],
    },

    # ---------------- 二叉树 ----------------
    "114": {
        "slug": "flatten-binary-tree-to-linked-list",
        "method": "flatten(root)",
        "text": "给你二叉树的根结点 root，把它原地展开成一条只往右走的“链表”：每个结点的 left 置为 null，right 指向链表中的下一个结点。"
                "展开后结点的先后顺序要与这棵树的先序遍历（根、左、右）顺序一致。函数不需要返回值，直接修改原树；进阶：能否只用 O(1) 的额外空间。",
        "constraints": ["树中结点数在 [0, 2000] 范围内", "-100 ≤ Node.val ≤ 100"],
        "examples": [
            {"input": "root = [1,2,5,3,4,null,6]", "output": "[1,null,2,null,3,null,4,null,5,null,6]", "note": "先序顺序为 1,2,3,4,5,6，展开后每个结点只有右孩子。"},
            {"input": "root = []", "output": "[]", "note": "空树保持为空。"},
        ],
        "figure": {"kind": "tree", "value": [1, 2, 5, 3, 4, None, 6]},
    },
    "124": {
        "slug": "binary-tree-maximum-path-sum",
        "method": "maxPathSum(root)",
        "text": "二叉树中的一条“路径”是沿着父子边连起来的一串结点，每个结点在路径上最多出现一次，路径至少包含一个结点，不要求经过根结点，也不要求从上往下。"
                "路径和是路径上所有结点值之和。给你根结点 root，返回所有路径中最大的路径和（结点值可能为负）。",
        "constraints": ["树中结点数在 [1, 3 × 10⁴] 范围内", "-1000 ≤ Node.val ≤ 1000"],
        "examples": [
            {"input": "root = [-10,9,20,null,null,15,7]", "output": "42", "note": "路径 15 → 20 → 7 的和为 42，加上根 -10 反而会变小。"},
            {"input": "root = [1,2,3]", "output": "6", "note": "路径 2 → 1 → 3 的和为 6。"},
        ],
        "figure": {"kind": "tree", "value": [-10, 9, 20, None, None, 15, 7]},
    },

    # ---------------- 回溯 ----------------
    "77": {
        "slug": "combinations",
        "method": "combine(n, k)",
        "text": "给定两个整数 n 和 k，从 1 到 n 这 n 个数中选出 k 个，返回所有可能的选法。"
                "每种选法只看选了哪些数、不看顺序（[1,2] 和 [2,1] 算同一种），结果的排列顺序不限。",
        "constraints": ["1 ≤ n ≤ 20", "1 ≤ k ≤ n"],
        "examples": [
            {"input": "n = 4, k = 2", "output": "[[1,2],[1,3],[1,4],[2,3],[2,4],[3,4]]", "note": "从 4 个数里选 2 个共 6 种。"},
            {"input": "n = 1, k = 1", "output": "[[1]]", "note": ""},
        ],
    },
    "17": {
        "slug": "letter-combinations-of-a-phone-number",
        "method": "letterCombinations(digits)",
        "text": "给定一个只包含数字 2~9 的字符串 digits，每个数字按手机九宫格键盘对应若干字母（2: abc，3: def，4: ghi，5: jkl，6: mno，7: pqrs，8: tuv，9: wxyz，1 不对应字母）。"
                "从每个数字对应的字母里各挑一个、按 digits 的顺序拼起来，返回所有能拼出的字符串，结果顺序不限。",
        "constraints": ["digits.length ≤ 4", "digits[i] 是 '2' 到 '9' 之间的数字"],
        "examples": [
            {"input": "digits = \"23\"", "output": "[\"ad\",\"ae\",\"af\",\"bd\",\"be\",\"bf\",\"cd\",\"ce\",\"cf\"]", "note": "2 有 3 个字母、3 有 3 个字母，共 9 种拼法。"},
            {"input": "digits = \"2\"", "output": "[\"a\",\"b\",\"c\"]", "note": ""},
        ],
    },
    "39": {
        "slug": "combination-sum",
        "method": "combinationSum(candidates, target)",
        "text": "给定一个元素互不相同的正整数数组 candidates 和目标值 target，找出所有和为 target 的组合。"
                "同一个数可以被选任意多次；只要某个数被选的次数不同就算不同组合，同一组数换个顺序算同一种。结果顺序不限。",
        "constraints": ["1 ≤ candidates.length ≤ 30", "2 ≤ candidates[i] ≤ 40，且互不相同", "1 ≤ target ≤ 40"],
        "examples": [
            {"input": "candidates = [2,3,6,7], target = 7", "output": "[[2,2,3],[7]]", "note": "2 + 2 + 3 = 7（2 用了两次），7 本身也等于 7。"},
            {"input": "candidates = [2,3,5], target = 8", "output": "[[2,2,2,2],[2,3,3],[3,5]]", "note": ""},
        ],
    },
    "46": {
        "slug": "permutations",
        "method": "permute(nums)",
        "text": "给定一个不含重复数字的整数数组 nums，返回它的所有全排列（把全部元素排成一行的所有不同顺序），结果顺序不限。",
        "constraints": ["1 ≤ nums.length ≤ 6", "-10 ≤ nums[i] ≤ 10", "nums 中的整数互不相同"],
        "examples": [
            {"input": "nums = [1,2,3]", "output": "[[1,2,3],[1,3,2],[2,1,3],[2,3,1],[3,1,2],[3,2,1]]", "note": "3 个不同的数共 3! = 6 种排列。"},
            {"input": "nums = [0,1]", "output": "[[0,1],[1,0]]", "note": ""},
        ],
    },
    "78": {
        "slug": "subsets",
        "method": "subsets(nums)",
        "text": "给定一个元素互不相同的整数数组 nums，返回它的所有子集（包括空集和它本身）。"
                "结果中不能有重复的子集，子集之间的顺序不限。",
        "constraints": ["1 ≤ nums.length ≤ 10", "-10 ≤ nums[i] ≤ 10", "nums 中的元素互不相同"],
        "examples": [
            {"input": "nums = [1,2,3]", "output": "[[],[1],[2],[1,2],[3],[1,3],[2,3],[1,2,3]]", "note": "3 个元素共 2³ = 8 个子集。"},
            {"input": "nums = [0]", "output": "[[],[0]]", "note": ""},
        ],
    },
    "22": {
        "slug": "generate-parentheses",
        "method": "generateParenthesis(n)",
        "text": "给定整数 n，表示有 n 对圆括号，返回由它们组成的所有有效括号字符串。"
                "有效指每个左括号都能和它后面的某个右括号一一配对、且任何前缀中右括号都不多于左括号。结果顺序不限。",
        "constraints": ["1 ≤ n ≤ 8"],
        "examples": [
            {"input": "n = 3", "output": "[\"((()))\",\"(()())\",\"(())()\",\"()(())\",\"()()()\"]", "note": "3 对括号共有 5 种有效组合。"},
            {"input": "n = 1", "output": "[\"()\"]", "note": ""},
        ],
    },
    "79": {
        "slug": "word-search",
        "method": "exist(board, word)",
        "text": "给定 m × n 的字符网格 board 和字符串 word，判断能否在网格中找到 word：从某个格子出发，每一步走到上下左右相邻的格子，依次经过的字母连起来恰好是 word。"
                "同一条路径中同一个格子不能使用两次。能找到返回 true，否则返回 false。",
        "constraints": ["m == board.length，n == board[i].length，1 ≤ m, n ≤ 6", "1 ≤ word.length ≤ 15", "board 和 word 只由大小写英文字母组成"],
        "examples": [
            {"input": "board = [[\"A\",\"B\",\"C\",\"E\"],[\"S\",\"F\",\"C\",\"S\"],[\"A\",\"D\",\"E\",\"E\"]], word = \"ABCCED\"", "output": "true",
             "note": "A(0,0) → B(0,1) → C(0,2) → C(1,2) → E(2,2) → D(2,1) 依次相邻。"},
            {"input": "board = [[\"A\",\"B\",\"C\",\"E\"],[\"S\",\"F\",\"C\",\"S\"],[\"A\",\"D\",\"E\",\"E\"]], word = \"ABCB\"", "output": "false",
             "note": "拼到 ABC 后，唯一相邻的 B 已经用过，不能再用。"},
        ],
        "figure": {"kind": "grid", "value": [["A", "B", "C", "E"], ["S", "F", "C", "S"], ["A", "D", "E", "E"]]},
    },

    # ---------------- 贪心 ----------------
    "455": {
        "slug": "assign-cookies",
        "method": "findContentChildren(g, s)",
        "text": "有一些孩子和一些饼干：g[i] 是第 i 个孩子的胃口值，s[j] 是第 j 块饼干的大小。"
                "孩子拿到一块大小不小于自己胃口的饼干就会满足；每个孩子最多分一块，每块饼干也只能给一个孩子。返回最多能让多少个孩子满足。",
        "constraints": ["1 ≤ g.length ≤ 3 × 10⁴，0 ≤ s.length ≤ 3 × 10⁴", "1 ≤ g[i], s[j] ≤ 2³¹ - 1"],
        "examples": [
            {"input": "g = [1,2,3], s = [1,1]", "output": "1", "note": "两块饼干都只有 1，只能满足胃口为 1 的孩子。"},
            {"input": "g = [1,2], s = [1,2,3]", "output": "2", "note": "饼干足够，两个孩子都能满足。"},
        ],
    },
    "122": {
        "slug": "best-time-to-buy-and-sell-stock-ii",
        "method": "maxProfit(prices)",
        "text": "prices[i] 是某支股票第 i 天的价格。每天都可以决定买入和/或卖出，但任何时候手里最多只能持有一股（可以同一天卖出后再买入）。"
                "可以进行任意多次交易，返回能获得的最大总利润。",
        "constraints": ["1 ≤ prices.length ≤ 3 × 10⁴", "0 ≤ prices[i] ≤ 10⁴"],
        "examples": [
            {"input": "prices = [7,1,5,3,6,4]", "output": "7", "note": "第 2 天 1 元买、第 3 天 5 元卖赚 4，第 4 天 3 元买、第 5 天 6 元卖赚 3，共 7。"},
            {"input": "prices = [7,6,4,3,1]", "output": "0", "note": "价格一路下跌，不交易利润最大。"},
        ],
    },
    "55": {
        "slug": "jump-game",
        "method": "canJump(nums)",
        "text": "给定非负整数数组 nums，你一开始站在下标 0。nums[i] 表示站在下标 i 时一次最多能向后跳多少格（可以跳得更少）。"
                "判断能否到达最后一个下标，能则返回 true，否则返回 false。",
        "constraints": ["1 ≤ nums.length ≤ 10⁴", "0 ≤ nums[i] ≤ 10⁵"],
        "examples": [
            {"input": "nums = [2,3,1,1,4]", "output": "true", "note": "从下标 0 跳 1 格到下标 1，再跳 3 格到最后。"},
            {"input": "nums = [3,2,1,0,4]", "output": "false", "note": "不管怎么跳都会停在下标 3，而那里的最大跳跃长度是 0。"},
        ],
    },
    "45": {
        "slug": "jump-game-ii",
        "method": "jump(nums)",
        "text": "给定整数数组 nums，你一开始站在下标 0，nums[i] 表示从下标 i 一次最多能向后跳多少格。"
                "题目保证一定能到达最后一个下标，返回到达最后一个下标所需的最少跳跃次数。",
        "constraints": ["1 ≤ nums.length ≤ 10⁴", "0 ≤ nums[i] ≤ 1000", "保证可以到达 nums[n - 1]"],
        "examples": [
            {"input": "nums = [2,3,1,1,4]", "output": "2", "note": "下标 0 跳到下标 1，再从下标 1 跳 3 格到最后，共 2 次。"},
            {"input": "nums = [2,3,0,1,4]", "output": "2", "note": ""},
        ],
    },
    "53": {
        "slug": "maximum-subarray",
        "method": "maxSubArray(nums)",
        "text": "给定整数数组 nums，在所有非空的连续子数组中，找出元素和最大的那个，返回这个最大和。"
                "数组中可能有负数，子数组至少包含一个元素。",
        "constraints": ["1 ≤ nums.length ≤ 10⁵", "-10⁴ ≤ nums[i] ≤ 10⁴"],
        "examples": [
            {"input": "nums = [-2,1,-3,4,-1,2,1,-5,4]", "output": "6", "note": "连续子数组 [4,-1,2,1] 的和为 6，是最大的。"},
            {"input": "nums = [5,4,-1,7,8]", "output": "23", "note": "整个数组的和 23 最大。"},
        ],
    },
    "763": {
        "slug": "partition-labels",
        "method": "partitionLabels(s)",
        "text": "给定只含小写字母的字符串 s，把它切成尽可能多的连续片段，要求每个字母只出现在其中一个片段里。"
                "所有片段按原顺序拼回去仍是 s，返回各片段长度组成的列表（按从左到右的顺序）。",
        "constraints": ["1 ≤ s.length ≤ 500", "s 仅由小写英文字母组成"],
        "examples": [
            {"input": "s = \"ababcbacadefegdehijhklij\"", "output": "[9,7,8]", "note": "切成 \"ababcbaca\"、\"defegde\"、\"hijhklij\"，每个字母只在一段里出现。"},
            {"input": "s = \"eccbbbbdec\"", "output": "[10]", "note": "首尾都有 e、c，无法再切开。"},
        ],
    },

    # ---------------- 动态规划 ----------------
    "70": {
        "slug": "climbing-stairs",
        "method": "climbStairs(n)",
        "text": "楼梯一共有 n 阶，每一步可以爬 1 阶或 2 阶。"
                "从地面出发恰好爬到第 n 阶，一共有多少种不同的走法？（步子的先后顺序不同算不同走法）",
        "constraints": ["1 ≤ n ≤ 45"],
        "examples": [
            {"input": "n = 2", "output": "2", "note": "1+1 或 2。"},
            {"input": "n = 3", "output": "3", "note": "1+1+1、1+2、2+1。"},
        ],
    },
    "746": {
        "slug": "min-cost-climbing-stairs",
        "method": "minCostClimbingStairs(cost)",
        "text": "cost[i] 是踩上第 i 级台阶要付的费用，付完后可以往上爬 1 级或 2 级。"
                "你可以从下标 0 或下标 1 的台阶开始，目标是越过最后一级到达楼顶（下标 n 的位置），返回所需的最低总费用。",
        "constraints": ["2 ≤ cost.length ≤ 1000", "0 ≤ cost[i] ≤ 999"],
        "examples": [
            {"input": "cost = [10,15,20]", "output": "15", "note": "从下标 1 开始付 15，直接爬 2 级到楼顶。"},
            {"input": "cost = [1,100,1,1,1,100,1,1,100,1]", "output": "6", "note": "依次踩下标 0,2,4,6,7,9，每级付 1，共 6。"},
        ],
    },
    "121": {
        "slug": "best-time-to-buy-and-sell-stock",
        "method": "maxProfit(prices)",
        "text": "prices[i] 是某支股票第 i 天的价格。你只能选一天买入这支股票，并在之后的另一天卖出（只做一次交易）。"
                "返回能获得的最大利润；如果怎样都赚不到钱，返回 0。",
        "constraints": ["1 ≤ prices.length ≤ 10⁵", "0 ≤ prices[i] ≤ 10⁴"],
        "examples": [
            {"input": "prices = [7,1,5,3,6,4]", "output": "5", "note": "第 2 天以 1 买入、第 5 天以 6 卖出，赚 5；不能先卖后买。"},
            {"input": "prices = [7,6,4,3,1]", "output": "0", "note": "价格一路下跌，不交易。"},
        ],
    },
    "198": {
        "slug": "house-robber",
        "method": "rob(nums)",
        "text": "一排房屋里各存有一定金额的现金，nums[i] 是第 i 间房的金额。"
                "如果同一晚偷了两间相邻的房屋就会触发报警，求在不触发报警的前提下一晚最多能偷到的总金额。",
        "constraints": ["1 ≤ nums.length ≤ 100", "0 ≤ nums[i] ≤ 400"],
        "examples": [
            {"input": "nums = [1,2,3,1]", "output": "4", "note": "偷第 1 间和第 3 间，1 + 3 = 4。"},
            {"input": "nums = [2,7,9,3,1]", "output": "12", "note": "偷第 1、3、5 间，2 + 9 + 1 = 12。"},
        ],
    },
    "62": {
        "slug": "unique-paths",
        "method": "uniquePaths(m, n)",
        "text": "一个机器人站在 m 行 n 列网格的左上角，每次只能向右或向下走一格。"
                "它要走到网格的右下角，问一共有多少条不同的路径。",
        "constraints": ["1 ≤ m, n ≤ 100", "答案保证不超过 2 × 10⁹"],
        "examples": [
            {"input": "m = 3, n = 7", "output": "28", "note": ""},
            {"input": "m = 3, n = 2", "output": "3", "note": "右→下→下、下→下→右、下→右→下。"},
        ],
    },
    "322": {
        "slug": "coin-change",
        "method": "coinChange(coins, amount)",
        "text": "coins 是若干种不同面额的硬币，每种都有无限多枚；amount 是要凑出的总金额。"
                "返回恰好凑出 amount 所需的最少硬币数；如果无论怎样都凑不出，返回 -1。amount 为 0 时答案是 0。",
        "constraints": ["1 ≤ coins.length ≤ 12", "1 ≤ coins[i] ≤ 2³¹ - 1", "0 ≤ amount ≤ 10⁴"],
        "examples": [
            {"input": "coins = [1,2,5], amount = 11", "output": "3", "note": "11 = 5 + 5 + 1。"},
            {"input": "coins = [2], amount = 3", "output": "-1", "note": "只有 2 元硬币，凑不出奇数金额。"},
        ],
    },
    "300": {
        "slug": "longest-increasing-subsequence",
        "method": "lengthOfLIS(nums)",
        "text": "给定整数数组 nums，返回其中最长的严格递增子序列的长度。"
                "子序列是从数组中删掉若干元素（也可以不删）、剩下元素保持原有先后顺序得到的序列，不要求连续。进阶：能否做到 O(n log n) 时间。",
        "constraints": ["1 ≤ nums.length ≤ 2500", "-10⁴ ≤ nums[i] ≤ 10⁴"],
        "examples": [
            {"input": "nums = [10,9,2,5,3,7,101,18]", "output": "4", "note": "例如 [2,3,7,101] 或 [2,5,7,18]，长度都是 4。"},
            {"input": "nums = [7,7,7,7,7,7,7]", "output": "1", "note": "相等不算递增，只能取一个数。"},
        ],
    },
    "1143": {
        "slug": "longest-common-subsequence",
        "method": "longestCommonSubsequence(text1, text2)",
        "text": "给定两个字符串 text1 和 text2，返回它们最长公共子序列的长度；没有公共子序列时返回 0。"
                "子序列是删掉原字符串中若干字符（也可以不删）、其余字符保持相对顺序得到的新串，不要求连续；公共子序列指同时是两个字符串的子序列。",
        "constraints": ["1 ≤ text1.length, text2.length ≤ 1000", "text1 和 text2 仅由小写英文字母组成"],
        "examples": [
            {"input": "text1 = \"abcde\", text2 = \"ace\"", "output": "3", "note": "最长公共子序列是 \"ace\"。"},
            {"input": "text1 = \"abc\", text2 = \"def\"", "output": "0", "note": "两个字符串没有相同字符。"},
        ],
    },
    "416": {
        "slug": "partition-equal-subset-sum",
        "method": "canPartition(nums)",
        "text": "给定一个只含正整数的非空数组 nums，判断能否把它的元素分成两组（每个元素恰好属于一组），使两组的元素和相等。"
                "能分返回 true，否则返回 false。",
        "constraints": ["1 ≤ nums.length ≤ 200", "1 ≤ nums[i] ≤ 100"],
        "examples": [
            {"input": "nums = [1,5,11,5]", "output": "true", "note": "分成 [1,5,5] 和 [11]，和都是 11。"},
            {"input": "nums = [1,2,3,5]", "output": "false", "note": "总和 11 是奇数，不可能平分。"},
        ],
    },

    # ---------------- 二分查找 ----------------
    "704": {
        "slug": "binary-search",
        "method": "search(nums, target)",
        "text": "给定一个按升序排列、元素互不相同的整数数组 nums 和目标值 target，如果 target 在数组中就返回它的下标，否则返回 -1。"
                "要求时间复杂度为 O(log n)。",
        "constraints": ["1 ≤ nums.length ≤ 10⁴", "-10⁴ < nums[i], target < 10⁴", "nums 中元素互不相同且升序排列"],
        "examples": [
            {"input": "nums = [-1,0,3,5,9,12], target = 9", "output": "4", "note": "9 位于下标 4。"},
            {"input": "nums = [-1,0,3,5,9,12], target = 2", "output": "-1", "note": "数组中没有 2。"},
        ],
    },
    "35": {
        "slug": "search-insert-position",
        "method": "searchInsert(nums, target)",
        "text": "给定一个升序排列、元素互不相同的整数数组 nums 和目标值 target。"
                "如果 target 在数组中，返回它的下标；如果不在，返回把它插入后仍保持有序时它应处的下标。要求时间复杂度为 O(log n)。",
        "constraints": ["1 ≤ nums.length ≤ 10⁴", "-10⁴ ≤ nums[i], target ≤ 10⁴", "nums 中元素互不相同且升序排列"],
        "examples": [
            {"input": "nums = [1,3,5,6], target = 5", "output": "2", "note": "5 就在下标 2。"},
            {"input": "nums = [1,3,5,6], target = 2", "output": "1", "note": "2 应插在 1 和 3 之间，即下标 1。"},
        ],
    },
    "34": {
        "slug": "find-first-and-last-position-of-element-in-sorted-array",
        "method": "searchRange(nums, target)",
        "text": "给定一个按非递减顺序排列的整数数组 nums（可能有重复）和目标值 target，返回 target 在数组中第一次和最后一次出现的下标 [start, end]。"
                "如果 target 不在数组中，返回 [-1, -1]。要求时间复杂度为 O(log n)。",
        "constraints": ["0 ≤ nums.length ≤ 10⁵", "-10⁹ ≤ nums[i], target ≤ 10⁹", "nums 是非递减数组"],
        "examples": [
            {"input": "nums = [5,7,7,8,8,10], target = 8", "output": "[3,4]", "note": "8 出现在下标 3 和 4。"},
            {"input": "nums = [5,7,7,8,8,10], target = 6", "output": "[-1,-1]", "note": "数组中没有 6。"},
        ],
    },
    "153": {
        "slug": "find-minimum-in-rotated-sorted-array",
        "method": "findMin(nums)",
        "text": "一个元素互不相同的升序数组被“旋转”了若干次：每旋转一次，就把最后一个元素移到最前面（例如 [0,1,2,4,5,6,7] 旋转 4 次得到 [4,5,6,7,0,1,2]）。"
                "给你旋转后的数组 nums，返回其中的最小元素。要求时间复杂度为 O(log n)。",
        "constraints": ["1 ≤ nums.length ≤ 5000", "-5000 ≤ nums[i] ≤ 5000", "nums 中元素互不相同，原数组升序且旋转了 1 到 n 次"],
        "examples": [
            {"input": "nums = [3,4,5,1,2]", "output": "1", "note": "原数组 [1,2,3,4,5] 旋转 3 次得到它。"},
            {"input": "nums = [11,13,15,17]", "output": "11", "note": "旋转了 n 次，数组和原来一样。"},
        ],
    },
    "33": {
        "slug": "search-in-rotated-sorted-array",
        "method": "search(nums, target)",
        "text": "一个元素互不相同的升序数组在某个未知位置被切开，后半段整体挪到了前面（例如 [0,1,2,4,5,6,7] 变成 [4,5,6,7,0,1,2]，也可能没切）。"
                "给你这样的数组 nums 和目标值 target，返回 target 的下标，不存在则返回 -1。要求时间复杂度为 O(log n)。",
        "constraints": ["1 ≤ nums.length ≤ 5000", "-10⁴ ≤ nums[i], target ≤ 10⁴", "nums 中元素互不相同"],
        "examples": [
            {"input": "nums = [4,5,6,7,0,1,2], target = 0", "output": "4", "note": "0 位于下标 4。"},
            {"input": "nums = [4,5,6,7,0,1,2], target = 3", "output": "-1", "note": "数组中没有 3。"},
        ],
    },
    "74": {
        "slug": "search-a-2d-matrix",
        "method": "searchMatrix(matrix, target)",
        "text": "给定 m × n 的整数矩阵 matrix：每一行从左到右非递减，并且每一行的第一个数都大于上一行的最后一个数。"
                "判断 target 是否在矩阵中，在返回 true，否则返回 false。要求时间复杂度为 O(log(m × n))。",
        "constraints": ["m == matrix.length，n == matrix[i].length，1 ≤ m, n ≤ 100", "-10⁴ ≤ matrix[i][j], target ≤ 10⁴"],
        "examples": [
            {"input": "matrix = [[1,3,5,7],[10,11,16,20],[23,30,34,60]], target = 3", "output": "true", "note": "3 在第 0 行。"},
            {"input": "matrix = [[1,3,5,7],[10,11,16,20],[23,30,34,60]], target = 13", "output": "false", "note": "矩阵中没有 13。"},
        ],
        "figure": {"kind": "grid", "value": [[1, 3, 5, 7], [10, 11, 16, 20], [23, 30, 34, 60]]},
    },

    # ---------------- 图论 ----------------
    "733": {
        "slug": "flood-fill",
        "method": "floodFill(image, sr, sc, color)",
        "text": "image 是一张 m × n 的图片，image[i][j] 是像素值。从起点像素 (sr, sc) 出发，把它以及所有能通过上下左右相邻、且与起点原颜色相同的像素连成一片的像素，全部改成 color。"
                "返回修改后的图片。",
        "constraints": ["m == image.length，n == image[i].length，1 ≤ m, n ≤ 50", "0 ≤ image[i][j], color < 2¹⁶", "0 ≤ sr < m，0 ≤ sc < n"],
        "examples": [
            {"input": "image = [[1,1,1],[1,1,0],[1,0,1]], sr = 1, sc = 1, color = 2", "output": "[[2,2,2],[2,2,0],[2,0,1]]",
             "note": "右下角的 1 只和起点斜向相连，不算相邻，所以不变。"},
            {"input": "image = [[0,0,0],[0,0,0]], sr = 0, sc = 0, color = 0", "output": "[[0,0,0],[0,0,0]]", "note": "新颜色和原颜色相同，图片不变。"},
        ],
        "figure": {"kind": "grid", "value": [[1, 1, 1], [1, 1, 0], [1, 0, 1]]},
    },
    "200": {
        "slug": "number-of-islands",
        "method": "numIslands(grid)",
        "text": "grid 是一个 m × n 的二维网格，每个格子是字符 '1'（陆地）或 '0'（水）。上下左右相邻的陆地连成一座岛屿，网格外围都视为水。"
                "返回网格中岛屿的数量。",
        "constraints": ["m == grid.length，n == grid[i].length，1 ≤ m, n ≤ 300", "grid[i][j] 为 '0' 或 '1'"],
        "examples": [
            {"input": "grid = [[\"1\",\"1\",\"0\",\"0\",\"0\"],[\"1\",\"1\",\"0\",\"0\",\"0\"],[\"0\",\"0\",\"1\",\"0\",\"0\"],[\"0\",\"0\",\"0\",\"1\",\"1\"]]",
             "output": "3", "note": "左上角 2×2 一块、中间单独一格、右下角两格各成一座岛；斜着挨着不算相连。"},
            {"input": "grid = [[\"1\",\"1\",\"1\",\"1\",\"0\"],[\"1\",\"1\",\"0\",\"1\",\"0\"],[\"1\",\"1\",\"0\",\"0\",\"0\"],[\"0\",\"0\",\"0\",\"0\",\"0\"]]",
             "output": "1", "note": "所有陆地连成一片。"},
        ],
        "figure": {"kind": "grid", "value": [["1", "1", "0", "0", "0"], ["1", "1", "0", "0", "0"], ["0", "0", "1", "0", "0"], ["0", "0", "0", "1", "1"]]},
    },
    "695": {
        "slug": "max-area-of-island",
        "method": "maxAreaOfIsland(grid)",
        "text": "grid 是一个由 0 和 1 组成的 m × n 网格，1 表示陆地。上下左右相邻的 1 连成一座岛屿，岛屿面积是它包含的格子数。"
                "返回所有岛屿中的最大面积；没有岛屿时返回 0。",
        "constraints": ["m == grid.length，n == grid[i].length，1 ≤ m, n ≤ 50", "grid[i][j] 为 0 或 1"],
        "examples": [
            {"input": "grid = [[0,0,1,0,0],[1,1,1,0,0],[0,0,0,1,1],[0,1,0,1,0]]", "output": "4",
             "note": "左上方那座岛有 4 格，右下方那座有 3 格，左下角单独 1 格。"},
            {"input": "grid = [[0,0,0,0,0,0,0,0]]", "output": "0", "note": "没有陆地。"},
        ],
        "figure": {"kind": "grid", "value": [[0, 0, 1, 0, 0], [1, 1, 1, 0, 0], [0, 0, 0, 1, 1], [0, 1, 0, 1, 0]]},
    },
    "994": {
        "slug": "rotting-oranges",
        "method": "orangesRotting(grid)",
        "text": "m × n 网格中每格的值：0 表示空格，1 表示新鲜橘子，2 表示腐烂的橘子。"
                "每过一分钟，与腐烂橘子上下左右相邻的新鲜橘子都会变腐烂。返回直到没有新鲜橘子为止所需的最少分钟数；如果有橘子永远不会腐烂，返回 -1。",
        "constraints": ["m == grid.length，n == grid[i].length，1 ≤ m, n ≤ 10", "grid[i][j] 为 0、1 或 2"],
        "examples": [
            {"input": "grid = [[2,1,1],[1,1,0],[0,1,1]]", "output": "4", "note": "右下角的橘子离左上角的烂橘子最远，第 4 分钟才腐烂。"},
            {"input": "grid = [[2,1,1],[0,1,1],[1,0,1]]", "output": "-1", "note": "左下角的橘子四周没有能传过来的橘子，永远不会腐烂。"},
        ],
        "figure": {"kind": "grid", "value": [[2, 1, 1], [1, 1, 0], [0, 1, 1]]},
    },
    "207": {
        "slug": "course-schedule",
        "method": "canFinish(numCourses, prerequisites)",
        "text": "共有 numCourses 门课，编号 0 到 numCourses - 1。prerequisites[i] = [a, b] 表示想学课程 a 必须先学完课程 b。"
                "判断能否按某种顺序学完所有课程，能返回 true，否则返回 false。",
        "constraints": ["1 ≤ numCourses ≤ 2000", "0 ≤ prerequisites.length ≤ 5000", "0 ≤ a, b < numCourses，且所有 [a, b] 互不相同"],
        "examples": [
            {"input": "numCourses = 2, prerequisites = [[1,0]]", "output": "true", "note": "先学 0 再学 1。"},
            {"input": "numCourses = 2, prerequisites = [[1,0],[0,1]]", "output": "false", "note": "学 1 要先学 0，学 0 又要先学 1，互相卡住。"},
        ],
    },
    "547": {
        "slug": "number-of-provinces",
        "method": "findCircleNum(isConnected)",
        "text": "有 n 个城市，isConnected 是 n × n 矩阵：isConnected[i][j] = 1 表示城市 i 和城市 j 直接相连，0 表示不直接相连。"
                "直接或间接相连的城市属于同一个省份（相连关系可以传递）。返回省份的数量。",
        "constraints": ["1 ≤ n ≤ 200，isConnected 为 n × n 矩阵", "isConnected[i][j] 为 0 或 1，isConnected[i][i] == 1", "isConnected[i][j] == isConnected[j][i]"],
        "examples": [
            {"input": "isConnected = [[1,1,0],[1,1,0],[0,0,1]]", "output": "2", "note": "城市 0 和 1 相连成一个省，城市 2 自成一个省。"},
            {"input": "isConnected = [[1,0,0],[0,1,0],[0,0,1]]", "output": "3", "note": "三个城市互不相连。"},
        ],
    },
}
