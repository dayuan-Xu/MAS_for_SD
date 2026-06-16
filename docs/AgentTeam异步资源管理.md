# AgentTeam 异步资源管理指南

## 🎯 问题背景

之前使用 AgentTeam 时，需要手动调用 `sandbox.delete_session()` 来清理沙盒会话，否则会导致：
- 云端资源浪费
- 会话超时后无法下载成果物
- 需要记住在每个退出点都调用清理代码

## ✅ 解决方案：异步上下文管理器

现在 `AgentTeam` 支持 Python 的 `async with` 语句，可以**自动管理资源生命周期**。

---

## 📖 使用方式对比

### ❌ 旧方式（需要手动清理）

```python
async def old_way():
    # 1. 创建团队
    dev_team = await AgentTeam.create_with_agentbay_mcp(
        task_name="My Task",
        enable_brown=True
    )
    
    try:
        # 2. 执行任务
        result = await dev_team.ainvoke({...})
        
        # 3. 手动下载成果物
        dev_team.sandbox.download_task_artifacts(local_dir)
        
    except Exception as e:
        logger.error(f"任务失败: {e}")
        raise
    
    finally:
        # 4. ⚠️ 必须手动清理（容易忘记！）
        dev_team.sandbox.delete_session()
```

**问题：**
- 需要在每个退出点都记得调用 `delete_session()`
- 如果忘记调用，会导致资源泄漏
- 代码冗长，容易出错

---

### ✅ 新方式（自动清理，推荐）

```python
async def new_way():
    # 1. 使用 async with 自动管理资源
    async with await AgentTeam.create_with_agentbay_mcp(
        task_name="My Task",
        enable_brown=True
    ) as dev_team:
        
        # 2. 执行任务
        result = await dev_team.ainvoke({...})
        
        # 3. ✅ 无需手动清理！退出 async with 块时自动：
        #    - 下载成果物到本地
        #    - 删除沙盒会话
        #    - 记录日志
    
    # 4. 即使发生异常，也会自动清理
```

**优势：**
- ✅ 自动清理，不会遗漏
- ✅ 代码简洁，易于维护
- ✅ 异常安全，保证资源释放
- ✅ 符合 Python 最佳实践

---

## 🔧 工作原理

当你使用 `async with` 时：

```python
async with await AgentTeam.create_with_agentbay_mcp(...) as dev_team:
    # ... 你的代码 ...
    pass
# ← 退出这里时自动触发 __aexit__
```

**自动执行的清理步骤：**

1. **下载成果物**：将云端沙盒中的文件下载到本地仓库
2. **删除会话**：调用 `sandbox.delete_session()` 释放云端资源
3. **记录日志**：详细记录清理过程
4. **异常处理**：即使发生错误，也会尽力清理

---

## 📝 完整示例

### 示例 1：获取检查点消息

```python
async def get_messages():
    setup_logging(task_name="Agent test")

    # ✅ 使用 async with 自动管理资源
    async with await AgentTeam.create_with_agentbay_mcp(
        task_name="Agent test",
        enable_brown=True
    ) as dev_team:
        
        agent = dev_team.planner
        
        config = {
            "configurable": {
                "thread_id": dev_team.thread_id,
                "checkpoint_ns": ""
            }
        }
        
        checkpoint = await agent.aget_state(config)
        
        if checkpoint and 'messages' in checkpoint.values:
            messages = checkpoint.values['messages']
            print(f"✅ 成功获取 {len(messages)} 条消息")
            pprint(messages)
        
    # ✅ 退出时自动清理，无需手动调用 delete_session()
```

### 示例 2：多轮对话

```python
async def talk_with_agent():
    setup_logging(task_name="Chat Task")

    async with await AgentTeam.create_with_agentbay_mcp(
        task_name="Chat Task",
        enable_brown=False
    ) as dev_team:
        
        agent = dev_team.planner
        
        run_config = {
            "configurable": {
                "thread_id": str(uuid.uuid4()),
                "checkpoint_ns": dev_team.team_type
            }
        }
        
        # 启动多轮对话
        await async_multi_turn_conversation(agent, run_config, dev_team.sandbox)
        
    # ✅ 对话结束后自动清理
```

### 示例 3：自动化开发任务

```python
async def auto_develop_task(task: Task):
    start_time = time.time()
    
    async with await AgentTeam.create_with_agentbay_mcp(
        task_name=task.name,
        team_type="simple",
        enable_brown=True
    ) as dev_team:
        
        # 执行多轮 ReAct 循环
        await multi_react_loop(
            task,
            dev_team,
            recursion_limit=10_000
        )
        
        elapsed_time = time.time() - start_time
        return {
            'task_name': task.name,
            'success': True,
            'elapsed_time': elapsed_time
        }
    
    # ✅ 任务完成后自动清理
```

---

## ⚠️ 注意事项

### 1. 异常处理

即使发生异常，`async with` 也会尝试清理资源：

```python
async def safe_usage():
    async with await AgentTeam.create_with_agentbay_mcp(...) as dev_team:
        # 即使这里抛出异常
        raise ValueError("Something went wrong")
    
    # ✅ 仍然会执行清理（下载成果物 + 删除会话）
```

### 2. 提前退出

如果需要提前退出，可以使用 `return` 或 `break`：

```python
async def early_exit():
    async with await AgentTeam.create_with_agentbay_mcp(...) as dev_team:
        
        if some_condition:
            return  # ✅ 退出时仍会清理
        
        # 继续执行...
```

### 3. 嵌套使用

可以嵌套使用多个 `async with`：

```python
async def nested_usage():
    async with await AgentTeam.create_with_agentbay_mcp(task_name="Task1") as team1:
        async with await AgentTeam.create_with_agentbay_mcp(task_name="Task2") as team2:
            # 两个团队都会自动管理
            pass
        # team2 清理
    # team1 清理
```

---

## 🎉 总结

| 特性 | 旧方式 | 新方式 (async with) |
|------|--------|---------------------|
| 代码复杂度 | 高（需要 try-finally） | 低（自动管理） |
| 资源泄漏风险 | 高（容易忘记清理） | 无（自动清理） |
| 异常安全性 | 需要手动处理 | 自动保证 |
| 可维护性 | 差 | 好 |
| 推荐程度 | ❌ 不推荐 | ✅ **强烈推荐** |

**建议：** 所有新代码都应该使用 `async with` 方式来管理 AgentTeam 资源！
