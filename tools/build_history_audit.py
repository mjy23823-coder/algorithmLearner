"""2026-10-17 历史核对清单：基于逐段阅读，而非把日志中所有提及都当成完成。

生成可审阅 JSON，之后由 coach.py import-history 验证并补录。此脚本不修改学习状态。
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_HASH = "420323535514489fcb967fa90db5bd03c2c7b80c1475540a2d4e1efa900abcf1"


def build():
    raw = (ROOT / "learning-log.md").read_bytes()
    if hashlib.sha256(raw[:47926]).hexdigest() != SOURCE_HASH:
        raise ValueError("原日志与核对版本不一致，请重新核对引用")
    lines = raw.decode("utf-8-sig").splitlines()

    def event(day, result, refs, note, completion_confirmed=True):
        row = {"date": "2026-" + day, "result": result, "note": note,
               "evidence": [{"line": n, "text": lines[n - 1]} for n in refs]}
        if result == "historical":
            row["completion_confirmed"] = completion_confirmed
        return row

    specs = [
        ("1", "两数之和", "哈希", [event("09-13", "historical", [42, 44, 100], "哈希表保存已经出现的数字和下标；完成有记录，是否独立未注明")]),
        ("217", "存在重复元素", "哈希", [event("09-13", "historical", [42, 49, 100], "集合判重；完成有记录，是否独立未注明")]),
        ("283", "移动零", "双指针", [event("09-15", "historical", [119, 126, 148], "slow 指向下一个非零元素的写入位置；独立性待验证")]),
        ("344", "反转字符串", "双指针", [event("09-15", "historical", [171, 179], "相向双指针与原地交换；日志确认完成，未注明是否无提示独立完成")]),
        ("20", "有效的括号", "栈", [
            event("09-16", "failed", [199, 201, 236], "首次尝试未完整通过，不计完成"),
            event("09-17", "historical", [255, 257, 279], "完成括号匹配，独立性未注明"),
            event("09-19", "independent", [328, 330], "已独立完成；先判断空栈再匹配括号")]),
        ("1047", "删除字符串中的所有相邻重复项", "栈", [event("09-17", "historical", [255, 263, 279], "用栈处理相邻消除；完成有记录，独立性未注明")]),
        ("977", "有序数组的平方", "双指针", [event("09-17", "historical", [286, 288, 296], "日志有加练思路和模板，但未明确最终代码是否完成；完成次数待核对", False)]),
        ("167", "两数之和 II - 输入有序数组", "双指针", [event("09-18", "historical", [305, 310], "代码逻辑正确；注意返回 1-based 下标，独立性未注明")]),
        ("206", "反转链表", "链表", [
            event("09-19", "independent", [334, 336], "先保存下一个节点，再反转箭头"),
            event("09-20", "independent", [378, 380], "再次独立写出正确代码；相隔一天，不提升间隔掌握级别")]),
        ("203", "移除链表元素", "链表", [
            event("09-19", "independent", [342, 344], "dummy 固定起点，cur 为待检查节点的前驱"),
            event("09-20", "hinted", [387, 389, 390, 403], "修正 cur = cur.next.next 为修改 cur.next；当日总结确认完成复盘"),
            event("09-22", "independent", [417, 419], "独立完成，删除节点后不移动 cur")]),
        ("104", "二叉树的最大深度", "二叉树", [event("09-20", "independent", [394, 396], "空节点返回 0，当前高度为 1 + max(左右高度)")]),
        ("144", "二叉树的前序遍历", "二叉树", [event("09-22", "historical", [425, 427, 441], "已完成递归前序遍历；9-23 只口述，不另计完成次数")]),
        ("94", "二叉树的中序遍历", "二叉树", [event("09-22", "independent", [432, 434], "左中右；9-23 只口述，不另计完成次数")]),
        ("145", "二叉树的后序遍历", "二叉树", [event("09-22", "independent", [444, 446], "左右中；9-23 只口述，不另计完成次数")]),
        ("102", "二叉树的层序遍历", "二叉树", [
            event("09-22", "hinted", [456, 458, 468], "提示后完成队列版层序遍历，理解 level_size、level 与 result"),
            event("09-26", "failed", [524], "popleft 放在层循环外，尚未提交修正后的完整代码；9-27 短时回忆不另计完成")]),
        ("226", "翻转二叉树", "二叉树", [event("09-23", "hinted", [499], "经提示修正终止条件和遗漏的左右交换，再完成递归代码")]),
        ("100", "相同的树", "二叉树", [
            event("09-23", "historical", [511, 513], "日志确认补全并提交正确代码；整题是否无提示独立完成未明确"),
            event("09-26", "independent", [523], "独立重写正确，用 and 将左右子树判断结果传回上层")]),
        ("101", "对称二叉树", "二叉树", [event("09-26", "hinted", [525], "分层提示后完成镜像递归，配对左左与右右、左右与右左")]),
        ("543", "二叉树的直径", "二叉树", [
            event("09-27", "independent", [564, 566], "返回高度，同时用左右高度之和更新最大直径"),
            event("10-03", "independent", [669, 671], "间隔后再次独立完成，使用 nonlocal 更新直径")]),
        ("112", "路径总和", "二叉树", [
            event("09-27", "hinted", [574, 576, 578], "经关键纠错后完成；用 remain 参数传递各分支剩余和"),
            event("10-02", "historical", [638, 639, 641], "复习正确完成，曾混淆 root 和 node；是否无提示完成未注明")]),
        ("110", "平衡二叉树", "二叉树", [
            event("09-28", "hinted", [587, 589], "有代码框架提示时完成，用 -1 向上传递不平衡"),
            event("10-01", "independent", [605, 607], "首次有明确记录的独立重写完成，仍需下一次间隔验证")]),
        ("257", "二叉树的所有路径", "二叉树", [
            event("09-28", "hinted", [596, 598], "经提示补空节点、左右递归与回溯"),
            event("10-01", "independent", [611, 613], "独立写出回溯代码，递归返回前 pop 恢复路径")]),
        ("404", "左叶子之和", "二叉树", [event("10-01", "hinted", [619, 621, 623], "纠正递归调用缺少累加的问题，保留巩固状态")]),
        ("617", "合并二叉树", "二叉树", [event("10-01", "independent", [626, 628], "独立完成：空树返回另一棵，非空则累加并递归合并")]),
        ("700", "二叉搜索树中的搜索", "BST", [event("10-02", "historical", [644, 645, 660], "已完成递归搜索；是否独立未注明")]),
        ("98", "验证二叉搜索树", "BST", [event("10-02", "historical", [650, 651, 660], "上下界约束并严格比较；是否独立未注明")]),
        ("235", "二叉搜索树的最近公共祖先", "BST", [event("10-03", "historical", [678, 680], "修正递归调用缺少 return，整题独立性待验证")]),
        ("530", "二叉搜索树的最小绝对差", "BST", [
            event("10-03", "historical", [684, 686], "中序遍历比较相邻差值，首次完成独立性未注明"),
            event("10-04", "independent", [695, 697], "独立完成；相隔一天，不因重复练习标为间隔掌握")]),
        ("108", "将有序数组转换为二叉搜索树", "BST", [event("10-04", "historical", [704, 706, 708], "递归区间与构树逻辑正确，修正 Python 节点构造语法；整题独立性未注明")]),
        ("701", "二叉搜索树中的插入操作", "BST", [event("10-03", "historical", [711, 713], "10-04 日志中用户确认昨日完成，故练习日期为 10-03；独立性未注明")]),
        ("501", "二叉搜索树中的众数", "BST", [event("10-07", "hinted", [746, 748, 767], "多次修正后完成；注意 prev 保存值和连续计数更新顺序")]),
        ("230", "二叉搜索树中第 K 小的元素", "BST", [event("10-07", "independent", [753, 755], "独立写出正确中序计数代码，可在找到后提前停止")]),
        ("11", "盛最多水的容器", "双指针", [event("10-11", "hinted", [825, 827, 835], "讲解后修正指针边界和移动方向；计算面积后移动较短木板")]),
    ]
    manifest = {"schema_version": 1, "audit_id": "learning-log-recovery-2026-10-17",
                "source": "learning-log.md", "source_bytes": 47926, "source_sha256": SOURCE_HASH,
                "policy": "仅补缺失题目；次数是日志能确认的下限；未注明独立性用 historical；口述、计划和同日重复不增加次数",
                "excluded": [
                    {"date": "2026-09-23", "ids": ["144", "94", "145", "102"], "reason": "仅口述复盘，不追加完成记录", "line": 498},
                    {"date": "2026-09-27", "ids": ["102"], "reason": "短时回忆安排，不追加完成记录", "line": 543},
                    {"ids": ["42"], "reason": "只有待学队列记录，不能计为练过"}],
                "records": [{"id": pid, "title": title, "topic": topic, "events": events}
                            for pid, title, topic, events in sorted(specs, key=lambda row: int(row[0]))]}
    path = ROOT / "data" / "history-review-2026-10-17.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(build())
