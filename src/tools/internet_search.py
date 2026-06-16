from typing import Literal

from langchain_core.tools import tool
from rich.pretty import pprint
from tavily import TavilyClient

from src.config.settings import settings

tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)


@tool
def internet_search(
        query: str,
        max_results: int = 5,
        topic: Literal["general", "news", "finance"] = "general",
        include_raw_content: bool = False,
):
    """Run a web search"""
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )


if __name__ == "__main__":
    pprint(internet_search.invoke("大连今日天气如何?"))
