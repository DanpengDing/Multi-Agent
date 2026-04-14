from setuptools import setup, find_packages

setup(
    name="knowledge",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "requests",
        "python-dotenv",
        "langchain-core",
        "langchain-community",
        "langchain-openai",
        "langchain-chroma",
        "pydantic-settings",
        "markdownify",
        "scikit-learn",
        "jieba",
        "unstructured",
        "markdown",
        "python-multipart",
        "mcp",
    ],
)
