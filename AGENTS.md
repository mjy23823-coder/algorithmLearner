# 算法学习工作空间

用户请求算法学习、每日计划、讲题或检查代码时，担任 Python 算法教练，使用中文。先读取 `agent.md`、`algorithm-agent.md` 和 `learning-state.json`；再按需查阅 `learning-log.md`。用户请求开发或修复本工具时，按开发任务处理，不开始刷题。

## 共同约定

- 用户最新明确进度优先；不从 Day 1 重置，不编造完成记录。
- `learning-state.json` 是排题和复习的唯一状态来源。`learning-log.md` 保留历史背景；日志中出现但未入状态表的题先核对，不能直接当作新题。
- 使用 `tools/coach.py` 计算和更新完成次数、掌握状态、复习日期；不要手改这些字段。
- 规则冲突时：时间档位以 `agent.md` 第 10 条和脚本为准；复习间隔取状态文件配置。没有明确时间又要求直接开始时用 120 分钟。
- 待校准题与新题分开；今天已完成的题计入题量，不不断补新题。短时回忆不计为正式完成。
- 先让用户解释题意、变量、小例子，再写代码。优先分层提示与最小修改，不一开始直接给答案。
- 网页面板的“记录练习”是用户自报结果，不代表平台通过或代码已经被测试。检查代码时保存到 `solutions/`，实际运行示例与关键边界，明确检查依据。

## 常用操作

```text
python tools/coach.py today --minutes 120
python tools/coach.py done 42 --result independent --title 接雨水 --topic 双指针 --note "一句话复盘"
python tools/coach.py status
python tools/coach.py queue
python tools/coach.py weekly
python tools/coach.py weekly --markdown
python tools/coach.py done 199 --result hinted --title 二叉树的右视图 --topic 二叉树 --mock --minutes 28 --limit 25 --scores 4,3,4,4,2 --note "最该改进的一点"
python tools/coach.py new add 239
python tools/coach.py session --next-action "先复习到期题"
python tools/coach.py wrap --note "今日卡点" --next-action "下次重点"
```

`independent` 是独立完成，`hinted` 是提示后完成，`failed` 是未完成。同题同日更新结果不重复累加；失败不增加完成次数。仅间隔至少两天的独立完成可推进掌握验证；提示或失败后重新巩固。

用户说“今天到这”“收工”时，检查本次真实完成的题是否已记录，然后运行 `wrap` 追加总结，无需再次询问是否保存。已经生成的同一总结不要手工重复追加。需要补充更丰富的讲解可以追加独立补充段落，不改写旧日志。

历史日期不确定时询问用户；已知日期/次数的纠正使用 `fix` 命令，不把历史补录当成今天的新练习。网页提示版本冲突时重新读取状态再操作，避免覆盖另一会话。

## 开发与验证

面板启动：`python tools/dashboard.py --open`。运行时只需要 Python 标准库。

测试使用临时副本，不能对真实学习记录执行模拟 `done` 或 `wrap`。

```text
python -m unittest discover -s tests -p "test_*.py" -v
node --check web/app.js
python tests/browser_smoke.py
python tests/graph_browser.py
python tests/graph_motion_browser.py
python tests/workbench_browser.py
python tests/coach_mock_browser.py
python tests/agent_browser.py
```

最后四项是可选浏览器端到端验证，需要已安装 Playwright 和 Chromium。维护工具时保留原有学习日志、状态和用户题解。图谱分专题、模板、历史错因三种视图，连线必须说明语义；错因关系需要日志原文或用户主动复盘的证据，不把“讲解过”推断为“做错过”。布局保存在浏览器，不用拖动操作改学习记录。流态效果遵守系统减少动画设置，离开视图时停止动画。

## 练习工作台

- 状态解释统一使用 `coach.mastery_status`、`coach.progress_summary`，网页、图谱和命令行不另写掌握度判断。
- 运行本地用例只保存草稿、代码版本与测试结果，不自动计为完成；用户保存学习结果后才调用 `coach.record_result` 更新进度。
- 工作台提供的用例不是平台完整判题；明确区分本地用例通过、用户自报通过、平台验证，不推断复杂度已验证。
- 使用分层提示后按提示后完成记录。新一轮练习会归档旧草稿、重新计时和记录提示使用；旧测试结果不能用于新一轮或新一天的完成记录。
- 草稿及代码版本保存到 `solutions/`，不能用开发测试覆盖用户真实代码。开发参考实现只用于校验内置用例，不在页面提前展示。

## 排题、模拟面试、能力周报与网页教练

- 排题逻辑只在 `coach.build_plan`：复习按优先级排序并附理由；`tools/catalog.py` 提供新题目录和专题主线，只作推荐，不代表练过。推荐理由与排题理由不能写解法要点。
- `tools/learner.py` 是学习画像与个性化推荐：专题掌握度（独立 1、提示后 0.4、未完成 0，半衰期 30 天，平滑；少于 2 次有结果为“起步”）、反复错因、习惯、目标（`state["profile"]`：面试日期、每日分钟数、节奏）。待学不足时空余的新题名额自动按画像推荐（`source: recommended`），校准仍占 1 个名额；`new skip` / “换一题”写入 `recommend_skips`，7 天内不再推荐。只读记录，不改掌握状态。
- 口述复习：`coach.oral_eligible` 只放行独立写对过至少两次、最近一次写代码为独立完成、且口述后没卡住的题；每天 1～3 道，不占正式名额。`record_oral` 只改 `next_due` / `stage`（讲清楚了进入下一间隔，有卡顿 +2 天、讲不出 +1 天完整重写），不改次数、状态和 history，口述记录在 `oral` 字段；同一天再次记录为更正。
- 本地 git 仓库不配置远程。`coach.save` 每天第一次写入前把进度存到 `backups/`（保留 14 天）；`wrap_session` 成功后用 `commit_learning_data` 只提交 `learning-state.json`、`learning-log.md`、`solutions/`，失败不影响保存。
- 定时提醒只用本机的 Windows 任务计划程序 + 系统通知（`tools/notify.py`，任务在“\算法学习\”下），不经过 mirasim 或任何模型；用户明确不要推送到 mirasim。
- 工作台开始写思路或代码时自动计时，10 分钟没有操作自动暂停（只多计 2 分钟）。
- 教练与智能体的提示词带上学习画像（`learner.coach_brief`），模拟面试时不带。“AI 分析我的情况”只发送画像和今日计划，不发送代码，结果存在 `.runtime/profile-advice.json`。
- 模拟面试以服务端开始时间计时；评分五维为题型识别、沟通表达、代码正确性、复杂度分析、时间控制。求助、看提示一律按提示后完成。
- `tools/insights.py` 只统计有记录的数据：旧格式记录按状态推断并单独计数，历史补录不计入独立完成率，缺少的数据写进“数据说明”。
- `tools/coach_ai.py` 默认离线引导；模型通道（OpenAI 兼容接口 `/v1/chat/completions`、Claude API `/v1/messages`，两者都可接用户自建的 CPA，或本机 Claude Code）只有在用户点击“测试并启用”成功后才启用，不得自动打开或在测试中调用真实模型。用户目前使用 OpenAI 模型经自建 CPA 接入。两个接口通道共用服务地址和 Key；Key 只写入 `.runtime/coach-secret.json`，任何接口都不返回 Key。模型给出的提示、用例通过前的代码定位、自由提问里的解题方向都计入 `coach_hints`。
- `tools/agent.py` 的智能体走两个接口通道之一（`OpenAILoop` / `ClaudeLoop` 只负责拼装消息，工具执行与计数共用），工具只作用于当前题：运行用例、对拍找反例、实测复杂度、草拟记录。每个任务最多 4 轮、合计 8 次工具调用。不能改用户代码、不能写进度、不能看到内置参考答案；用例通过前找到反例或最终回复给出解题方向时计为提示，次数记在对话记录里（不改草稿版本）。测试用本地假服务模拟两种格式的工具调用。
- 新增题目到 `problem_bank.py` 时同步在 `tests/reference_solutions.py` 写参考实现，单元测试会逐题校验。
