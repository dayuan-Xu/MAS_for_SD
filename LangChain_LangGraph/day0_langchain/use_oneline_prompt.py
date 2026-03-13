import json
from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langsmith import Client
# 覆盖式加载环境变量
load_dotenv(override=True)
client = Client()
# 拉取 prompt
prompt = client.pull_prompt("homanp/superagent")

# 查看 prompt 需要的输入变量
print(f"Prompt 需要的输入变量：{prompt.input_variables}")

# 查看该prompt包含哪些消息
print(f"该prompt包含以下消息：{prompt.messages}")

# 创建 LLM 和解析器
from agents_quickstart_1 import llm
output_parser = StrOutputParser()

# 构建链
chain = prompt | llm | output_parser

# 使用示例
# 注意：根据 prompt.input_variables 的内容调整传入的参数
# 如果只有一个变量，可以直接传值

tools = [{
        "name": "get_weather_for_location",
        "description": "Get weather for a given city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city for which to get the weather."
                }
            },
            "required": ["city"]
        }
}]

output_format = {
  "workflow": "Generate Prompt and Replicate Image",
  "steps": [
    {
      "name": "Tool name 1",
      "function": "function_runner_1",
      "input_schema": {
        "query": "string"
      },
      "ouput_key": "result_1"
    },
    {
      "name": "Function 2",
      "function": "function_runner_2",
      "input_schema": {
        "input": "<result_1>"
      },
      "output_key": "result_2"
    }
  ]
}

response = chain.invoke({
    "tools": json.dumps(tools),
    "output_format":json.dumps(output_format),
    "input": "what is the weather in sf"
})

print(response)

# 或者如果有多个变量，需要传字典
# response = chain.invoke({
#     "variable1": "值 1",
#     "variable2": "值 2"
# })
