import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from opentelemetry.trace import get_tracer, SpanKind
from opentelemetry.propagate import extract

from api.routers import router
from infrastructure.logging.logger import logger
from infrastructure.tracing import setup_tracing, get_tracer
from infrastructure.tools.mcp.mcp_manager import mcp_connect, mcp_cleanup


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI应用生命周期管理

    在应用启动时建立MCP连接，在应用关闭时清理连接。
    确保资源正确初始化和释放。
    """
    # 应用启动时执行
    logger.info("应用启动，建立MCP连接...")
    try:
        await mcp_connect()
        logger.info("MCP连接建立完成")
    except Exception as e:
        logger.error(f"MCP连接建立失败: {str(e)}")

    yield  # 应用运行期间（先别释放mcp链接 去处理请求...）

    # 应用关闭时执行
    logger.info("应用关闭，清理MCP连接...")
    try:
        await mcp_cleanup()
        logger.info("MCP连接清理完成")
    except Exception as e:
        logger.error(f"MCP连接清理失败: {str(e)}")


def create_fast_api() -> FastAPI:
    # 初始化链路追踪
    tracer = get_tracer("multi-agent-api")

    # 1. 创建FastApi实例,绑定了生命周期事件
    app = FastAPI(title="Multi-Agent API", lifespan=lifespan)

    # 2. 添加链路追踪中间件
    @app.middleware("http")
    async def tracing_middleware(request: Request, call_next):
        """链路追踪中间件，跟踪每个 HTTP 请求。"""
        tracer = get_tracer("multi-agent-api")

        # 从请求头中提取追踪上下文
        context = extract(request.headers)
        span_name = f"{request.method} {request.url.path}"

        with tracer.start_as_current_span(
            span_name,
            context=context,
            kind=SpanKind.SERVER,
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.host": request.headers.get("host", ""),
                "http.user_agent": request.headers.get("user-agent", ""),
            }
        ) as span:
            try:
                response = await call_next(request)
                span.set_attribute("http.status_code", response.status_code)
                return response
            except Exception as e:
                span.set_attribute("http.status_code", 500)
                span.record_exception(e)
                raise

    # 3. 处理跨域
    app.add_middleware(
        CORSMiddleware,
        # CORSMiddleware 会自动拦截后端的响应 并贴上这些标签 Access-Control-Allow-Origin Access-Control-Allow-Methods Access-Control-Allow-Headers
        allow_origins=["*"],  # 生产环境应限制为特定域名
        allow_credentials=True,  # cookie(自定义的key value)(user_id)
        allow_methods=["*"],  # 任意的请求都可以（POST）
        allow_headers=["*"],  # 请求头中带上自己的信息（token）
    )

    # 4. 注册各种路由
    app.include_router(router=router)

    # 5.返回创建的FastAPI
    return app


if __name__ == '__main__':
    print("1.准备启动Web服务器")
    try:
        uvicorn.run(app=create_fast_api(), host="127.0.0.1", port=8000)

        logger.info("2.启动Web服务器成功...")

    except KeyboardInterrupt as e:
        logger.error(f"2.启动Web服务器失败: {str(e)}")
