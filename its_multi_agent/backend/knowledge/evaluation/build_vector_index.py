import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from repositories.vector_store_repository import VectorStoreRepository
from services.ingestion.ingestion_processor import IngestionProcessor


KNOWLEDGE_ROOT = PROJECT_ROOT
CRAWL_DIR = Path(settings.CRAWL_OUTPUT_DIR)
VECTOR_STORE_DIR = Path(settings.VECTOR_STORE_PATH)
OUTPUT_DIR = KNOWLEDGE_ROOT / "eval_outputs" / "build_index"


def build_vector_index() -> dict:
    markdown_files = sorted(CRAWL_DIR.glob("*.md"))

    shutil.rmtree(VECTOR_STORE_DIR, ignore_errors=True)
    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    vector_store = VectorStoreRepository(
        persist_directory=str(VECTOR_STORE_DIR),
        collection_name="multi-agent-knowledge",
    )
    ingestion_processor = IngestionProcessor(vector_store=vector_store)

    success_docs = 0
    fail_docs = 0
    chunks_added = 0
    failed_files = []

    for markdown_file in tqdm(markdown_files, desc="构建向量索引"):
        try:
            chunks_added += ingestion_processor.ingest_file(str(markdown_file))
            success_docs += 1
        except Exception as exc:
            fail_docs += 1
            failed_files.append(
                {
                    "file": markdown_file.name,
                    "error": str(exc),
                }
            )
            print(f"[WARN] 入库失败: {markdown_file.name} -> {exc}")

    metadata = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "crawl_dir": str(CRAWL_DIR),
        "vector_store_dir": str(VECTOR_STORE_DIR),
        "indexed_doc_count": len(markdown_files),
        "success_docs": success_docs,
        "fail_docs": fail_docs,
        "chunks_added": chunks_added,
        "failed_files": failed_files,
    }
    (OUTPUT_DIR / "build_index_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def main() -> None:
    metadata = build_vector_index()
    print("向量索引构建完成")
    print(f"向量库目录: {metadata['vector_store_dir']}")
    print(f"文档总数: {metadata['indexed_doc_count']}")
    print(f"成功入库: {metadata['success_docs']}")
    print(f"失败文档: {metadata['fail_docs']}")
    print(f"写入分块: {metadata['chunks_added']}")


if __name__ == "__main__":
    main()
