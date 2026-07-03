import uuid

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json
from typing import AsyncGenerator, Dict, Any, Optional

from langchain_core.runnables import RunnableConfig


# 自定义 JSON 编码器，处理 LangChain/LangGraph 对象
class LangChainJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        # 处理 AIMessage 等 LangChain 消息对象
        if hasattr(obj, "to_json"):
            return obj.to_json()
        # 处理 ValuesStreamPart 中的特殊对象
        if hasattr(obj, "dict"):
            return obj.dict()
        # 处理其他不可序列化的对象
        try:
            print(f"Attempting to serialize object of type {type(obj)}: {obj}")
            return json.JSONEncoder.default(self, obj)
        except TypeError:
            return str(obj)


# ========== 导入你自己写好的 LangChain Agent ==========
from src.langchain_learning.deep_agents.researcher import (
    researcher_agent,
)
from rich.pretty import pprint

app = FastAPI()

# 跨域配置（前端本地调试必须）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 存储对话线程信息（生产环境应使用数据库）
threads: Dict[str, Dict[str, Any]] = {}


# 创建线程 - LangChain API 标准端点
@app.post("/threads")
async def create_thread():
    thread_id = str(uuid.uuid4())
    threads[thread_id] = {"messages": []}
    return {"thread_id": thread_id}


# 获取线程 - LangChain API 标准端点
@app.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    if thread_id not in threads:
        threads[thread_id] = {"messages": []}
    return {"thread_id": thread_id, "messages": threads[thread_id]["messages"]}


# 发送命令到线程 - LangChain API 标准端点
@app.post("/threads/{thread_id}/commands")
async def send_command(thread_id: str, payload: dict):
    # 确保线程存在
    if thread_id not in threads:
        threads[thread_id] = {"messages": []}

    # 获取用户消息 - 适配 LangChain useStream 的请求格式
    user_msg = ""
    # 前端发送的格式: 
    # {
    # "id": 1, 
    # "method": "run.start", 
    # "params": {"input": {"messages": [...]}, "assistant_id": "Researcher", "config": {"thread_id": thread_id}}}
    params = payload["params"]
    user_msg = params['input']['messages'][-1]['content']
    config = params['config'] # 包含thread_id
    assistant_id = params['assistant_id']

    print(f"对话线程{thread_id}接收到新的用户指令:{user_msg}\n完整payload内容如下:")
    pprint(payload)

    async def event_generator() -> AsyncGenerator[str, None]:
        """逐一流式输出，格式适配 @langchain/react useStream"""
        real_config: RunnableConfig = {
            "tags": [assistant_id],
            **config,
        }
        async for chunk in researcher_agent.astream(
            {"input": user_msg}, config=real_config, stream_mode=["values"], version="v2"
        ):
            # 使用自定义编码器序列化 ValuesStreamPart 对象
            try:
                data = json.dumps(chunk, cls=LangChainJSONEncoder)
                print("成功序列化一个ValuesStreamPart对象，序列化结果如下：")
                pprint(data)
            except Exception as e:
                print(f"序列化一个ValuesStreamPart对象时出错，错误信息如下: {e}")
                continue
            yield f"data: {data}\n\n"

        print("本次ReAct循环结束")
        # 流结束标记
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=2024)
