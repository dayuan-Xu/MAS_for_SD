from pydantic import BaseModel, Field
from rich.pretty import pprint
from src.config.llm import LLMs

class Movie(BaseModel):
    """A movie with details."""
    title: str = Field(description="The title of the movie")
    year: int = Field(description="The year the movie was released")
    director: str = Field(description="The director of the movie")
    rating: float = Field(description="The movie's rating out of 10")


# model_with_structure = LLM_1.with_structured_output(Movie)
# response = model_with_structure.invoke("请用中文提供电影Inception的详细信息")
# pprint(response)  # Movie(title="Inception", year=2010, director="Christopher Nolan", rating=8.8)

# 设置include_raw来额外获取一个AIMessage
model_with_structure = LLMs['gpt-5-nano'].with_structured_output(Movie, include_raw=True)
response = model_with_structure.invoke("请用中文提供电影Inception的详细信息")
pprint(response)
"""
{
│   'raw': AIMessage(
│   │   content='',
│   │   additional_kwargs={'refusal': None},
│   │   response_metadata={
│   │   │   'token_usage': {
│   │   │   │   'completion_tokens': 23,
│   │   │   │   'prompt_tokens': 100,
│   │   │   │   'total_tokens': 123,
│   │   │   │   'completion_tokens_details': {
│   │   │   │   │   'accepted_prediction_tokens': None,
│   │   │   │   │   'audio_tokens': 0,
│   │   │   │   │   'reasoning_tokens': 0,
│   │   │   │   │   'rejected_prediction_tokens': None
│   │   │   │   },
│   │   │   │   'prompt_tokens_details': {
│   │   │   │   │   'audio_tokens': 0,
│   │   │   │   │   'cached_tokens': 0
│   │   │   │   }
│   │   │   },
│   │   │   'model_provider': 'openai',
│   │   │   'model_name': 'gpt-4o-mini-2024-07-18',
│   │   │   'system_fingerprint': 'fp_eb37e061ec',
│   │   │   'id': 'chatcmpl-DJ7QxasrWgFiV4DuWYGmHpR8PuvVV',
│   │   │   'finish_reason': 'stop',
│   │   │   'logprobs': None
│   │   },
│   │   id='lc_run--019ce9ce-f8a1-7e92-b612-2caf3da07bbd-0',
│   │   tool_calls=[
│   │   │   {
│   │   │   │   'name': 'Movie',
│   │   │   │   'args': {
│   │   │   │   │   'title': 'Inception',
│   │   │   │   │   'year': 2010,
│   │   │   │   │   'director': 'Christopher Nolan',
│   │   │   │   │   'rating': 8.8
│   │   │   │   },
│   │   │   │   'id': 'call_232FIqNmBYOsVW4LjacmK7Uh',
│   │   │   │   'type': 'tool_call'
│   │   │   }
│   │   ],
│   │   invalid_tool_calls=[],
│   │   usage_metadata={
│   │   │   'input_tokens': 100,
│   │   │   'output_tokens': 23,
│   │   │   'total_tokens': 123,
│   │   │   'input_token_details': {'audio': 0, 'cache_read': 0},
│   │   │   'output_token_details': {'audio': 0, 'reasoning': 0}
│   │   }
│   ),
│   'parsed': Movie(
│   │   title='Inception',
│   │   year=2010,
│   │   director='Christopher Nolan',
│   │   rating=8.8
│   ),
│   'parsing_error': None
}
"""


# 结构化输出支持嵌套结构
class Actor(BaseModel):
    name: str
    role: str

class MovieDetails(BaseModel):
    title: str
    year: int
    cast: list[Actor]
    genres: list[str]
    budget: float | None = Field(None, description="Budget in millions USD")

model_with_structure = LLMs['gpt-5-nano'].with_structured_output(MovieDetails)
