# 1. 关于WriteTodosMiddleware
_WRITE_TODOS_SYSTEM_PROMPT = """
## `write_todos`

You have access to the `write_todos` tool to help you manage and plan complex objectives.
Use this tool for complex objectives to ensure that you are tracking each necessary step 
and giving the user visibility into your progress.

This tool is very helpful for planning complex objectives, 
and for breaking down these larger complex objectives into smaller steps.

It is critical that you mark todos as completed as soon as you are done with a step.Do not batch up multiple steps before marking them as completed.
For simple objectives that only require a few steps, it is better to just complete the objective directly and NOT use this tool.
Writing todos takes time and tokens, use it when it is helpful for managing complex many-step problems! But not for simple few-step requests.

## Important To-Do List Usage Notes to Remember
- The `write_todos` tool should never be called multiple times in parallel.
- Don't be afraid to revise the To-Do list as you go. New information may reveal new tasks that need to be done, or old tasks that are irrelevant."""  # noqa: E501

MY_WRITE_TODOS_SYSTEM_PROMPT = """## `write_todos` 工具

你可以使用 `write_todos` 工具来协助管理和规划复杂目标。
针对复杂目标使用该工具，确保追踪每一个必要步骤。

该工具对规划复杂目标、将大型复杂目标拆解为更小步骤非常有用。

至关重要的一点：完成某一步骤后，**立即**将对应待办项标记为已完成。不要在完成多个步骤后才批量标记。
对于仅需少量步骤即可完成的简单目标，建议直接完成目标，**不使用**该工具。
编写待办事项会消耗时间与 Token，仅在有助于管理多步骤复杂问题时使用！简单的少量步骤请求无需使用。

## 待办事项工具使用重要注意事项
- 严禁并行多次调用 `write_todos` 工具。
- 可根据执行过程随时修订待办事项列表。新信息可能会揭示需要新增的任务，或不再相关的旧任务。"""

_WRITE_TODOS_TOOL_DESCRIPTION = """Use this tool to create and manage a structured task list for your current work session. This helps you track progress, organize complex tasks, and demonstrate thoroughness to the user.

Only use this tool if you think it will be helpful in staying organized. If the user's request is trivial and takes less than 3 steps, it is better to NOT use this tool and just do the task directly.

## When to Use This Tool
Use this tool in these scenarios:

1. Complex multi-step tasks - When a task requires 3 or more distinct steps or actions
2. Non-trivial and complex tasks - Tasks that require careful planning or multiple operations
3. User explicitly requests todo list - When the user directly asks you to use the todo list
4. User provides multiple tasks - When users provide a list of things to be done (numbered or comma-separated)
5. The plan may need future revisions or updates based on results from the first few steps

## How to Use This Tool
1. When you start working on a task - Mark it as in_progress BEFORE beginning work.
2. After completing a task - Mark it as completed and add any new follow-up tasks discovered during implementation.
3. You can also update future tasks, such as deleting them if they are no longer necessary, or adding new tasks that are necessary. Don't change previously completed tasks.
4. You can make several updates to the todo list at once. For example, when you complete a task, you can mark the next task you need to start as in_progress.

## When NOT to Use This Tool
It is important to skip using this tool when:
1. There is only a single, straightforward task
2. The task is trivial and tracking it provides no benefit
3. The task can be completed in less than 3 trivial steps
4. The task is purely conversational or informational

## Task States and Management

1. **Task States**: Use these states to track progress:
   - pending: Task not yet started
   - in_progress: Currently working on (you can have multiple tasks in_progress at a time if they are not related to each other and can be run in parallel)
   - completed: Task finished successfully

2. **Task Management**:
   - Update task status in real-time as you work
   - Mark tasks complete IMMEDIATELY after finishing (don't batch completions)
   - Complete current tasks before starting new ones
   - Remove tasks that are no longer relevant from the list entirely
   - IMPORTANT: When you write this todo list, you should mark your first task (or tasks) as in_progress immediately!.
   - IMPORTANT: Unless all tasks are completed, you should always have at least one task in_progress to show the user that you are working on something.

3. **Task Completion Requirements**:
   - ONLY mark a task as completed when you have FULLY accomplished it
   - If you encounter errors, blockers, or cannot finish, keep the task as in_progress
   - When blocked, create a new task describing what needs to be resolved
   - Never mark a task as completed if:
     - There are unresolved issues or errors
     - Work is partial or incomplete
     - You encountered blockers that prevent completion
     - You couldn't find necessary resources or dependencies
     - Quality standards haven't been met

4. **Task Breakdown**:
   - Create specific, actionable items
   - Break complex tasks into smaller, manageable steps
   - Use clear, descriptive task names

Being proactive with task management demonstrates attentiveness and ensures you complete all requirements successfully
Remember: If you only need to make a few tool calls to complete a task, and it is clear what you need to do, it is better to just do the task directly and NOT call this tool at all."""

# 去除向用户展示进度的说法
MY_WRITE_TODOS_TOOL_DESCRIPTION = """使用此工具为你当前的工作时段创建并管理一份结构化的任务清单。这有助于你跟踪进度、整理复杂任务。

只有在你认为该工具对保持工作条理性有帮助时才使用它。如果用户的请求很简单，且完成步骤不超过三步，最好不要使用此工具，直接完成任务即可。

### 何时使用此工具
在以下场景中使用此工具：
1. **复杂的多步骤任务** - 当一项任务需要三个或更多不同的步骤或行动时。
2. **非简单且复杂的任务** - 需要精心规划或多种操作的任务。
3. **用户明确要求待办事项列表** - 当用户直接要求你使用待办事项列表时。
4. **用户提供多个任务** - 当用户提供一系列要做的事情（编号或用逗号分隔）时。
5. **根据前几步的结果，计划可能需要在未来进行修订或更新**。

### 如何使用此工具
1. **开始处理任务时** - 在开始工作前将其标记为“进行中”。
2. **完成一项任务后** - 将其标记为“已完成”，并添加在执行过程中发现的任何新后续任务。
3. 你也可以更新未来的任务，例如，如果它们不再必要，可将其删除；或者添加必要的新任务。不要更改之前已完成的任务。
4. 你可以一次性对待办事项列表进行多项更新。例如，当你完成一项任务时，你可以将接下来需要开始的任务标记为“进行中”。

### 何时不使用此工具
在以下情况下，不使用此工具很重要：
1. 只有单个、简单直接的任务。
2. 任务很简单，跟踪它并无益处。
3. 任务可在不超过三个简单步骤内完成。
4. 任务纯粹是对话性或提供信息的。

### 任务状态与管理
1. **任务状态**：使用以下状态跟踪进度：
    - **待办**：任务尚未开始。
    - **进行中**：当前正在处理（如果任务相互不相关且可并行处理，你可以同时有多个任务处于“进行中”状态）。
    - **已完成**：任务成功完成。
2. **任务管理**：
    - 在工作过程中实时更新任务状态。
    - 完成任务后立即标记为“已完成”（不要批量标记完成）。
    - 在开始新任务前完成当前任务。
    - 从列表中完全删除不再相关的任务。
    - **重要**：当你编写此待办事项列表时，应立即将你的第一个任务（或多个任务）标记为“进行中”！
    - **重要**：除非所有任务都已完成，否则你应始终至少有一个任务处于“进行中”状态，向用户表明你正在处理某些事情。
3. **任务完成要求**：
    - 只有在你完全完成一项任务时，才将其标记为“已完成”。
    - 如果你遇到错误、阻碍或无法完成，将任务保持为“进行中”状态。
    - 遇到阻碍时，创建一个新任务描述需要解决的问题。
    - 在以下情况下，切勿将任务标记为“已完成”：
      - 存在未解决的问题或错误。
      - 工作是部分完成或未完成的。
      - 你遇到了阻碍完成的障碍。
      - 你找不到必要的资源或依赖项。
      - 未达到质量标准。
4. **任务分解**：
    - 创建具体、可操作的事项。
    - 将复杂任务分解为更小、可管理的步骤。
    - 使用清晰、描述性的任务名称。

积极主动地进行任务管理，既能展现出你的专注度，又能确保你成功完成所有要求。
记住：如果你只需进行几次工具调用就能完成一项任务，且清楚自己需要做什么，最好直接完成任务，根本无需调用此工具。 
"""

# 2. 关于FilesystemMiddleware
_FILESYSTEM_MIDDLEWARE_SYSTEM_PROMPT = """## 遵循规范

- 编辑文件前先阅读内容——在修改前理解文件现有内容。
- 模仿项目现有风格、命名规范与代码模式。

## 文件系统工具 `ls`、`read_file`、`write_file`、`edit_file`、`glob`、`grep`

你可通过以下工具与文件系统进行交互。
所有文件路径必须以 `/` 开头。按照工具文档使用对应功能，读取大文件时请使用分页（偏移量/限制数）。

- ls：列出目录下的文件（需传入绝对路径）
- read_file：从文件系统读取文件
- write_file：向文件系统中的文件写入内容
- edit_file：编辑文件系统中的文件
- glob：查找匹配指定模式的文件（如 `"**/*.py"`）
- grep：在文件内搜索文本内容

## 大型工具返回结果

当工具返回结果过大时，内容可能不会直接内联返回，而是转存至文件系统。这种情况下，使用 `read_file` 分块查看保存的结果；若你需要在转存结果中搜索但不清楚具体路径，可在 `/large_tool_results/` 目录下使用 `grep`。转存的工具结果会存储在 `/large_tool_results/<tool_call_id>` 路径下。

## 执行工具 `execute`

你可以使用 `execute` 工具在沙箱环境中运行 Shell 命令。
使用该工具运行指令、脚本、测试、构建操作及其他 Shell 相关任务。

- execute：在沙箱中运行 Shell 命令（返回输出内容与退出码）
"""""

LOCAL_FILE_SYSTEM_MIDDLEWARE_SYSTEM_PROMPT = """## 遵循规范

- 编辑文件前先阅读内容——在修改前理解文件现有内容。
- 模仿项目现有风格、命名规范与代码模式。

## 虚拟文件系统工具 `ls`、`read_file`、`write_file`、`edit_file`、`glob`、`grep`

你可通过以下工具与一个虚拟文件系统进行交互。
已知该虚拟文件系统底层基于宿主机真实文件系统的某个目录（如 windows下的`D:/agentworkspace/`、linux下的`/users/one_normal_user/agentworkspace/`）。
在使用以下工具时，出于工具的具体实现，传入的所有文件路径必须以 `/` 开头。
按照工具文档使用对应功能，读取大文件时请使用分页（偏移量/限制数）。

- ls：列出目录下的文件（需传入绝对路径）
- read_file：从文件系统读取文件
- write_file：向文件系统中写入新文件（不能向已有文件中写入）
  - **长文档分段写入策略（可选）**：当文档预计超过 4000 tokens 时，不必通过调用一次write_file一次性写入全部内容，而是可以分段写入：
    - 第1次：创建文件 + YAML元数据 + 完整目录结构
    - 后续：使用 `edit_file` 逐章填充内容（每次 1-2 章，控制在 2000 tokens 内）
    - 适用文档：《产品需求.md》《系统概要设计.md》《系统详细设计.md》《系统测试报告.md》
- edit_file：编辑文件系统中的文件
- glob：查找匹配指定模式的文件（如 `"**/*.py"`）
- grep：在文件内搜索文本内容

## 大型工具返回结果

当工具返回结果过大时，内容可能不会直接内联返回，而是转存至文件系统。这种情况下，使用 `read_file` 分块查看保存的结果；若你需要在转存结果中搜索但不清楚具体路径，可在 `/large_tool_results/` 目录下使用 `grep`。转存的工具结果会存储在 `/large_tool_results/<tool_call_id>` 路径下。

## 执行工具 `execute`

你可以使用 `execute` 工具运行 Shell 命令。
使用该工具运行指令、脚本、测试、构建操作及其他 Shell 操作。
严禁调用该工具执行有害操作，比如删除文件、修改系统设置等，调用前务必确保执行的命令安全且必要。

- execute：运行 Shell 命令，获得命令输出内容与退出码，该工具底层依赖的shell不固定（windows cmd/linux bash），需要运行时检测！
"""

_EXECUTE_TOOL_DESCRIPTION = """
在隔离沙箱环境中执行 Shell 命令。

## 用法
在沙箱环境中执行指定命令，并进行妥善处理与安全防护。
执行命令前，请遵循以下步骤：
1. **目录校验**
   - 若命令将创建新目录或文件，需先使用 `ls` 工具确认父目录已存在且位置正确
   - 示例：执行 `mkdir foo/bar` 前，先用 `ls` 检查 `foo` 目录是否存在且为目标父目录

2. **命令执行**
   - 对包含空格的文件路径**必须用双引号包裹**（如：`cd "path with spaces/file.txt"`）
   - 正确与错误引用示例：
     - `cd "/Users/name/My Documents"`（正确）
     - `cd /Users/name/My Documents`（错误，执行失败）
     - `python "/path/with spaces/script.py"`（正确）
     - `python /path/with spaces/script.py`（错误，执行失败）
   - 确认引用格式无误后，再执行命令
   - 捕获命令执行输出

## 使用说明
- 所有命令均运行在**隔离沙箱环境**中
- 返回标准输出、标准错误的合并内容及退出码
- 若输出内容过大，可能会被截断
- 对于耗时较长的命令，可通过可选参数 `timeout` 覆盖默认超时时间（示例：`execute(command="make build", timeout=300)`）
- 超时时间设为 0 时，可在支持无超时执行的后端中关闭超时限制
- **非常重要**：严禁使用 `find`、`grep` 等搜索类命令，改用内置的 `grep`、`glob` 工具；严禁使用 `cat`、`head`、`tail` 等文件读取工具，改用 `read_file` 读取文件
- 执行多条命令时，用 `;` 或 `&&` 分隔，**禁止使用换行符**（引号字符串内可换行）
  - 命令存在依赖关系时使用 `&&`（示例：`"mkdir dir && cd dir"`）
  - 仅需顺序执行、不关心前置命令是否执行成功时使用 `;`
- 尽量在会话全程保持当前工作目录不变，使用**绝对路径**，避免使用 `cd` 命令

## 示例
### 推荐用法
- `execute(command="pytest /foo/bar/tests")`
- `execute(command="python /path/to/script.py")`
- `execute(command="npm install && npm test")`
- `execute(command="make build", timeout=300)`

### 禁止用法（请勿使用）
- `execute(command="cd /foo/bar && pytest tests")`  # 请改用绝对路径
- `execute(command="cat file.txt")`  # 请改用 `read_file` 工具
- `execute(command="find . -name '*.py'")`  # 请改用 `glob` 工具
- `execute(command="grep -r 'pattern' .")`  # 请改用内置 `grep` 工具

## 备注
仅当后端支持执行功能（SandboxBackendProtocol）时，该工具方可使用。
若不支持命令执行，工具将返回错误信息。
"""

LOCAL_EXECUTE_TOOL_DESCRIPTION = """## 执行工具`execute`

- **检测execute工具底层依赖的Shell 类型**：
    - 先调用execute工具执行 `echo %COMSPEC%`

    - 输出包含 `cmd.exe` → Windows CMD
    - 输出为空或报错 → 可能是 Linux Bash

- **⚠️调用execute工具执行shell命令时的铁律**：

    - **虚拟文件系统工具**（`ls`、`read_file`、`write_file` 等）：出于工具的具体实现，可以使用绝对路径 `/warehouse/...`，这是**特殊情况**
    - **execute 工具**（执行 shell 命令）：**命令中绝对不能**使用以 `/` 开头的绝对路径，必须使用**相对路径**

    - **为什么？**execute 工具最终会启动一个shell终端执行命令，其工作目录是虚拟文件系统根目录，它映射到真实文件系统的某个目录，比如`D:/agentworkspace/`（windows）、`/users/normal_user/agentworkspace/`（linux）。
    如果你在命令中使用 `/warehouse/...`等以 `/` 开头的绝对路径，系统会尝试访问宿主机真实文件系统的根目录或盘根目录下的 warehouse，这很可能会导致"文件未找到"错误
    - 示例：
        - ✅ 正确：`cd "./warehouse/gomoku_game_v1_2026-04-07_10-00/gomoku/tests" && python -m pytest ./ -v`
        - ✅ 正确：`python -m pytest "warehouse/gomoku_game_v1_2026-04-07_10-00/gomoku/tests/test_pytest.py" -v`
        - ❌ 错误：`python -m pytest "/warehouse/gomoku_game_v3_2026-04-09_17-08/gomoku/tests/" -v`
        - ❌ 错误：`python -m pytest "/warehouse/gomoku_game_v3_2026-04-09_17-08/gomoku/tests/test_pytest.py" -v`

- **每次调用 execute 工具前，必须在 <think> 标签中自我检查：**

    1. 我要执行的命令中包含路径吗？
    2. 这个路径是以 `/` 开头的吗？
    3. 如果是，我必须将其改为相对路径（去掉开头的 `/`，或加上 `./` 前缀）
    4. 我是否应该先用 `cd` 切换到目标目录？

    **违反此规则的后果：命令执行失败，浪费迭代次数，可能导致项目终止！**"""

# 3. 关于SubAgentMiddleware
_TASK_PROMPT = """## `task` (subagent spawner)

You have access to a `task` tool to launch short-lived subagents that handle isolated tasks. These agents are ephemeral — they live only for the duration of the task and return a single result.

When to use the task tool:
- When a task is complex and multi-step, and can be fully delegated in isolation
- When a task is independent of other tasks and can run in parallel
- When a task requires focused reasoning or heavy token/context usage that would bloat the orchestrator thread
- When sandboxing improves reliability (e.g. code execution, structured searches, data formatting)
- When you only care about the output of the subagent, and not the intermediate steps (ex. performing a lot of research and then returned a synthesized report, performing a series of computations or lookups to achieve a concise, relevant answer.)

Subagent lifecycle:
1. **Spawn** → Provide clear role, instructions, and expected output
2. **Run** → The subagent completes the task autonomously
3. **Return** → The subagent provides a single structured result
4. **Reconcile** → Incorporate or synthesize the result into the main thread

When NOT to use the task tool:
- If you need to see the intermediate reasoning or steps after the subagent has completed (the task tool hides them)
- If the task is trivial (a few tool calls or simple lookup)
- If delegating does not reduce token usage, complexity, or context switching
- If splitting would add latency without benefit

## Important Task Tool Usage Notes to Remember
- Whenever possible, parallelize the work that you do. This is true for both tool_calls, and for tasks. Whenever you have independent steps to complete - make tool_calls, or kick off tasks (subagents) in parallel to accomplish them faster. This saves time for the user, which is incredibly important.
- Remember to use the `task` tool to silo independent tasks within a multi-part objective.
- You should use the `task` tool whenever you have a complex task that will take multiple steps, and is independent from other tasks that the agent needs to complete. These agents are highly competent and efficient."""  # noqa: E501

MY_TASK_PROMPT = """## 副智能体调用工具`task`

你可以使用 `task` 工具启动子智能体（或者称作‘副智能体’），处理独立隔离的任务。这类智能体有些具备多轮对话记忆，有些并不具备。

### 适用场景
- 任务复杂且步骤繁多，可完全独立委托执行时
- 任务与其他操作相互独立，可并行运行时
- 任务需要专注推理，或会消耗大量 Token/上下文，会导致主协调线程臃肿时
- 沙箱运行可提升可靠性时（如代码执行、结构化搜索、数据格式化）
- 你只关心子智能体的最终输出，而非中间步骤时（例如完成大量调研后返回整合报告，执行一系列计算或查询以得到简洁相关的答案）

### 子智能体生命周期
1. **启动（指派）** → 提供清晰的执行指令与预期输出
2. **运行** → 子智能体自主完成任务
3. **返回** → 子智能体提交单一结构化结果
4. **整合** → 将结果纳入主线程并进行汇总处理

### 不适用场景
- 你需要查看子智能体完成任务后的中间推理或步骤时（该工具会隐藏中间过程）
- 任务极为简单（仅需少量工具调用或简单查询）
- 委托执行无法减少 Token 消耗、复杂度或上下文切换成本时
- 拆分任务只会增加延迟却无实际收益时

## task 工具使用重要注意事项
- 在多个任务无依赖关系时，尽可能并行地调用task工具执行工作。工具调用与指派副智能体完成任务均适用此原则。当存在多个独立步骤时，并行发起工具调用或启动子智能体任务以提升效率。这能为用户节省时间，至关重要。
- 记得使用 `task` 工具隔离多目标任务中的独立子任务。
- 当你遇到一个需要多步骤完成、且与其他待执行任务相独立的复杂任务时，应使用 `task` 工具。这类副智能体能力强、效率高。"""

_TASK_TOOL_DESCRIPTION = """## `task` 工具说明
启动一个临时子代理，在独立上下文窗口中处理复杂、多步骤的独立任务。

可用代理类型及其可调用工具：
{available_agents}

使用 task 工具时，必须指定 `subagent_type` 参数，以选择要使用的代理类型。

## 使用说明
1. 尽可能并发启动多个代理以最大化性能；可通过单条消息发起多次工具调用实现。
2. 代理完成任务后，会返回一条消息给你。代理返回的结果对用户不可见。若要向用户展示结果，需向用户发送文本消息，对结果进行简洁总结。
3. 每次代理调用均为**无状态**。你无法向该代理发送额外消息，代理也无法在最终报告之外与你通信。因此，你的提示词必须包含**高度详细的任务描述**，让代理能够自主完成任务，并明确指定代理在唯一一条返回消息中应传回的信息。
4. 通常可信任代理的输出结果。
5. 明确告知代理你希望其**创作内容、执行分析还是仅做调研**（搜索、读取文件、网络请求等），因为代理无法感知用户意图。
6. 如果某类代理说明中提示应**主动使用**，则你应尽量在用户未主动要求时就自行判断并使用。
7. 当仅提供通用代理时，所有任务均应使用该代理。它非常适合隔离上下文与令牌消耗、完成特定复杂任务，因为它具备与主代理完全相同的能力。

### 通用代理使用示例

<example_agent_descriptions>
"general-purpose"：用于通用任务，可调用与主代理完全相同的所有工具。
</example_agent_descriptions>

<example>
用户：“我想调研勒布朗·詹姆斯、迈克尔·乔丹和科比·布莱恩特的成就，并进行对比。”
助手：*并行使用 task 工具，分别独立调研三位球员*
助手：*整合三份独立调研结果并回复用户*
<commentary>
调研本身就是复杂的多步骤任务。
每位球员的调研互不依赖。
助手通过 task 工具将复杂目标拆分为三个独立任务。
每个调研任务只需关注单一球员的上下文与令牌消耗，最终返回整合后的球员信息作为工具结果。
这使得每个任务都能深入研究、消耗足量令牌与上下文，但最终仅返回精炼信息，长期来看能在对比球员时节省令牌。
</commentary>
</example>

<example>
用户：“分析一个大型代码仓库的安全漏洞并生成报告。”
助手：*启动单个 task 子代理执行仓库分析*
助手：*接收报告并整合为最终总结*
<commentary>
即使只有一个任务，也使用子代理隔离大型、高上下文消耗任务，避免主线程被细节过载。
若用户后续提出追问，可直接参考简洁报告，而非完整分析与工具调用历史，省时且节约成本。
</commentary>
</example>

<example>
用户：“帮我安排两场会议并分别准备议程。”
助手：*并行调用 task 工具，启动两个子代理分别准备议程*
助手：*返回最终日程与议程*
<commentary>
单个任务虽简单，但子代理有助于隔离议程准备工作。
每个子代理只需关注一场会议的议程。
</commentary>
</example>

<example>
用户：“我想在达美乐点披萨、麦当劳点汉堡、赛百味点沙拉。”
助手：*直接并行调用工具完成点餐*
<commentary>
助手未使用 task 工具，因为目标极其简单清晰，仅需少量基础工具调用。
直接完成任务比使用 task 工具更合适。
</commentary>
</example>

### 自定义代理使用示例

<example_agent_descriptions>
"content-reviewer"：在完成大量内容或文档创作后使用该代理进行审核
"greeting-responder"：用于对用户问候进行友好玩笑式回复
"research-analyst"：用于对复杂主题进行深度调研
</example_agent_descriptions>

<example>
用户：“写一个判断数字是否为质数的函数。”
助手：好的，我来写一个判断质数的函数。
助手：首先我用 Write 工具编写判断质数的函数。
助手：我将使用 Write 工具写入如下代码：
<code>
function isPrime(n) {{
  if (n <= 1) return false
  for (let i = 2; i * i <= n; i++) {{
    if (n % i === 0) return false
  }}
  return true
}}
</code>
<commentary>
已完成重要内容创作与任务，现使用 content-reviewer 代理审核成果。
</commentary>
助手：现在我用 content-reviewer 代理审核这段代码。
助手：使用 task 工具启动 content-reviewer 代理。
</example>

<example>
用户：“能否调研不同可再生能源的环境影响，并生成一份综合报告？”
<commentary>
这是复杂调研任务，适合使用 research-analyst 代理开展深度分析。
</commentary>
助手：我将为你调研可再生能源的环境影响。我使用 research-analyst 代理对该主题展开全面研究。
助手：使用 task 工具启动 research-analyst 代理，并提供详细指令，说明调研内容与报告格式。
</example>

<example>
用户：“你好。”
<commentary>
用户发来问候，使用 greeting-responder 代理附带友好笑话进行回复。
</commentary>
助手：“我将使用 task 工具启动 greeting-responder 代理。”
</example>"""  # noqa: E501

MY_TASK_TOOL_DESCRIPTION = """调用该工具指派团队成员完成特定任务。
**任务指派内容（严格遵守）**：

1. 开发类型：绿地开发or棕地开发
2. 当前项目工作空间
3. 本次任务要求，力求简洁。不必向你的团队专家指明文档交付物的输出格式，因为每个团队成员都是专业的。比如：
    - 请进行{{当前任务：比如需求分析、架构设计、系统测试}}，交付《{{文档名：当前文档交付物名称}}.md》
    - 请创建/实现/编写{{filename}}，完成/实现{{coding_task_description：当前编码任务在详细设计文档中的描述}}。
4. 交付物保存地址"""
