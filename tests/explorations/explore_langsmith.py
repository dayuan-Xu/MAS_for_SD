# from openai import OpenAI
# from langsmith.wrappers import wrap_openai  # traces openai calls
#
# from src.config.settings import settings
#
#
# def retriever(query: str):
#     return ["Harrison worked at Kensho"]
#
# # 包裹以便实现LangSmith追踪
# client = wrap_openai(OpenAI(api_key=settings.OPENAI_API_KEY,base_url=settings.OPENAI_BASE_URL))  # log traces by wrapping the model calls
#
# def rag(question: str) -> str:
#     docs = retriever(question)
#     system_message = (
#         "Answer the user's question using only the provided information below:\n"
#         + "\n".join(docs)
#     )
#     resp = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             {"role": "system", "content": system_message},
#             {"role": "user", "content": question},
#         ],
#     )
#     return resp.choices[0].message.content
#
# if __name__ == "__main__":
#     print(rag("Where did Harrison work?"))

# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import StrOutputParser
#
# from src.config.llm import LLMs
#
# prompt = ChatPromptTemplate.from_messages([
#     ("system", "You are a helpful AI."),
#     ("user", "{input}")
# ])
#
# # 运行时配置中添加的tags和metadata会被子运行继承，如果子运行本身有tags和metadata，则会合并
# chat_model = LLMs["gpt-4o-mini"].with_config({"tags": ["model-tag"], "metadata": {"model-key": "model-value"}})
# output_parser = StrOutputParser()
#
# # Tags and metadata can be configured with RunnableConfig
# # run name不会被子运行继承
# chain = (prompt | chat_model | output_parser).with_config({"tags": ["config-tag"], "metadata": {"config-key": "config-value"}}).with_config({"run_name": "MyCustomChain"})
#
# chain.invoke({"input": "What is the meaning of life?"})

from langsmith import trace, traceable, Client

@traceable
def foo(x):
    return {"y": x * 2}

@traceable
def bar(y):
    return {"z": y - 1}

client = Client()

inputs = {"x": 1}
with trace(name="foobar", inputs=inputs) as root_run:
    result = foo(**inputs)
    result = bar(**result)
    root_run.outputs = result
    trace_id = root_run.id
    child_runs = root_run.child_runs

# Provide feedback for a trace (a.k.a. a root run)
client.create_feedback(
    key="user_feedback",
    score=1,
    trace_id=trace_id,
    comment="the user said that ..."
)

# Provide feedback for a child run
foo_run_id = [run for run in child_runs if run.name == "foo"][0].id
client.create_feedback(
    key="correctness",
    score=0,
    run_id=foo_run_id,
    # trace_id= is optional but recommended to enable batched and backgrounded
    # feedback ingestion.
    trace_id=trace_id,
)