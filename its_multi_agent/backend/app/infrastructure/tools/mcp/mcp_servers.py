import asyncio
import json
from typing import Any, Dict

from agents.mcp import MCPServerSse

from config.settings import settings


search_mcp_client = MCPServerSse(
    name="通用联网搜索",
    params={
        "url": f"{settings.DASHSCOPE_BASE_URL}",
        "headers": {
            "Authorization": f"Bearer {settings.AL_BAILIAN_API_KEY}",
        },
        "timeout": 60,
        "sse_read_timeout": 60 * 30,
    },
    client_session_timeout_seconds=60 * 10,
    cache_tools_list=True,
)


baidu_mcp_client = MCPServerSse(
    name="百度地图",
    params={
        "url": f"https://mcp.map.baidu.com/sse?ak={settings.BAIDUMAP_AK}",
        "timeout": 60,
        "sse_read_timeout": 60 * 30,
    },
    client_session_timeout_seconds=60 * 10,
    cache_tools_list=True,
)


knowledge_mcp_client = MCPServerSse(
    name="知识库问答",
    params={
        "url": f"{settings.KNOWLEDGE_MCP_URL}",
        "timeout": 60,
        "sse_read_timeout": 60 * 30,
    },
    client_session_timeout_seconds=60 * 10,
    cache_tools_list=True,
)


async def run_mcp_call(
    mcp_instance: MCPServerSse,
    tool_name: str,
    tool_args: Dict[str, Any],
):
    """通用 MCP 调试入口，用于手动查看工具列表并调用指定工具。"""
    server_name = mcp_instance.name
    print(f"\n{'=' * 60}")
    print(f"[测试启动] 服务: {server_name}")
    print(f"{'=' * 60}")

    try:
        print("[连接] 正在连接服务...")
        await mcp_instance.connect()
        print("[连接] 成功")

        print("\n[列表] 正在获取工具列表和参数定义...")
        tools_list = await mcp_instance.list_tools()

        if tools_list:
            print(f"发现 {len(tools_list)} 个工具：")
            for index, tool in enumerate(tools_list, start=1):
                print(f"\n[{index}] 工具名: {tool.name}")
                print(f"描述: {tool.description}")
                print("参数 Schema:")
                print(json.dumps(tool.inputSchema, indent=2, ensure_ascii=False))
        else:
            print("未获取到工具列表")

        print(f"\n{'-' * 40}")
        print(f"发送参数: {json.dumps(tool_args, ensure_ascii=False)}")

        result = await mcp_instance.call_tool(tool_name, tool_args)
        print("\n[响应] 服务端返回结果:")

        for content in result.content:
            if hasattr(content, "text"):
                print(content.text)
            else:
                print(f"[Non-Text] {content}")

    except Exception as exc:
        print(f"\n[异常] 测试失败: {exc}")
        raise
    finally:
        print("\n[断开] 正在清理连接...")
        await mcp_instance.cleanup()
        print(f"{server_name} 测试结束\n")


async def test_knowledge_mcp():
    """测试本地知识库 MCP。"""
    await run_mcp_call(
        mcp_instance=knowledge_mcp_client,
        tool_name="search_knowledge",
        tool_args={"query": "如何使用U盘安装 Windows 7 操作系统？", "top_k": 2},
    )


if __name__ == "__main__":
    asyncio.run(test_knowledge_mcp())
