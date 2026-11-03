# Expense Loop 边界试验 v0.1

这是一份分支内的设计草案，用于试验“3 个产品执行载体 + 2 个开发支撑载体、4 条 Function”的划分。
它没有替换现有八条 Function、五个载体定义、历史判断或平台接口。

结构化边界草案见 [model.json](model.json)，本页解释取舍与覆盖关系。两者均是设计文档，不是新增 schema、运行时或平台契约。

## 版本与方案依据

以下版本及 PR 状态核对于 2026-11-03，仅作为本次试验的基线快照。

- 分支基线：Expense `40b4d763f85d6b8be38f682afaae262b47acfa97`，来自仍未合并的 [PR #4](https://github.com/choreoatlas/Expense-Approval/pull/4)。
- 本轮读取的 main：`6100d4538d0d5210a1fc9d97d24d2112be2b164f`。主业务代码与上述候选一致；候选额外保存接入工具及证据。
- 概念依据：[原始 CloseLoop 方案包清单](https://github.com/choreoatlas/close_loop_management/blob/e035bfc4d0292706a9f18fe745b5f3a0e8a7e072/authority/original_close_loop_model/v0.1/CONTENT_MANIFEST.json)，特别是主模型 §4、§5.1–5.2、§6.1–6.2，Execution/Function v0.2 与 Relation Protocol v0.1。
- 目标依据：[原委托](https://github.com/choreoatlas/Expense-Approval/issues/1)及[总经理两阶段要求](https://github.com/choreoatlas/Expense-Approval/issues/1#issuecomment-5571183600)。
- [原 Owner 接受](https://github.com/choreoatlas/Expense-Approval/issues/1#issuecomment-5571375864)绑定 `c0f01dbf4af0dc9f9201c15f37cf960b925fce0c` 与 `reference-sample` 域。现有 v0.2 的部分 current/gap 是接受前的历史时点，不能直接作为今天的未实现清单。
- 冻结观察仍来自 `57fa2b3551a0e8f9243241cb2604d03ca09b19d8`，不改称本试验分支的执行。

Expense 是开发对象；CloseLoop 三个仓库共同提供开发平台。费用单版本和业务角色不是平台 Loop 身份或治理权威。
范围沿用本地单组织、具名角色、SQLite、Chromium 和正常应用重启；原 scope/limits 保留。

## 执行 Loop：以实现载体为边界

| ID | 实现载体 | 拥有的实施责任 | 边界外 |
| --- | --- | --- | --- |
| E1 | 费用审批核心 | domain + Store：内容校验、角色、状态、版本、决定与账本 | HTTP、UI、Function 判断 |
| E2 | 本地应用服务 | HTTP、JSON/错误映射、静态资源、应用装配与进程入口 | 重新定义审批规则 |
| E3 | 浏览器客户端 | 表单、操作、状态和历史展示 | 权威权限检查、服务端状态变更 |
| E4 | 验证与原始观察工具 | tests、CI、依赖环境、observe：驱动程序并保存观察 | 由 runner 断定 Function 成立 |
| E5 | 项目接入与冻结重放工具 | profile、对象/版本绑定、材料恢复、公共入口调用 | 复制平台算法、从 replay 自动生成判断 |

E1 合并的是管理边界，domain.py 与 store.py 的文件结构保持不动。
当前 Store 承担业务流程、最新版本检查和状态选择，将其描述为纯持久化层会掩盖真实责任。

实现调用依赖为 E3 → E2 → E1。E4 驱动产品载体；E5 引用项目定义与 E4 材料，调用既有平台接口。
这些是调用/工作依赖说明，不是已经写入的正式 relation 记录。

model.json 的 maintained_paths 给出唯一的候选维护归属。测试代码由 E4 维护，断言必须追溯到对应 Function 契约；
它不因此拥有业务规则或路径判断。其他载体可以引用测试和运行材料。

E5 对 conditions/composition 等文件只承担格式、绑定和引用的技术维护；判断准则仍归对应 Function 作者。
归档保管也不改变原始观察、判断与平台输出各自的来源和事实归属。

records/ 下的观察、manifest、runner 脚本和结果全部保留为冻结历史材料；
其中 Python 文件不因为进入此表就成为新的活动实现入口。E5 的活动入口是现有顶层 replay.py 等项目适配代码。

## Function：以独立目标和判断责任为边界

| ID | 能力目标 | 输入 → 输出 | 责任止点 |
| --- | --- | --- | --- |
| F1 | 申报准备与提交 | 员工/内容 → 合法且确定的已提交版本 | 不产生审批决定 |
| F2 | 两阶段安全决策 | 当前待审版本/角色/理由 → 决定链及对应状态 | 不编辑内容或创建返修版本 |
| F3 | 拒绝后的新草稿 | 当前拒绝版本/修订内容 → 新 draft revision | 重提由 F1、再审由 F2 承担 |
| F4 | 可追溯历史读取 | 费用单身份 → 有序版本及角色/理由明确的决定视图 | 不产生或改写业务决定 |

初审和总经理终审先放在 F2 内，分别保留角色、阶段、同版本和拒绝条件。
F2 的目标是完整的两阶段决策能力；这不将两个阶段压成一次检查。

F3 自身止于新草稿。原“拒绝—修订—重提—再次审批”完整承诺仍由 I1/I2 明确覆盖：
F3 → F1 → F2，不能因调整边界漏掉重新提交、两阶段重新审批或旧决定保留。

F1–F4 的 product_support 是 E1/E2/E3，verification_support 是 E4。
同用一组载体不合并能力目标或判断责任。E5 负责平台交接，不作为业务能力成立的证明。

各路径还分别记录了源码可见的 current_capability_state、尚待澄清而非已经证实缺功能的 capability_gap，
以及向执行载体提出补证、修正或范围澄清的反馈边界。它们不是仅有名称和静态分类的清单。

## 共享条件逐路径负责

| 条件 | F1 | F2 | F3 | F4 |
| --- | --- | --- | --- | --- |
| 版本一致性 | 提交内容与版本确定，提交后冻结 | 决定绑定同一当前版本 | 新版本不继承旧审批 | 正确显示版本/决定关系 |
| 历史保留 | 不覆盖已提交/审查事实 | 保留两阶段决定和理由 | 保留旧版及拒绝 | 可查询、排序、核对 |
| 非法操作不改变业务状态 | 输入、编辑、提交 | 角色、阶段、旧版、重复决定 | 资格、内容、重复修订 | 有效/无效查询 |
| 浏览器可办理 | 建稿、编辑、提交 | 两阶段批准与拒绝 | 返修并交付 F1 | 查询并核对历史 |
| 正常本地重启恢复 | 角色、内容、提交状态 | 阶段及决定 | 新旧版本和拒绝 | 恢复后的查询 |

浏览器与恢复能力在此草案中改为各路径的必要契约条件，不降为可选项。
Chromium、本地 SQLite 和正常应用重启等原限制仍然适用。
同一证据可以复用，但每条 Function 必须说明它支撑自己的哪个条件；不存在全局“共享条件通过”结论。

这份草案列的是拟议路径条件，没有产生新 assessment、composition 或 path_state，也未激活 condition-assessment pilot。

## 原八条目标的覆盖对照

| 原身份 | 草案中的责任位置 |
| --- | --- |
| FL-draft-submit | F1 |
| FL-authority-safe-review | F2 的初审条件 |
| FL-general-manager-final-approval | F2 的终审条件 |
| FL-reject-revise-resubmit | F3 新草稿 + I1/I2 中的 F1 重提、F2 再审 |
| FL-approval-revision-binding | F1–F4 各自的版本条件 |
| FL-history | F4 读取；F1–F3 的历史保留条件 |
| FL-browser | F1–F4 的界面条件与 I1/I2 |
| FL-durable | F1–F4 的恢复条件与 I4 |

原始目标、scope/limits 以源定义为准。此表是设计覆盖对照，不是状态迁移或自动 supersedes。
尤其是旧终审 pilot 只判断了它原有范围，不能直接变成新 F2 的结果。
旧八条定义和候选材料仍由现有 reader 使用，未将本草案接入运行链。

## 关系与修订

每个 Loop 保留自己的边界和事实归属，多对多引用发生在明确的记录之间。
正式 supports/composes/depends_on 的 source 是被支撑/组合的 Function 记录，target 是被引用的 Execution 记录；
材料向上交付的示意箭头不等于 typed edge 的方向。

真正采用时需绑定两端记录与 revision、actor、scope、limits、依据和传播规则。
相关依据变化才沿适用关系触发 stale/rejudge；项目节点、目录或任意文件变化不自动使全部路径失效。
原 execution-design 的 supports 数组是待核对的设计声明，不直接导入为正式关系事实。

## 试验中保留的问题

1. **历史粒度**：原委托的 full status history 是否要求每次状态转换的事件日志？
   当前代码主要保存 revision 当前状态和有序决定。草案保留原要求，不静默承诺或缩减事件覆盖。
2. **并发范围**：同一费用单的哪些并发操作应原子地维护状态与版本不变量？
   ThreadingHTTPServer 与部分事务外检查构成待调查代码风险，尚未运行证实。
3. **业务调用身份**：具名本地角色与“员工办理自己的费用”之间的信任边界如何解释？
   角色查找不等于认证调用者；仍需结合原样例范围澄清，不自行扩成企业 IAM。

这些问题不撤销历史接受，也不把源代码推断冒充新执行事实。

后续获准的演化应保留载体边界、changed scope、source revision、执行/证据引用和复现限制；
Function 对照目标和当前能力提出有界支撑要求，再据新依据判断。相关依赖按 typed relation 重判，
历史发现、拒收与修正回应继续保留。新治理决定由适用的治理 actor 形成，本草案不代行。

## 如何审阅这一版

先检查载体维护归属、四条目标止点、原八条要求覆盖和 I1–I4 的交接，再决定是否采用或调整。
采用之前要明确剩余问题、目标/条件版本以及适配器所需的有界调整。
本分支只新增这两份试验文档；业务、测试、CI、历史定义、证据和三个平台仓库均不改动。
