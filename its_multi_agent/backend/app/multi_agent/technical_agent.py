from agents import Agent, ModelSettings, RunConfig, Runner

from infrastructure.ai.openai_client import sub_model
from infrastructure.ai.prompt_loader import load_prompt
from infrastructure.tools.local.knowledge_base import query_knowledge
from infrastructure.tools.mcp.mcp_servers import knowledge_mcp_client, search_mcp_client


technical_agent = Agent(
    name="资讯与技术专家",
    instructions=load_prompt("technical_agent"),
    model=sub_model,
    model_settings=ModelSettings(temperature=0),
    tools=[query_knowledge],
    mcp_servers=[search_mcp_client, knowledge_mcp_client],
)


async def run_single_test(case_name: str, input_text: str):
    """单条测试入口，便于手动验证技术 Agent 的工具选择。"""
    print(f"\n{'=' * 80}")
    print(f"测试用例: {case_name}")
    print(f"输入: \"{input_text}\"")
    print("-" * 80)
    try:
        await search_mcp_client.connect()
        await knowledge_mcp_client.connect()
        print("思考中...")
        result = await Runner.run(
            technical_agent,
            input=input_text,
            run_config=RunConfig(tracing_disabled=True),
        )
        print(f"\n\nAgent 的最终输出: {result.final_output}")
    except Exception as e:
        print(f"\n异常: {e}\n")
    finally:
        try:
            await search_mcp_client.cleanup()
        except Exception:
            pass

        try:
            await knowledge_mcp_client.cleanup()
        except Exception:
            pass


async def main():
    test_cases = [
        ("Case 1: 知识库问答", "如何使用U盘安装 Windows 7 操作系统？"),
    ]

    for name, question in test_cases:
        await run_single_test(name, question)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
