"""
应用配置管理模块。

使用 pydantic-settings 统一管理环境变量和 .env 配置，
避免在各个模块里重复读取配置。
"""

from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


class Settings(BaseSettings):
    """应用配置类。"""

    SF_API_KEY: Optional[str] = Field(default=None, description="硅基流动 API Key")
    SF_BASE_URL: Optional[str] = Field(default=None, description="硅基流动 Base URL")

    AL_BAILIAN_API_KEY: Optional[str] = Field(
        default=None,
        description="阿里百炼 API Key",
    )
    AL_BAILIAN_BASE_URL: Optional[str] = Field(
        default=None,
        description="阿里百炼 Base URL",
    )

    MAIN_MODEL_NAME: Optional[str] = Field(
        default="Qwen/Qwen3-32B",
        description="主模型名称",
    )
    SUB_MODEL_NAME: Optional[str] = Field(
        default="",
        description="子模型名称",
    )

    MYSQL_HOST: Optional[str] = Field(default="localhost", description="MySQL 主机地址")
    MYSQL_PORT: int = Field(default=3306, description="MySQL 端口")
    MYSQL_USER: Optional[str] = Field(default="root", description="MySQL 用户名")
    MYSQL_PASSWORD: Optional[str] = Field(default="", description="MySQL 密码")
    MYSQL_DATABASE: Optional[str] = Field(default="multi_agent_db", description="MySQL 数据库名")
    MYSQL_CHARSET: str = Field(default="utf8mb4", description="MySQL 字符集")
    MYSQL_CONNECT_TIMEOUT: int = Field(default=10, description="MySQL 连接超时秒数")
    MYSQL_MAX_CONNECTIONS: int = Field(default=5, description="MySQL 最大连接数")

    KNOWLEDGE_BASE_URL: Optional[str] = Field(
        default=None,
        description="知识库 HTTP 服务地址",
    )
    KNOWLEDGE_MCP_URL: Optional[str] = Field(
        default="http://127.0.0.1:9000/sse",
        description="本地知识库 MCP 的 SSE 地址",
    )
    DASHSCOPE_BASE_URL: Optional[str] = Field(
        default=None,
        description="通义千问 DashScope Base URL",
    )
    DASHSCOPE_API_KEY: Optional[str] = Field(
        default="sk-26d57c968c364e7bb14f1fc350d4bff0",
        description="通义千问 DashScope API Key",
    )
    BAIDUMAP_AK: Optional[str] = Field(
        default=None,
        description="百度地图 AK",
    )

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        validate_default=True,
    )

    @model_validator(mode="after")
    def check_ai_service_configuration(self) -> Self:
        """至少保证配置了一个可用的 AI 服务。"""
        has_service = any(
            [
                self.SF_API_KEY and self.SF_BASE_URL,
                self.AL_BAILIAN_API_KEY and self.AL_BAILIAN_BASE_URL,
            ]
        )

        if not has_service:
            raise ValueError("必须至少配置一个 AI 服务（硅基流动或阿里百炼）")

        return self


settings = Settings()
