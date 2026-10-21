class Solution:
    def groupAnagrams(self, strs: list[str]) -> list[list[str]]:
        ans={}
        for word in strs:
            # 这种排序得到的结果是list，需要将其转为dict
            key = "".join(sorted(word))
            # ans中没出现就先存入key，用空进行占位
            if key not in ans:
                ans[key]=[]
            # 如果排序后出现过就直接将其加入到对应字典里
            ans[key].append(word)
        # 将字典的结果转回list
        return list(ans.values())
