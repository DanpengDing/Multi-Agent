from infrastructure.logging.logger import logger
from infrastructure.tools.mcp.mcp_servers import (
    baidu_mcp_client,
    knowledge_mcp_client,
    search_mcp_client,
)


async def mcp_connect():
    # 单个 MCP 连不上时，只记录日志，不阻塞其他 MCP 初始化。
    try:
        await baidu_mcp_client.connect()
        logger.info("百度地图 MCP 连接成功")
    except Exception as e:
        logger.error("百度地图 MCP 连接失败: %s", str(e))

    try:
        await search_mcp_client.connect()
        logger.info("搜索 MCP 连接成功")
    except Exception as e:
        logger.error("搜索 MCP 连接失败: %s", str(e))

    try:
        await knowledge_mcp_client.connect()
        logger.info("知识库 MCP 连接成功")
    except Exception as e:
        logger.error("知识库 MCP 连接失败: %s", str(e))


async def mcp_cleanup():
    # 清理阶段失败不应覆盖主流程结果，所以这里只记 warning。
    try:
        await baidu_mcp_client.cleanup()
    except Exception as e:
        logger.warning("百度地图 MCP 清理时出现非致命错误: %s", e)

    try:
        await search_mcp_client.cleanup()
    except Exception as e:
        logger.warning("搜索 MCP 清理时出现非致命错误: %s", e)

    try:
        await knowledge_mcp_client.cleanup()
    except Exception as e:
        logger.warning("知识库 MCP 清理时出现非致命错误: %s", e)
