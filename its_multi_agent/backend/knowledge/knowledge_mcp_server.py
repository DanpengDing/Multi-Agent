from knowledge_mcp.knowledge_mcp_server import mcp


if __name__ == "__main__":
    print("Knowledge MCP Server starting, default SSE endpoint: http://127.0.0.1:9000/sse")
    mcp.run(transport="sse")
