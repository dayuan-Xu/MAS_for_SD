import logging

from langchain_mcp_adapters.client import MultiServerMCPClient

from src.config.settings import settings
from src.dev_team.team_config import AGENTBAY_MCP_SERVER_NAME
from src.utils.mcp_interceptors import MCPMonitorInterceptor, UnicodeDecodeInterceptor

logger = logging.getLogger(__name__)


def get_excluded_tools():
    sandbox_tools = {
        "create_sandbox",  # 沙盒层面的工具
        "get_sandbox_url",
        "system_screenshot",
        "kill_sandbox"
    }

    # 与LangChain文件系统中间件重合的工具
    redundant_tools = {
        "read_file", "write_file", "edit_file", "copy_file", "move_file",
        "create_directory", "search_file", "list_directory", "read_multiple_files",
        "shell",  # 和sandbox backend提供的execute工具重合
        "run_code",
        "start_ChromeByCDP", "stopChrome",  # Chrome DevTools Protocol相关工具，功能太过低级，不如browser use封装的 playright 工具
    }

    too_large_returns_tools = {
        "browser_take_screenshot", "browser_snapshot",
        "page_use_screenshot", "screenshot",  # 返回大段base64编码后的字符串的工具
    }

    useless_tools = {
        "get_file_change",
        "get_file_info"
        "get_metrics"
    }

    dangerous_tools = {
        "delete_file",  # 危险工具
    }

    my_excluded_tools = sandbox_tools | redundant_tools | too_large_returns_tools | useless_tools | dangerous_tools
    return my_excluded_tools


async def load_wuying_mcp_tools(image_id: str,
                                mcp_tool_name_prefix: bool = True,
                                excluded_tools: set[str] | None = None,
                                included_tools: set[str] | None = None,
                                enable_monitor: bool = False,  # 默认不启用监控拦截器，避免过多日志输出
                                monitor_tool_names: set[str] | None = None,
                                monitor_log_level: str = "INFO",
                                decode_unicode: bool = True,  # 默认启用Unicode解码拦截器，将返回结果中的Unicode编码解码为LLM可读文本
                                unicode_decode_tool_names: set[str] | None = None,
                                ) -> list:
    """异步加载 Wuying MCP 服务器提供的工具。

    Args:
        image_id: 镜像ID
        mcp_tool_name_prefix: 是否为MCP工具名称添加前缀
        excluded_tools: 要排除的工具名称集合
        included_tools: 要包含的工具名称集合（如果指定，则只保留这些工具）
        enable_monitor: 是否启用MCP工具执行监控拦截器
        monitor_tool_names: 需要监控的工具名称集合。如果为None且enable_monitor=True，则监控所有工具
        monitor_log_level: 监控日志级别，默认为"INFO"
        decode_unicode: 是否启用Unicode解码拦截器，将返回结果中的Unicode转义字符解码为可读文本
        unicode_decode_tool_names: 需要应用Unicode解码的工具名称集合。如果为None且decode_unicode=True，则应用于所有工具


    Returns:
        list: 过滤后的 MCP 工具列表
    """
    mcp_image_id = image_id
    logger.info(f"开始加载 Wuying MCP 服务器工具，加载自IMAGEID= {image_id}")

    try:
        # 创建拦截器列表
        tool_interceptors = []

        # 1. 添加监控拦截器（如果需要）
        if enable_monitor:
            monitor_interceptor = MCPMonitorInterceptor(
                tool_names=monitor_tool_names,
                log_level=monitor_log_level
            )
            tool_interceptors.append(monitor_interceptor)
            logger.info(f"已启用MCP工具执行监控拦截器 (日志级别: {monitor_log_level})")

        # 2. 添加Unicode解码拦截器（如果需要）
        if decode_unicode:
            interceptor = UnicodeDecodeInterceptor()
            tool_interceptors.append(interceptor)
            logger.info("已启用Unicode解码拦截器")

        client = MultiServerMCPClient(
            {
                AGENTBAY_MCP_SERVER_NAME: {
                    "transport": "http",
                    "url": f"https://agentbay.wuying.aliyuncs.com/v2/mcp?APIKEY={settings.WUYING_AGENTBAY_API_KEY}&IMAGEID={mcp_image_id}",
                }
            },
            tool_interceptors=tool_interceptors if tool_interceptors else None,  # 添加拦截器
            tool_name_prefix=mcp_tool_name_prefix,  # 启用MCP工具名前缀，会将'MCP服务器名称_'作为MCP工具名前缀
        )
        tools = await client.get_tools()

        logger.info(
            f"从 MCP 服务器获取到 {len(tools)} 个原始工具")
        logger.debug(f"原始工具名称: {[tool.name for tool in tools]}")

        # 应用工具过滤

        # 1. 如果指定了 included_tools，只保留这些工具
        if included_tools:
            tools = [
                tool for tool in tools
                if tool.name in included_tools
            ]
            logger.info(f"按包含列表过滤后剩余 {len(tools)} 个工具")

        # 2. 如果指定了 excluded_tools，排除这些工具
        if excluded_tools:
            original_count = len(tools)
            tool_names_to_be_excluded = [
                tool.name for tool in tools
                if tool.name in excluded_tools
            ]
            logger.info(f"将排除以下MCP工具：\n{tool_names_to_be_excluded}")

            # 保留不需要排除的MCP工具
            tools = [
                tool for tool in tools
                if tool.name not in tool_names_to_be_excluded
            ]

            excluded_count = original_count - len(tools)
            if excluded_count > 0:
                logger.info(f"排除了 {excluded_count} 个工具，剩余 {len(tools)} 个工具")

        logger.info(
            f"✅ 成功加载 {len(tools)} 个 Wuying MCP 工具（已过滤），本次加载的MCP工具由 AgentBay Image（ID={mcp_image_id}）提供")
        logger.debug(f"最终工具名称: {[tool.name for tool in tools]}")
        return tools
    except Exception as e:
        logger.error(f"❌ 加载 Wuying MCP 工具失败: {e}", exc_info=True)
        logger.warning("将不使用 Wuying MCP 工具，继续初始化")
        return []
