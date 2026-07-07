from openai import APIStatusError
import datetime
import json
import logging
from typing import AsyncGenerator
from agentbay import AsyncSession
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.runnables import RunnableConfig

from backend.app.dao.task_dao import TaskDAO
from backend.app.schemas.task_execute import (
    DestroySessionRequest,
    StartTaskRequest,
    CancelSessionRequest,
    SSEAgentMessage,
    SSESystemMessage,
    SSEErrorMessage,
)
from backend.app.services.agent_team import AgentTeam
from backend.app.services.agent_team_session_manager import session_manager
from backend.app.services.custom_agent_middleware.human_cancel import (
    TaskCancelledException,
)


logger = logging.getLogger(__name__)


async def start_task_execution(
    db: AsyncSession, task_id: int, request: StartTaskRequest
):
    #  查询数据库获知任务名名称
    task = await TaskDAO.get_by_id(db, task_id)  # type: ignore
    if task is None:
        return {"success": False, "msg": "Task not found"}
    task_name = task.name
    try:
        async with await AgentTeam.create_with_agentbay_mcp(
            task_name=task.name,
            # thread_id: ThreadModel.thread_id（LangGraph线程ID，字符串类型），用于棕地开发恢复会话
            thread_id=request.thread_id if request.thread_id else None,
            db=db,
        ) as dev_team:
            # dev_team.thread_id: LangGraph线程ID（字符串类型），可能是新生成的或从数据库恢复的
            thread_id = dev_team.thread_id

            config_across_react_loop: RunnableConfig = {
                "tags": [f"{task_name}", f"{dev_team.team_type}"],
                "recursion_limit": 10_000,
                "configurable": {
                    # thread_id: LangGraph线程ID（字符串类型），用于LangGraph状态管理
                    "thread_id": thread_id,
                    "checkpoint_ns": dev_team.team_type,  # ⭐ 可选：为 Leader/Planner 设置 namespace
                },
            }

            input_text = request.user_input

            dev_input = {"messages": [{"role": "user", "content": input_text}]}

            current_timestamp = datetime.datetime.now().strftime("%H:%M")

            run_config = {
                **config_across_react_loop,
                "run_name": f"{task_name}_{current_timestamp}",
            }

            logger.info(
                "=" * 20
                + f" 开启一次 ReAct 循环: {task_name}_{current_timestamp} "
                + "=" * 20
            )

            # 使用异步调用（一次ainvoke就是一个完整的ReAct loop）
            await dev_team.ainvoke(input=dev_input, config=run_config)

            return {
                "success": True,
                "msg": "ReAct 循环执行成功",
            }
    except TaskCancelledException as e:
        return {
            "success": True,
            "msg": "用户成功取消了 ReAct 循环",
        }

    except Exception as e:
        if "沙盒会话已被主动提前断开" in str(
            e
        ) or "沙盒会话即将达到最大运行时间限制" in str(e):
            return {
                "success": False,
                "msg": str(e),
            }
        else:
            raise e


def _build_graph_input_and_run_config(request, task_name, thread_id, dev_team):
    config_across_react_loop: RunnableConfig = {
        "tags": [f"{task_name}", f"{dev_team.team_type}"],
        "recursion_limit": 10_000,
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": dev_team.team_type,
        },
    }
    dev_input = {"messages": [{"role": "user", "content": request.user_input}]}
    run_config = {
        **config_across_react_loop,
        "run_name": f"{task_name}_{datetime.datetime.now().strftime('%H:%M')}",
    }

    return dev_input, run_config


async def start_task_execution_sse(
    db: AsyncSession, task_id: int, request: StartTaskRequest
):
    """SSE流式执行，返回结构化消息给前端"""
    task = await TaskDAO.get_by_id(db, task_id)
    if task is None:
        yield SSEErrorMessage(message="Task not found").model_dump()
        return

    task_name = task.name
    # thread_id: ThreadModel.thread_id（LangGraph线程ID，字符串类型），用于棕地开发恢复会话；为空时创建新会话
    thread_id = request.thread_id if request.thread_id else None
    dev_team = None

    if thread_id:
        # 根据 ThreadModel.thread_id（LangGraph线程ID，字符串类型）查找已存在的会话
        dev_team = await session_manager.get_agent_team(thread_id=thread_id)

    if dev_team is None:
        yield SSESystemMessage(
            thread_id=thread_id,
            message="开始创建沙盒...",
        ).model_dump()

        try:
            dev_team = await session_manager.create_agent_team(
                task_name=task_name,
                thread_id=thread_id,
                db=db,
            )

        except Exception as e:
            yield SSEErrorMessage(
                thread_id=thread_id,
                message="创建沙盒和智能体团队会话失败，错误信息为：" + str(e),
            ).model_dump()
            return

        else:
            yield SSESystemMessage(
                thread_id=dev_team.thread_id,
                message="沙盒创建完成，智能体团队创建成功",
            ).model_dump()

    # 更新为实际的 LangGraph线程ID（字符串类型），可能是新生成的或从数据库恢复的
    thread_id = dev_team.thread_id

    _, acquired = await session_manager.try_acquire_session(thread_id)
    if not acquired:
        yield SSESystemMessage(
            thread_id=thread_id,
            message="当前线程正在执行中，暂时无法及时处理最新的用户消息，请 稍后再试（等待其执行完毕） 或 手动中止其当前执行",
        ).model_dump()
        return

    # 成功获取到当前AgentTeamSession的使用权，当前AgentTeamSession进入运行状态，其内部的AgentTeam进入运行状态
    # 重置中止标志，确保新一轮执行不受上一轮中止状态的影响
    session = session_manager.sessions[thread_id]
    session.cancel_event.clear()
    msg_ids_sent_to_frontend = session.msg_ids_sent_to_frontend

    dev_input, run_config = _build_graph_input_and_run_config(
        request, task_name, thread_id, dev_team
    )
    try:
        async for stream_part in dev_team.astream(
            input=dev_input,
            config=run_config,
            stream_mode=["values"],
            subgraphs=True,
            version="v2",
        ):
            namespace = stream_part.get("ns", ())
            data = stream_part.get("data", {})
            messages = data.get("messages", [])

            for msg in messages:
                if msg.id not in msg_ids_sent_to_frontend:
                    msg_ids_sent_to_frontend.add(msg.id)
                    yield SSEAgentMessage(
                        thread_id=thread_id,
                        agent_name=(namespace[0] if namespace else "alice"),
                        message=msg.model_dump(),
                    ).model_dump()

        yield SSESystemMessage(
            thread_id=thread_id,
            message="智能体团队本轮运行结束",
        ).model_dump()

    except TaskCancelledException:
        logger.info(
            f"智能体团队本轮运行因用户中止而结束，thread_id={thread_id}"
        )
        yield SSESystemMessage(
            thread_id=thread_id,
            message="智能体团队本轮运行已中止",
        ).model_dump()

    except APIStatusError as e:
        # 检查是否为余额不足等客户端错误
        is_insufficient_balance = False
        status_code = getattr(e, "status_code", None)
        if status_code == 402:
            is_insufficient_balance = True

        if is_insufficient_balance:
            logger.error(
                f"智能体团队本轮运行因余额不足而结束，thread_id={thread_id}",
                exc_info=True,
            )
            yield SSESystemMessage(
                thread_id=thread_id,
                message="❌ 模型 API 余额不足，智能体团队本轮运行已停止，请充值后重新启动任务",
            ).model_dump()
        else:
            logger.error(
                f"LLM API客户端错误，thread_id={thread_id}",
                exc_info=True,
            )
            yield SSESystemMessage(
                thread_id=thread_id,
                message="❌ LLM API客户端错误，智能体团队本轮运行已停止，请检查LLM API相关配置后重新启动任务",
            ).model_dump()
            
    except Exception as e:
            logger.error(
                "本轮AgentTeam执行过程中出现未预料的异常，具体异常信息如下：\n" + str(e),
                exc_info=True,
            )
            yield SSEErrorMessage(
                thread_id=thread_id,
                message=str(e),
            ).model_dump()

    finally:
        # 无论本次AgentTeam的运行是否成功结束，都释放当前协程对于该AgentTeamSession的使用权
        # 但是还不急销毁该AgentTeamSession
        await session_manager.release_session(thread_id)


async def cancel_agent_team_session(db: AsyncSession, request: CancelSessionRequest):
    """请求中止正在运行的智能体团队执行

    设置中止标志后，智能体将在下次模型调用前检测到标志并优雅停止。
    """
    thread_id = request.thread_id
    if not thread_id:
        return {"success": False, "msg": "缺少thread_id"}

    try:
        success = await session_manager.request_cancel(thread_id)
        if success:
            return {"success": True, "msg": "已发送中止信号，智能体将在当前模型调用前停止"}
        else:
            return {"success": False, "msg": "当前线程未在运行，无需中止"}
    except Exception as e:
        logger.error(e, exc_info=True)
        return {"success": False, "msg": str(e)}


async def destroy_agent_team_session(db: AsyncSession, request: DestroySessionRequest):
    """销毁和某条thread相关的智能体团队会话

    注意：前端发起该请求时，相应的智能体团队必须处于非运行状态！
    """
    thread_id = request.thread_id
    if not thread_id:
        return {"success": False, "msg": "缺少thread_id"}

    try:
        is_running = await session_manager.is_session_running(thread_id)
        if is_running:
            return {
                "success": False,
                "msg": "当前线程正在执行中（正在处理上一条用户消息），请 等待其执行完成后 或者 手动中止其执行后 再点击销毁按钮",
            }

        await session_manager.destroy(thread_id)
        return {"success": True, "msg": "沙盒已销毁，任务已停止"}
    except Exception as e:
        logger.error(e, exc_info=True)
        return {"success": False, "msg": str(e)}


async def sse_event_generator(
    db: AsyncSession, task_id: int, request: StartTaskRequest
) -> AsyncGenerator[str, None]:
    """生成 SSE 事件流"""
    try:
        async for msg_dict in start_task_execution_sse(db, task_id, request):
            sse_chunk = f"data: {json.dumps(msg_dict, ensure_ascii=False)}\n\n"
            logger.info(
                "=" * 20 + "\n本次即将推送到前端的SSE chunk内容如下：\n" + sse_chunk
            )
            yield sse_chunk
    except GeneratorExit:
        logger.error("SSE 连接被前端关闭")
    except Exception as e:
        logger.error(f"SSE 推送过程中出现异常: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error_message', 'message': str(e)}, ensure_ascii=False)}\n\n"
