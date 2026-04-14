"""
OpenTelemetry 链路追踪配置模块。

提供分布式追踪能力，跟踪请求在各个 Agent 间的流转。
"""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.trace import Tracer
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.propagate import set_global_textmap

# 服务名称
SERVICE_NAME_VALUE = "multi-agent-service"
SERVICE_VERSION = "1.0.0"


def setup_tracing(service_name: str = SERVICE_NAME_VALUE) -> Tracer:
    """
    初始化 OpenTelemetry 链路追踪。

    Args:
        service_name: 服务名称

    Returns:
        配置好的 Tracer 实例
    """
    # 创建资源
    resource = Resource.create({
        SERVICE_NAME: service_name,
        SERVICE_VERSION: SERVICE_VERSION,
    })

    # 创建追踪提供者
    provider = TracerProvider(resource=resource)

    # 添加控制台导出器（开发环境使用，生产环境可替换为 OTLP 导出器）
    console_exporter = ConsoleSpanExporter()
    span_processor = BatchSpanProcessor(console_exporter)
    provider.add_span_processor(span_processor)

    # 设置全局追踪提供者
    trace.set_tracer_provider(provider)

    # 设置全局文本映射传播器（用于跨服务追踪）
    propagator = TraceContextTextMapPropagator()
    set_global_textmap(propagator)

    # 返回 tracer
    tracer = trace.get_tracer(service_name)

    return tracer


def get_tracer(name: str = SERVICE_NAME_VALUE) -> Tracer:
    """
    获取已配置的 Tracer。

    Args:
        name: tracer 名称

    Returns:
        Tracer 实例
    """
    return trace.get_tracer(name)


# 全局 tracer 实例
tracer = setup_tracing()
