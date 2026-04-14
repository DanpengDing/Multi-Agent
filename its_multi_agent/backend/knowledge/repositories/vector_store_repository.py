import logging
from typing import List, Optional

import requests
from langchain_chroma import Chroma
from langchain_core.documents import Document

from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DashScopeEmbeddings:
    """Call DashScope's native text embedding API."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        dimension: int = 1024,
        timeout: int = 60,
        batch_size: int = 10,
    ):
        self.model = model
        self.api_key = api_key
        self.dimension = dimension
        self.timeout = timeout
        self.batch_size = batch_size
        self.endpoint = self._build_endpoint(base_url)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    @staticmethod
    def _build_endpoint(base_url: str) -> str:
        normalized = (base_url or "").rstrip("/")
        if normalized.endswith("/compatible-mode/v1"):
            normalized = normalized[: -len("/compatible-mode/v1")] + "/api/v1"
        elif not normalized.endswith("/api/v1"):
            normalized = f"{normalized}/api/v1"

        return f"{normalized}/services/embeddings/text-embedding/text-embedding"

    def _embed_batch(self, texts: List[str], text_type: str) -> List[List[float]]:
        payload = {
            "model": self.model,
            "input": {"texts": texts},
            "parameters": {
                "text_type": text_type,
                "dimension": self.dimension,
                "output_type": "dense",
            },
        }
        response = self.session.post(
            self.endpoint,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()

        response_json = response.json()
        embeddings = response_json.get("output", {}).get("embeddings", [])
        if len(embeddings) != len(texts):
            raise ValueError(
                f"DashScope returned {len(embeddings)} embeddings for {len(texts)} texts"
            )

        return [item["embedding"] for item in embeddings]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        cleaned_texts = [text if isinstance(text, str) else str(text) for text in texts]
        if not cleaned_texts:
            return []

        embeddings: List[List[float]] = []
        for index in range(0, len(cleaned_texts), self.batch_size):
            batch = cleaned_texts[index : index + self.batch_size]
            embeddings.extend(self._embed_batch(batch, text_type="document"))
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        query_text = text if isinstance(text, str) else str(text)
        return self._embed_batch([query_text], text_type="query")[0]


class VectorStoreRepository:
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = "multi-agent-knowledge",
        embedding_model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.embedding = DashScopeEmbeddings(
            model=embedding_model or settings.EMBEDDING_MODEL,
            api_key=api_key or settings.API_KEY,
            base_url=base_url or settings.BASE_URL,
        )

        self.vector_database = Chroma(
            persist_directory=persist_directory or settings.VECTOR_STORE_PATH,
            collection_name=collection_name,
            embedding_function=self.embedding,
        )

    def add_documents(self, documents: List[Document], batch_size: int = 16) -> int:
        total_documents_chunks = len(documents)
        documents_chunks_added = 0

        try:
            for index in range(0, total_documents_chunks, batch_size):
                batch = documents[index : index + batch_size]
                self.vector_database.add_documents(batch)
                documents_chunks_added += len(batch)
                logger.info(
                    "Document chunks written to vector store: %s/%s",
                    documents_chunks_added,
                    total_documents_chunks,
                )

            return documents_chunks_added
        except Exception as exc:
            logger.error("Failed to write document chunks to vector store: %s", exc)
            raise

    def embedd_document(self, text: str) -> List[float]:
        return self.embedding.embed_query(text)

    def embedd_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embedding.embed_documents(texts)

    def search_similarity_with_score(
        self, user_question: str, top_k: int = 5
    ) -> List[tuple[Document, float]]:
        return self.vector_database.similarity_search_with_score(user_question, top_k)
