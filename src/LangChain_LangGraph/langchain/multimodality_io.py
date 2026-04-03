from langchain.messages import HumanMessage

# String content
human_message = HumanMessage("Hello, how are you?")

# Provider-native format (e.g., OpenAI)  可以使用提供商原生的内容块格式创建多模态消息
human_message = HumanMessage(content=[
    {"type": "text", "text": "Hello, how are you?"},
    {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
])

# List of standard content blocks        也可以使用LangChain官方的内容块格式
# 在初始化消息时指定 content_blocks 仍然会填充消息的 content（content就是最终输入给模型的数据）字段，但LangChain为其提供了类型安全的接口。
human_message = HumanMessage(content_blocks=[
    {"type": "text", "text": "Hello, how are you?"},
    {"type": "image", "url": "https://example.com/image.jpg"},
])

"""
在用户输入方面：
Multimodality refers to the ability to work with data that comes in different forms,
such as text, audio, images, and video.
LangChain includes standard types for these data that can be used across providers.
多模态指的是能够处理不同形式的数据，如文本、音频、图像和视频。
LangChain 包含了这些数据的标准类型，可以跨供应商使用。

比如文本+图像输入
# From URL
message = {
    "role": "user",
    "content": [
        {"type": "text", "text": "Describe the content of this image."},
        {"type": "image", "url": "https://example.com/path/to/image.jpg"},
    ]
}

# From base64 data
message = {
    "role": "user",
    "content": [
        {"type": "text", "text": "Describe the content of this image."},
        {
            "type": "image",
            "base64": "AAAAIGZ0eXBtcDQyAAAAAGlzb21tcDQyAAACAGlzb2...",
            "mime_type": "image/jpeg",
        },
    ]
}

# From provider-managed File ID
message = {
    "role": "user",
    "content": [
        {"type": "text", "text": "Describe the content of this image."},
        {"type": "image", "file_id": "file-abc123"},
    ]
}
"""



"""
在解析不同提供商ai消息输出方面，LangChain提供了Standard content blocks  标准内容块
LangChain provides a standard representation for message content that works across providers.
LangChain 为跨服务商的消息内容提供了标准表示。
Message objects implement a content_blocks property 
that will lazily parse the content attribute into a standard, type-safe representation.
For example, messages generated from ChatAnthropic or ChatOpenAI will
include thinking or reasoning blocks in the format of the respective provider, 
but can be lazily parsed into a consistent ReasoningContentBlock representation:
消息对象实现了一个 content_blocks 属性，可以懒惰地解析内容属性，形成标准的类型安全表示。
例如，ChatAnthropic 或 ChatOpenAI （的某些模型具备深度思考模式），生成的消息会包含相应提供者格式的思考或推理块，
但可以懒散地解析成一致的 ReasoningContentBlock 和其他LangChain标准内容块表示（这是LangChain标准下的ReasoningContentBlock）：
[{'type': 'reasoning', 'id': 'rs_abc123', 'reasoning': 'summary 1'},
 {'type': 'reasoning', 'id': 'rs_abc123', 'reasoning': 'summary 2'},
 {'type': 'text', 'text': '...', 'id': 'msg_abc123'}]
 

# 流式输出各种模型生成的内容块
for chunk in model.stream("What color is the sky?"):
    for block in chunk.content_blocks:
        if block["type"] == "reasoning" and (reasoning := block.get("reasoning")):
            print(f"Reasoning: {reasoning}")
        elif block["type"] == "tool_call_chunk":
            print(f"Tool call chunk: {block}")
        elif block["type"] == "text":
            print(block["text"])
        else:
            ...

# 流式输出模型的推理内容块，如果没有推理内容块，那就输出普通文本内容块
for chunk in model.stream("Why do parrots have colorful feathers?"):
    reasoning_steps = [r for r in chunk.content_blocks if r["type"] == "reasoning"]
    print(reasoning_steps if reasoning_steps else chunk.text)
    
"""
