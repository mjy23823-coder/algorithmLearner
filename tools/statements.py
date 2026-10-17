# -*- coding: utf-8 -*-
"""题面：用自己的话改写的完整题意、约束和力扣链接。完整原题以力扣为准。

有本地用例的题，示例直接取 problem_bank 里的基础用例（这里只补说明）；
没有本地用例的推荐题，示例写在 statements_extra 里。题意只说明要做什么，不写解法。
"""
import json

try:
    from .statements_extra import EXTRA
except ImportError:
    try:
        from statements_extra import EXTRA
    except ImportError:
        EXTRA = {}


def st(slug, text, constraints, notes=None, figure=None):
    return {"slug": slug, "text": text, "constraints": constraints, "notes": notes or {}, "figure": figure}


STATEMENTS = {
    "1": st("two-sum", "给你一个整数数组 nums 和一个目标值 target。请找出数组里和为 target 的两个数，返回它们的下标。同一个位置的元素不能用两次；每组输入恰好只有一个答案，下标顺序不限。",
            ["2 ≤ nums.length ≤ 10⁴", "-10⁹ ≤ nums[i], target ≤ 10⁹", "只存在一个有效答案"], {0: "nums[0] + nums[1] = 2 + 7 = 9，所以返回 [0,1]。"}),
    "3": st("longest-substring-without-repeating-characters", "给定一个字符串 s，在它的所有连续子串中，找出不包含重复字符的那些，返回其中最长的长度。注意是连续的子串，不是可以跳着选的子序列。",
            ["0 ≤ s.length ≤ 5×10⁴", "s 由英文字母、数字、符号和空格组成"], {0: "最长的无重复子串是 \"abc\"，长度 3。", 3: "\"ab\" 或 \"ba\" 都不重复，\"abb\"、\"bba\" 都含重复字符。"}),
    "11": st("container-with-most-water", "数组 height 的第 i 个数表示在横坐标 i 处立着一根高 height[i] 的竖线。任选两根竖线，和 x 轴一起围成一个容器，容器能装的水 = 两线距离 × 较短那根的高度。返回能装水的最大值。容器不能倾斜。",
             ["n == height.length，2 ≤ n ≤ 10⁵", "0 ≤ height[i] ≤ 10⁴"], {0: "选下标 1（高 8）和下标 8（高 7）：宽 7，水面高 7，面积 49。"}, figure="bars"),
    "15": st("3sum", "给定整数数组 nums，找出所有三个不同下标的元素之和为 0 的组合 [nums[i], nums[j], nums[k]]。答案里不能有重复的三元组（数值相同算重复），三元组内部和整体的顺序都不限。",
             ["3 ≤ nums.length ≤ 3000", "-10⁵ ≤ nums[i] ≤ 10⁵"], {0: "和为 0 的组合只有 (-1,0,1) 和 (-1,-1,2) 两种；数组里有两个 -1，但 (-1,0,1) 只算一次。"}),
    "16": st("3sum-closest", "给定整数数组 nums 和目标值 target，从数组中选出三个不同下标的数，使它们的和与 target 的差的绝对值最小，返回这个和。假设每组输入只有一个最接近的和。",
             ["3 ≤ nums.length ≤ 500", "-1000 ≤ nums[i] ≤ 1000", "-10⁴ ≤ target ≤ 10⁴"], {0: "-1 + 2 + 1 = 2，与 1 相差 1，是所有选法中最接近的。"}),
    "20": st("valid-parentheses", "字符串 s 只包含 '(' ')' '[' ']' '{' '}' 六种字符。判断它是否有效：每个左括号都必须由同类型的右括号闭合，并且闭合顺序要正确（后打开的先关闭），每个右括号也都要有对应的左括号。",
             ["1 ≤ s.length ≤ 10⁴", "s 只由 '()[]{}' 组成"], {1: "括号数量都配对，但 '[' 还没关闭就先遇到了 ')'，顺序错误。"}),
    "26": st("remove-duplicates-from-sorted-array", "nums 按非递减顺序排列。请原地删除重复出现的元素，使每个值只保留一次，并保持原来的相对顺序，然后返回剩下元素的个数 k。判题只检查 nums 的前 k 个位置，k 之后放什么都可以。不要另开数组。",
             ["1 ≤ nums.length ≤ 3×10⁴", "-100 ≤ nums[i] ≤ 100", "nums 已按非递减顺序排列"], {0: "去重后前两个位置是 1、2，返回 k = 2。"}),
    "27": st("remove-element", "给你数组 nums 和一个值 val，原地移除所有等于 val 的元素，返回剩余元素个数 k。判题只看 nums 的前 k 个位置，它们的顺序可以改变，k 之后的内容不重要。不要另开数组。",
             ["0 ≤ nums.length ≤ 100", "0 ≤ nums[i] ≤ 50", "0 ≤ val ≤ 100"], {0: "移除两个 3 后剩下两个 2，返回 k = 2。"}),
    "42": st("trapping-rain-water", "给定 n 个非负整数，表示一排宽度都为 1 的柱子的高度。下雨后，柱子之间低洼的地方会积水。计算这排柱子一共能接住多少单位的雨水。",
             ["n == height.length，1 ≤ n ≤ 2×10⁴", "0 ≤ height[i] ≤ 10⁵"], {0: "图中蓝色为积水：下标 2、4、6、9 各 1 格，下标 5 有 2 格，合计 6。"}, figure="bars"),
    "94": st("binary-tree-inorder-traversal", "给定二叉树的根节点 root，按中序（左子树 → 根 → 右子树）顺序访问所有节点，返回节点值组成的列表。",
             ["节点数在 [0, 100] 内", "-100 ≤ Node.val ≤ 100"], {0: "1 没有左孩子，右孩子是 2，3 是 2 的左孩子，所以顺序是 1、3、2。"}),
    "98": st("validate-binary-search-tree", "给定二叉树的根节点 root，判断它是不是一棵有效的二叉搜索树：每个节点左子树里的所有值都严格小于它，右子树里的所有值都严格大于它，并且左右子树本身也都满足这个要求。",
             ["节点数在 [1, 10⁴] 内", "-2³¹ ≤ Node.val ≤ 2³¹ - 1"], {1: "根是 5，但右子树里有 3，3 < 5，不满足要求。", 2: "值必须严格大小，相等也不行。"}),
    "100": st("same-tree", "给你两棵二叉树的根节点 p 和 q，判断这两棵树是否相同：结构完全一样，并且对应位置的节点值也相等。",
              ["两棵树的节点数都在 [0, 100] 内", "-10⁴ ≤ Node.val ≤ 10⁴"], {1: "两棵树都有值 1、2，但 2 一个在左边、一个在右边，结构不同。"}),
    "101": st("symmetric-tree", "给定二叉树的根节点 root，判断这棵树是否以根为轴左右镜像对称，即把整棵树左右翻转后和原来一模一样。",
              ["节点数在 [1, 1000] 内", "-100 ≤ Node.val ≤ 100"], {1: "两个 3 都挂在各自父节点的右边，翻转后应该一左一右，所以不对称。"}),
    "102": st("binary-tree-level-order-traversal", "给定二叉树的根节点 root，从上到下逐层、每层从左到右访问节点，把每一层的节点值单独放进一个列表，返回这些列表组成的列表。",
              ["节点数在 [0, 2000] 内", "-1000 ≤ Node.val ≤ 1000"], {0: "第 1 层是 3，第 2 层是 9、20，第 3 层是 15、7。"}),
    "104": st("maximum-depth-of-binary-tree", "给定二叉树的根节点 root，返回它的最大深度，即从根节点到最远叶子节点的路径上一共有多少个节点。空树深度为 0。",
              ["节点数在 [0, 10⁴] 内", "-100 ≤ Node.val ≤ 100"], {0: "最长路径是 3 → 20 → 15（或 3 → 20 → 7），共 3 个节点。"}),
    "108": st("convert-sorted-array-to-binary-search-tree", "给你一个严格递增的整数数组 nums，用它的全部元素构造一棵高度平衡的二叉搜索树并返回根节点。高度平衡指每个节点的左右子树高度差不超过 1。满足条件的树可能有多棵，返回任意一棵即可。",
              ["1 ≤ nums.length ≤ 10⁴", "-10⁴ ≤ nums[i] ≤ 10⁴", "nums 严格递增"], {0: "[0,-3,9,-10,null,5] 和 [0,-10,5,null,-3,null,9] 都是正确答案。"}),
    "110": st("balanced-binary-tree", "给定一棵二叉树，判断它是否高度平衡：树中每一个节点的左右两棵子树高度相差都不超过 1。空树算平衡。",
              ["节点数在 [0, 5000] 内", "-10⁴ ≤ Node.val ≤ 10⁴"], {1: "根节点左边深 3 层、右边只有 1 层，相差 2。"}),
    "112": st("path-sum", "给你二叉树的根节点 root 和整数 targetSum，判断树中是否存在一条从根节点走到某个叶子节点的路径，路径上所有节点值相加正好等于 targetSum。叶子节点是没有孩子的节点。",
              ["节点数在 [0, 5000] 内", "-1000 ≤ Node.val ≤ 1000", "-1000 ≤ targetSum ≤ 1000"], {0: "路径 5 → 4 → 11 → 2 的和是 22。", 2: "空树里没有任何路径。"}),
    "144": st("binary-tree-preorder-traversal", "给定二叉树的根节点 root，按前序（根 → 左子树 → 右子树）顺序访问所有节点，返回节点值组成的列表。",
              ["节点数在 [0, 100] 内", "-100 ≤ Node.val ≤ 100"]),
    "145": st("binary-tree-postorder-traversal", "给定二叉树的根节点 root，按后序（左子树 → 右子树 → 根）顺序访问所有节点，返回节点值组成的列表。",
              ["节点数在 [0, 100] 内", "-100 ≤ Node.val ≤ 100"]),
    "167": st("two-sum-ii-input-array-is-sorted", "numbers 按非递减顺序排列。找出其中和为 target 的两个数，返回它们的位置 [index1, index2]，位置从 1 开始数，且 index1 < index2。同一个元素不能用两次；每组输入恰好有一个答案。要求只使用常量级的额外空间。",
              ["2 ≤ numbers.length ≤ 3×10⁴", "-1000 ≤ numbers[i] ≤ 1000", "numbers 非递减，只有一个有效答案"], {0: "2 + 7 = 9，它们是第 1 个和第 2 个数，返回 [1,2]。"}),
    "203": st("remove-linked-list-elements", "给你链表的头节点 head 和一个整数 val，删除链表中所有值等于 val 的节点，返回新的头节点。头节点本身也可能要删除。",
              ["节点数在 [0, 10⁴] 内", "1 ≤ Node.val ≤ 50", "0 ≤ val ≤ 50"]),
    "206": st("reverse-linked-list", "给你单链表的头节点 head，把整条链表反转（每个节点的指向都调转方向），返回反转后链表的头节点。",
              ["节点数在 [0, 5000] 内", "-5000 ≤ Node.val ≤ 5000"]),
    "209": st("minimum-size-subarray-sum", "给定一个正整数数组 nums 和一个正整数 target，找出和大于等于 target 的最短连续子数组，返回它的长度。如果不存在这样的子数组，返回 0。",
              ["1 ≤ target ≤ 10⁹", "1 ≤ nums.length ≤ 10⁵", "1 ≤ nums[i] ≤ 10⁴"], {0: "子数组 [4,3] 的和是 7，长度 2，没有更短的。", 2: "全部加起来也只有 4，达不到 11。"}),
    "217": st("contains-duplicate", "给你一个整数数组 nums，如果有任何一个值出现了至少两次，返回 true；如果所有元素都互不相同，返回 false。",
              ["1 ≤ nums.length ≤ 10⁵", "-10⁹ ≤ nums[i] ≤ 10⁹"]),
    "226": st("invert-binary-tree", "给你一棵二叉树的根节点 root，把它左右翻转（对每个节点交换它的左右孩子），返回翻转后的根节点。",
              ["节点数在 [0, 100] 内", "-100 ≤ Node.val ≤ 100"]),
    "230": st("kth-smallest-element-in-a-bst", "给定一棵二叉搜索树的根节点 root 和整数 k，返回树中第 k 小的值，k 从 1 开始计数。",
              ["树中节点数为 n，1 ≤ k ≤ n ≤ 10⁴", "0 ≤ Node.val ≤ 10⁴"], {1: "树中的值从小到大是 1、2、3、4、5、6，第 3 小是 3。"}),
    "235": st("lowest-common-ancestor-of-a-binary-search-tree", "给定一棵二叉搜索树和树中两个不同的节点 p、q，找出它们的最近公共祖先：一个节点同时是 p 和 q 的祖先，并且在满足条件的节点里离它们最近（深度最大）。一个节点也可以是它自己的祖先。",
              ["节点数在 [2, 10⁵] 内", "所有节点值互不相同", "p ≠ q，且都在树中"], {1: "2 本身就是 4 的祖先，节点可以是自己的祖先，所以答案是 2。"}),
    "236": st("lowest-common-ancestor-of-a-binary-tree", "给定一棵普通二叉树（不是搜索树）和树中两个不同的节点 p、q，找出它们的最近公共祖先：一个节点同时是 p 和 q 的祖先，并且在满足条件的节点里深度最大。一个节点也可以是它自己的祖先。",
              ["节点数在 [2, 10⁵] 内", "-10⁹ ≤ Node.val ≤ 10⁹，值互不相同", "p ≠ q，且都在树中"], {0: "5 在左子树、1 在右子树，最近的共同祖先是根 3。", 1: "4 在 5 的子树里，5 是自己的祖先，所以答案是 5。"}),
    "242": st("valid-anagram", "给定两个字符串 s 和 t，判断 t 是否是 s 的字母异位词：两个字符串用到的字符完全一样，每个字符出现的次数也相同，只是排列顺序可以不同。",
              ["1 ≤ s.length, t.length ≤ 5×10⁴", "s 和 t 只包含小写字母"]),
    "257": st("binary-tree-paths", "给你二叉树的根节点 root，返回所有从根节点到叶子节点的路径。每条路径写成字符串，节点值之间用 \"->\" 连接。路径的先后顺序不限。",
              ["节点数在 [1, 100] 内", "-100 ≤ Node.val ≤ 100"]),
    "283": st("move-zeroes", "给定数组 nums，把所有 0 移到数组末尾，同时保持非零元素原来的相对顺序。必须原地修改 nums，不能复制出新数组；函数不需要返回值。",
              ["1 ≤ nums.length ≤ 10⁴", "-2³¹ ≤ nums[i] ≤ 2³¹ - 1"]),
    "344": st("reverse-string", "字符串以字符列表 s 的形式给出，请把它原地反转。必须直接修改输入的列表，只能使用 O(1) 的额外空间；函数不需要返回值。",
              ["1 ≤ s.length ≤ 10⁵", "s[i] 都是 ASCII 可打印字符"]),
    "404": st("sum-of-left-leaves", "给定二叉树的根节点 root，返回所有左叶子的值之和。左叶子是指：它是某个节点的左孩子，并且它自己没有孩子。",
              ["节点数在 [1, 1000] 内", "-1000 ≤ Node.val ≤ 1000"], {0: "左叶子有 9 和 15，和为 24；7 是右叶子，不算。"}),
    "438": st("find-all-anagrams-in-a-string", "给定字符串 s 和 p，在 s 中找出所有和 p 互为字母异位词的子串（长度和 p 相同，字符及次数也完全相同），返回这些子串的起始下标。下标顺序不限。",
              ["1 ≤ s.length, p.length ≤ 3×10⁴", "s 和 p 只包含小写字母"], {0: "下标 0 开始的 \"cba\" 和下标 6 开始的 \"bac\" 都是 \"abc\" 的异位词。"}),
    "450": st("delete-node-in-a-bst", "给定二叉搜索树的根节点 root 和一个值 key，删除树中值为 key 的节点（如果有），并保证删除后仍是一棵二叉搜索树，返回新的根节点。树中不存在 key 时原样返回。删除方式可能有多种，任意正确的结果都可以。",
              ["节点数在 [0, 10⁴] 内", "-10⁵ ≤ Node.val, key ≤ 10⁵", "节点值互不相同"], {0: "删掉 3 后，[5,4,6,2,null,null,7] 和 [5,2,6,null,4,null,7] 都正确。"}),
    "501": st("find-mode-in-binary-search-tree", "给你一棵可能含重复值的二叉搜索树的根节点，找出出现次数最多的值（众数）。如果有多个值出现次数并列最多，全部返回，顺序不限。这里的搜索树允许相等值：左子树的值 ≤ 节点值 ≤ 右子树的值。",
              ["节点数在 [1, 10⁴] 内", "-10⁵ ≤ Node.val ≤ 10⁵"]),
    "530": st("minimum-absolute-difference-in-bst", "给你一棵二叉搜索树的根节点，返回树中任意两个不同节点的值之差的绝对值的最小值。",
              ["节点数在 [2, 10⁴] 内", "0 ≤ Node.val ≤ 10⁵"], {0: "1 和 2、2 和 3、3 和 4 等都相差 1，没有更小的差。"}),
    "538": st("convert-bst-to-greater-tree", "给定一棵节点值互不相同的二叉搜索树，把每个节点的值改成：原树中所有大于或等于该节点值的值之和。树的结构不变，返回根节点。",
              ["节点数在 [0, 10⁴] 内", "-10⁴ ≤ Node.val ≤ 10⁴", "节点值互不相同"], {0: "原值 6 变成 6 + 7 + 8 = 21，原值 8 没有更大的值，保持 8。"}),
    "543": st("diameter-of-binary-tree", "给你一棵二叉树的根节点，返回它的直径：树中任意两个节点之间最长路径的长度，用路径上的边数计。这条路径不一定经过根节点。",
              ["节点数在 [1, 10⁴] 内", "-100 ≤ Node.val ≤ 100"], {0: "最长路径 4 → 2 → 1 → 3（或 5 → 2 → 1 → 3）有 3 条边。"}),
    "567": st("permutation-in-string", "给你两个字符串 s1 和 s2，判断 s2 中是否有一段连续的子串，恰好是 s1 的某种排列（字符和每个字符的出现次数都相同，顺序任意）。",
              ["1 ≤ s1.length, s2.length ≤ 10⁴", "s1 和 s2 只包含小写字母"], {0: "s2 里有 \"ba\"，是 \"ab\" 的一种排列。"}),
    "617": st("merge-two-binary-trees", "给你两棵二叉树 root1 和 root2，把它们叠在一起合并成一棵新树：两边都有节点的位置，新节点的值是两个值之和；只有一边有节点的位置，直接用那个节点。从两棵树的根开始合并，返回合并后的根。",
              ["两棵树的节点数都在 [0, 2000] 内", "-10⁴ ≤ Node.val ≤ 10⁴"]),
    "669": st("trim-a-binary-search-tree", "给你二叉搜索树的根节点 root，以及边界 low 和 high。修剪这棵树，只保留值在 [low, high] 内的节点；保留下来的节点之间的相对结构（谁是谁的祖先或后代）不能变。返回修剪后的根节点，根节点可能会改变。",
              ["节点数在 [1, 10⁴] 内", "0 ≤ Node.val ≤ 10⁴，值互不相同", "0 ≤ low ≤ high ≤ 10⁴"], {1: "0 和 4 超出 [1,3] 被剪掉，0 下面的 2、1 接到 3 的左边。"}),
    "700": st("search-in-a-binary-search-tree", "给定二叉搜索树的根节点 root 和一个值 val，找到值等于 val 的节点，返回以它为根的子树；如果不存在，返回 None。",
              ["节点数在 [1, 5000] 内", "1 ≤ Node.val ≤ 10⁷", "1 ≤ val ≤ 10⁷"]),
    "701": st("insert-into-a-binary-search-tree", "给定二叉搜索树的根节点 root 和一个原树中不存在的值 val，把 val 插入树中，返回插入后的根节点，结果必须仍是二叉搜索树。插入的位置可能有多种，任意正确的结果都可以。",
              ["节点数在 [0, 10⁴] 内", "-10⁸ ≤ Node.val, val ≤ 10⁸，值互不相同", "保证 val 不在原树中"]),
    "977": st("squares-of-a-sorted-array", "给你一个按非递减顺序排列的整数数组 nums（可能有负数），返回每个数平方后组成的新数组，新数组也要按非递减顺序排列。",
              ["1 ≤ nums.length ≤ 10⁴", "-10⁴ ≤ nums[i] ≤ 10⁴", "nums 非递减"], {0: "平方后是 [16,1,0,9,100]，排序后是 [0,1,9,16,100]。"}),
    "1047": st("remove-all-adjacent-duplicates-in-string", "字符串 s 由小写字母组成。每次找到两个相邻且相同的字母，把它们一起删掉；删除后两边的字符变成相邻，可能又出现新的相同对。一直重复，直到不能再删，返回最终的字符串。答案是唯一的。",
               ["1 ≤ s.length ≤ 10⁵", "s 只包含小写字母"], {0: "先删 \"bb\" 得到 \"aaca\"，再删 \"aa\" 得到 \"ca\"。"}),
    "125": st("valid-palindrome", "给你一个字符串 s。先把所有大写字母转成小写，再去掉所有不是字母或数字的字符。如果剩下的字符串正着读和反着读一样，返回 true，否则返回 false。",
              ["1 ≤ s.length ≤ 2×10⁵", "s 由 ASCII 可打印字符组成"], {0: "处理后是 \"amanaplanacanalpanama\"，是回文。", 2: "去掉空格后是空字符串，空串算回文。"}),
    "75": st("sort-colors", "数组 nums 里只有 0、1、2 三种数，分别代表红、白、蓝三种颜色。请原地排序，使相同颜色相邻，并按 0、1、2 的顺序排列。不能使用库里的排序函数；函数不需要返回值。",
             ["n == nums.length，1 ≤ n ≤ 300", "nums[i] 为 0、1 或 2"]),
    "18": st("4sum", "给你数组 nums 和目标值 target，找出所有四个不同下标的元素之和等于 target 的组合 [a, b, c, d]。答案里不能有重复的四元组（数值相同算重复），顺序不限。",
             ["1 ≤ nums.length ≤ 200", "-10⁹ ≤ nums[i], target ≤ 10⁹"]),
    "904": st("fruit-into-baskets", "一排果树从左到右排开，fruits[i] 是第 i 棵树上水果的种类。你有两个篮子，每个篮子只能装一种水果，数量不限。你可以从任意一棵树开始，向右每棵树摘一个水果，一旦遇到两个篮子都装不下的种类就必须停下。返回最多能摘多少个水果。",
               ["1 ≤ fruits.length ≤ 10⁵", "0 ≤ fruits[i] < fruits.length"], {1: "从下标 1 开始摘 [1,2,2]，共 3 个。", 3: "摘 [1,2,1,1,2] 共 5 个。"}),
    "1004": st("max-consecutive-ones-iii", "给定一个只包含 0 和 1 的数组 nums 和整数 k。你最多可以把 k 个 0 改成 1，返回改完之后数组中最长的一段连续 1 的长度。",
               ["1 ≤ nums.length ≤ 10⁵", "nums[i] 为 0 或 1", "0 ≤ k ≤ nums.length"], {0: "把下标 5、10 的 0 改成 1，得到从下标 5 到 10 的 6 个连续 1。"}),
    "424": st("longest-repeating-character-replacement", "给你一个只含大写英文字母的字符串 s 和整数 k。每次操作可以把任意一个位置的字符改成任意大写字母，最多操作 k 次。返回操作后能得到的、只由同一个字母组成的最长连续子串的长度。",
              ["1 ≤ s.length ≤ 10⁵", "s 只包含大写英文字母", "0 ≤ k ≤ s.length"], {0: "把两个 A 都改成 B（或两个 B 改成 A），整串 4 个字符都相同。"}),
    "76": st("minimum-window-substring", "给你字符串 s 和 t，在 s 中找出最短的一段连续子串，使 t 中的每个字符（包括重复的）都被它包含。不存在这样的子串时返回空字符串 \"\"。题目保证答案唯一。",
             ["1 ≤ s.length, t.length ≤ 10⁵", "s 和 t 由英文字母组成"], {0: "\"BANC\" 包含 A、B、C，是满足条件的最短子串。", 2: "t 需要两个 a，s 只有一个。"}),
    "21": st("merge-two-sorted-lists", "给你两个按非递减顺序排列的链表的头节点 list1 和 list2，把它们合并成一个新的有序链表并返回头节点。新链表由原来两个链表的节点拼接而成。",
             ["两个链表的节点数都在 [0, 50] 内", "-100 ≤ Node.val ≤ 100", "两个链表都按非递减顺序排列"]),
    "876": st("middle-of-the-linked-list", "给你单链表的头节点 head，找到链表的中间节点并返回它（判题会从这个节点一直读到链表末尾）。节点个数为偶数、有两个中间节点时，返回第二个。",
              ["节点数在 [1, 100] 内", "1 ≤ Node.val ≤ 100"], {1: "6 个节点有两个中间节点 3 和 4，返回第二个 4。"}),
    "234": st("palindrome-linked-list", "给你单链表的头节点 head，判断这条链表的值序列是不是回文，即正着读和反着读一样。",
              ["节点数在 [1, 10⁵] 内", "0 ≤ Node.val ≤ 9"]),
    "19": st("remove-nth-node-from-end-of-list", "给你一个链表，删除链表的倒数第 n 个节点，返回删除后链表的头节点。被删除的可能正好是头节点。",
             ["链表节点数为 sz，1 ≤ sz ≤ 30", "0 ≤ Node.val ≤ 100", "1 ≤ n ≤ sz"], {0: "倒数第 2 个节点是 4，删掉后是 1 → 2 → 3 → 5。", 3: "倒数第 2 个就是头节点 1。"}),
    "24": st("swap-nodes-in-pairs", "给你一个链表，把相邻的节点两两交换位置，返回交换后链表的头节点。必须真正交换节点本身，不能只交换节点里的值。节点数为奇数时，最后一个节点保持不动。",
             ["节点数在 [0, 100] 内", "0 ≤ Node.val ≤ 100"]),
    "2": st("add-two-numbers", "两个非空链表分别表示两个非负整数，数字按逆序存放：头节点是个位，每个节点存一位数字。请把这两个数相加，并以同样的逆序链表形式返回结果。除了数字 0 本身，两个数都不会以 0 开头。",
            ["每个链表的节点数在 [1, 100] 内", "0 ≤ Node.val ≤ 9", "除了数字 0 本身，没有前导零"], {0: "342 + 465 = 807，逆序存放就是 7 → 0 → 8。"}),
    "92": st("reverse-linked-list-ii", "给你单链表的头节点 head 和两个位置 left ≤ right（位置从 1 开始数），只反转从第 left 个到第 right 个节点的这一段，其余部分保持不变，返回头节点。",
             ["链表节点数为 n，1 ≤ n ≤ 500", "-500 ≤ Node.val ≤ 500", "1 ≤ left ≤ right ≤ n"], {0: "第 2～4 个节点 2 → 3 → 4 反转成 4 → 3 → 2。"}),
    "383": st("ransom-note", "给你两个字符串 ransomNote 和 magazine，判断能否只用 magazine 里的字符拼出 ransomNote。magazine 里的每个字符只能使用一次。",
              ["1 ≤ ransomNote.length, magazine.length ≤ 10⁵", "两个字符串都只包含小写字母"], {1: "需要两个 a，magazine 里只有一个。"}),
    "49": st("group-anagrams", "给你一个字符串数组，把互为字母异位词的字符串分到同一组（用到的字母和每个字母的次数都相同，只是顺序不同）。返回所有分组，组的顺序和组内顺序都不限。",
             ["1 ≤ strs.length ≤ 10⁴", "0 ≤ strs[i].length ≤ 100", "strs[i] 只包含小写字母"]),
    "128": st("longest-consecutive-sequence", "给定一个未排序的整数数组 nums，找出数值上连续的数字（例如 1、2、3、4）最多能凑出多长的序列，返回这个长度。这些数字不要求在原数组中相邻，重复的数字只算一次。请设计 O(n) 时间的算法。",
              ["0 ≤ nums.length ≤ 10⁵", "-10⁹ ≤ nums[i] ≤ 10⁹"], {0: "最长的连续序列是 1、2、3、4，长度 4。"}),
    "560": st("subarray-sum-equals-k", "给你一个整数数组 nums（可能有负数）和整数 k，统计数组中和为 k 的连续子数组一共有多少个。起止位置不同就算不同的子数组。",
              ["1 ≤ nums.length ≤ 2×10⁴", "-1000 ≤ nums[i] ≤ 1000", "-10⁷ ≤ k ≤ 10⁷"], {0: "下标 0～1 和下标 1～2 两段的和都是 2。"}),
    "454": st("4sum-ii", "给你四个长度都为 n 的整数数组 nums1、nums2、nums3、nums4，统计有多少个下标组合 (i, j, k, l) 满足 nums1[i] + nums2[j] + nums3[k] + nums4[l] = 0。",
              ["每个数组长度 n 满足 1 ≤ n ≤ 200", "-2²⁸ ≤ 元素值 ≤ 2²⁸"], {0: "(0,0,0,1)：1 + (-2) + (-1) + 2 = 0；(1,1,0,0)：2 + (-1) + (-1) + 0 = 0。"}),
    "14": st("longest-common-prefix", "给你一个字符串数组，找出所有字符串共同拥有的最长开头部分（公共前缀）。如果没有公共前缀，返回空字符串 \"\"。",
             ["1 ≤ strs.length ≤ 200", "0 ≤ strs[i].length ≤ 200", "非空的 strs[i] 只包含小写字母"]),
    "151": st("reverse-words-in-a-string", "给你一个字符串 s，单词是由非空格字符组成的连续片段。把单词的顺序反过来，用单个空格连接后返回。原字符串开头、结尾可能有空格，单词之间也可能有多个空格，结果里都不能保留多余的空格。",
              ["1 ≤ s.length ≤ 10⁴", "s 包含英文字母、数字和空格", "s 中至少有一个单词"]),
    "5": st("longest-palindromic-substring", "给你一个字符串 s，找出其中最长的回文子串（连续的、正着读和反着读一样）并返回。如果有多个同样长的答案，返回任意一个都可以。",
            ["1 ≤ s.length ≤ 1000", "s 只由数字和英文字母组成"], {0: "\"bab\" 和 \"aba\" 一样长，返回哪个都对。"}),
    "459": st("repeated-substring-pattern", "给定一个非空字符串 s，判断它能否由它的某个子串重复多次（至少两次）拼接而成。",
              ["1 ≤ s.length ≤ 10⁴", "s 只包含小写字母"], {0: "\"ab\" 重复两次。", 2: "\"abc\" 重复四次（\"abcabc\" 重复两次也可以）。"}),
    "150": st("evaluate-reverse-polish-notation", "给你一个字符串数组 tokens，表示一个逆波兰表达式（后缀表达式：运算符写在两个运算数之后），计算并返回表达式的值。运算符只有 + - * /，整数除法向零截断，不会出现除以 0，中间结果和最终结果都在 32 位整数范围内。",
              ["1 ≤ tokens.length ≤ 10⁴", "tokens[i] 是运算符，或 [-200, 200] 内的整数"], {0: "等价于 (2 + 1) * 3 = 9。", 1: "等价于 4 + (13 / 5) = 4 + 2 = 6。"}),
    "739": st("daily-temperatures", "数组 temperatures 记录了每天的气温。对每一天，求要再等几天才会遇到更高的气温，写成 answer[i]；如果之后都不会更高，answer[i] 为 0。返回 answer。",
              ["1 ≤ temperatures.length ≤ 10⁵", "30 ≤ temperatures[i] ≤ 100"], {0: "下标 2 的 75，要到下标 6 的 76 才更高，等 4 天。"}),
    "239": st("sliding-window-maximum", "给你整数数组 nums 和窗口大小 k。一个长度为 k 的窗口从数组最左边每次向右滑动一格，直到最右边。返回窗口在每个位置时里面的最大值。",
              ["1 ≤ nums.length ≤ 10⁵", "-10⁴ ≤ nums[i] ≤ 10⁴", "1 ≤ k ≤ nums.length"], {0: "窗口依次是 [1,3,-1]、[3,-1,-3]、[-1,-3,5]……最大值分别是 3、3、5……"}),
    "347": st("top-k-frequent-elements", "给你一个整数数组 nums 和整数 k，返回出现频率最高的 k 个元素，顺序不限。题目保证答案唯一。要求算法的时间复杂度优于 O(n log n)。",
              ["1 ≤ nums.length ≤ 10⁵", "k 在 [1, 数组中不同元素的个数] 内", "答案唯一"], {0: "1 出现 3 次、2 出现 2 次、3 出现 1 次，最高的两个是 1 和 2。"}),
    "199": st("binary-tree-right-side-view", "想象你站在一棵二叉树的右侧往左看，从上到下每一层你只能看到最右边的那个节点。按从上到下的顺序返回你能看到的节点值。",
              ["节点数在 [0, 100] 内", "-100 ≤ Node.val ≤ 100"], {0: "第 3 层只有 5 和 4，从右边看到的是 4。"}),
    "513": st("find-bottom-left-tree-value", "给定一棵非空二叉树的根节点，找出最底下一层中最左边那个节点的值。",
              ["节点数在 [1, 10⁴] 内", "-2³¹ ≤ Node.val ≤ 2³¹ - 1"], {1: "最底层只有节点 7。"}),
    "105": st("construct-binary-tree-from-preorder-and-inorder-traversal", "给定同一棵二叉树的前序遍历 preorder 和中序遍历 inorder（树中节点值互不相同），还原出这棵树并返回根节点。",
              ["1 ≤ preorder.length ≤ 3000", "inorder.length == preorder.length", "节点值互不相同"]),
    "437": st("path-sum-iii", "给定二叉树的根节点 root 和整数 targetSum，统计有多少条路径上的节点值之和等于 targetSum。路径不必从根开始，也不必在叶子结束，但只能从上往下走（从父节点到子节点）。",
              ["节点数在 [0, 1000] 内", "-10⁹ ≤ Node.val ≤ 10⁹", "-1000 ≤ targetSum ≤ 1000"], {0: "和为 8 的路径有 5 → 3、5 → 2 → 1、-3 → 11，共 3 条。"}),
    "222": st("count-complete-tree-nodes", "给你一棵完全二叉树的根节点 root，返回节点总数。完全二叉树指除最后一层外每层都是满的，最后一层的节点都集中在最左边。进阶：能否做到比 O(n) 更快？",
              ["节点数在 [0, 5×10⁴] 内", "题目保证输入是完全二叉树"]),
}

LEETCODE_URL = "https://leetcode.cn/problems/{}/"
CODEC_NOTES = {"tree": "{}：二叉树的根节点。示例里按层序写成数组，null 表示该位置没有节点",
               "list": "{}：链表的头节点。示例里把链表各节点的值写成数组",
               "node": "{}：树中的一个节点。示例里写的是它的值"}


def entry(pid):
    return STATEMENTS.get(str(pid)) or EXTRA.get(str(pid))


def text(pid):
    """完整题意，供页面和教练提示词使用；没有题面时返回空字符串。"""
    found = entry(pid)
    return found["text"] if found else ""


def _value(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _output(judge, expected, params):
    # 有些题的期望值是判题条件，不是字面输出，这里换成人能读懂的说法。
    if judge == "unique_prefix":
        return f"k = {expected['k']}，nums 的前 {expected['k']} 个元素为 {_value(expected['prefix'])}"
    if judge == "remove_prefix":
        return f"k = {expected['k']}，nums 的前 {expected['k']} 个元素为 {_value(expected['prefix'])}（顺序不限）"
    if judge == "mutated_array":
        return f"修改后 {params[0]} = {_value(expected)}"
    if judge == "balanced_bst":
        return f"任意一棵中序遍历为 {_value(expected['inorder'])} 的高度平衡 BST"
    if judge == "bst":
        return f"任意一棵中序遍历为 {_value(expected['inorder'])} 的二叉搜索树" if expected["inorder"] else "[]（空树）"
    if judge in ("unordered", "triplets", "nested_unordered"):
        return f"{_value(expected)}（顺序不限）"
    if judge == "one_of":
        return _value(expected[0]) + (f"（{'、'.join(_value(v) for v in expected[1:])} 也正确）" if len(expected) > 1 else "")
    return _value(expected)


def _figures(exercise, case, figure):
    found = []
    for name, codec, arg in zip(exercise["params"], exercise["codecs"], case["args"]):
        if codec in ("tree", "list") and arg:
            found.append({"label": name, "kind": codec, "value": arg})
    if figure == "bars" and case["args"][0]:
        found.append({"label": exercise["params"][0], "kind": "bars", "value": case["args"][0], "water": exercise["method"] == "trap"})
    out_kind = {"tree": "tree", "linked_list": "list"}.get(exercise["judge"])
    if out_kind and case["expected"]:
        found.append({"label": "输出", "kind": out_kind, "value": case["expected"]})
    return found


def view(pid, exercise=None):
    """题面展示数据。exercise 为 problem_bank 的练习契约；没有本地用例时用 EXTRA 里写好的示例。"""
    pid = str(pid)
    found = entry(pid)
    if not found:
        return None
    result = {"id": pid, "slug": found["slug"], "url": LEETCODE_URL.format(found["slug"]), "text": found["text"],
              "constraints": found.get("constraints", []), "local": bool(exercise), "param_notes": [], "examples": []}
    if exercise:
        result["method"] = f"{exercise['method']}({', '.join(exercise['params'])})"
        result["param_notes"] = [CODEC_NOTES[c].format(n) for n, c in zip(exercise["params"], exercise["codecs"]) if c in CODEC_NOTES]
        if exercise["judge"] == "mutated_array":
            result["param_notes"].append(f"不需要返回值：判题检查的是函数结束后 {exercise['params'][0]} 的内容")
        for i, case in enumerate(exercise["cases"]):
            result["examples"].append({
                "input": ", ".join(f"{n} = {_value(a)}" for n, a in zip(exercise["params"], case["args"])),
                "output": _output(exercise["judge"], case["expected"], exercise["params"]),
                "note": found["notes"].get(i, ""), "figures": _figures(exercise, case, found.get("figure"))})
    else:
        result["method"] = found.get("method", "")
        for i, example in enumerate(found.get("examples", [])):
            figure = found.get("figure") if i == 0 else None
            result["examples"].append({"input": example["input"], "output": example["output"], "note": example.get("note", ""),
                                       "figures": [dict(figure, label="示例")] if figure else []})
    return result
