import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from openai import OpenAI
from ragas import EvaluationDataset, evaluate
from ragas.llms import llm_factory
from ragas.metrics import LLMContextRecall, Faithfulness, FactualCorrectness
from ragas.run_config import RunConfig
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from evaluation.eval_cases import EVAL_CASES
from repositories.vector_store_repository import VectorStoreRepository
from services.query_service import QueryService
from services.retrieval_service import RetrievalService


KNOWLEDGE_ROOT = PROJECT_ROOT
CRAWL_DIR = Path(settings.CRAWL_OUTPUT_DIR)
VECTOR_STORE_DIR = Path(settings.VECTOR_STORE_PATH)
OUTPUT_ROOT = KNOWLEDGE_ROOT / "eval_outputs"

# qwen-flash 在 RAGAS 的事实正确性判题里很容易因为输出 JSON 太长而被截断。
# 这里主动压缩评估输入，优先保证流程跑通。
MAX_EVAL_CONTEXT_CHARS = 800
MAX_EVAL_RESPONSE_CHARS = 220
MAX_EVAL_REFERENCE_CHARS = 180


def _truncate_text(text: str, max_chars: int) -> str:
    if text is None:
        return ""
    text = str(text).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[truncated for eval]"


def _normalize_response_for_eval(text: str) -> str:
    if not text:
        return ""

    normalized = str(text).strip()
    for marker in ["参考了资料编号", "参考资料编号", "参考文档", "参考资料"]:
        marker_index = normalized.find(marker)
        if marker_index != -1:
            normalized = normalized[:marker_index].rstrip()
            break
    return normalized


def merge_detail_rows(rows: list[dict], detail_df: pd.DataFrame) -> pd.DataFrame:
    base_df = pd.DataFrame(rows).reset_index(drop=True)
    detail_df = detail_df.reset_index(drop=True)

    missing_base_columns = [
        column for column in base_df.columns if column not in detail_df.columns
    ]
    if missing_base_columns:
        detail_df = pd.concat([base_df[missing_base_columns], detail_df], axis=1)

    if detail_df.columns.has_duplicates:
        detail_df = detail_df.loc[:, ~detail_df.columns.duplicated()]

    return detail_df


def normalize_rows_for_eval(rows: list[dict]) -> list[dict]:
    normalized_rows = []
    for row in rows:
        contexts = row.get("retrieved_contexts") or []
        normalized_rows.append(
            {
                **row,
                "retrieved_contexts": [
                    _truncate_text(context, MAX_EVAL_CONTEXT_CHARS)
                    for context in contexts[:2]
                ],
                "response": _truncate_text(
                    _normalize_response_for_eval(row.get("response", "")),
                    MAX_EVAL_RESPONSE_CHARS,
                ),
                "reference": _truncate_text(
                    row.get("reference", ""),
                    MAX_EVAL_REFERENCE_CHARS,
                ),
            }
        )
    return normalized_rows


def collect_evaluation_data(
    retrieval_service: RetrievalService,
    query_service: QueryService,
    eval_cases: list[dict],
) -> list[dict]:
    rows = []
    for case in tqdm(eval_cases, desc="开始构建回答"):
        docs = retrieval_service.retrieval(case["question"])
        response = query_service.generate_answer(case["question"], docs)
        rows.append(
            {
                "source_file": case["source_file"],
                "user_input": case["question"],
                "retrieved_contexts": [doc.page_content for doc in docs],
                "response": response,
                "reference": case["reference"],
                "retrieved_titles": " | ".join(
                    [doc.metadata.get("title", "") for doc in docs]
                ),
            }
        )
    return normalize_rows_for_eval(rows)


def get_latest_rows_file() -> Path:
    candidates = sorted(
        OUTPUT_ROOT.glob("*/evaluation_rows.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("未找到任何 evaluation_rows.json")
    return candidates[0]


def load_existing_rows(rows_file: Path) -> list[dict]:
    rows = json.loads(rows_file.read_text(encoding="utf-8"))
    return normalize_rows_for_eval(rows)


def build_metrics(
    include_faithfulness: bool,
    include_factual_correctness: bool,
):
    metrics = [LLMContextRecall()]

    if include_faithfulness:
        metrics.append(Faithfulness())

    if include_factual_correctness:
        metrics.append(
            FactualCorrectness(
                mode="precision",
                atomicity="low",
                coverage="low",
            )
        )
    return metrics


def evaluate_rows(
    rows: list[dict],
    include_faithfulness: bool,
    include_factual_correctness: bool,
):
    evaluation_dataset = EvaluationDataset.from_list(rows)
    openai_client = OpenAI(
        api_key=settings.API_KEY,
        base_url=settings.BASE_URL,
    )
    evaluator_llm = llm_factory(settings.MODEL, client=openai_client)
    metrics = build_metrics(include_faithfulness, include_factual_correctness)

    result = evaluate(
        dataset=evaluation_dataset,
        metrics=metrics,
        llm=evaluator_llm,
        run_config=RunConfig(timeout=240, max_workers=1, max_retries=1),
        batch_size=1,
        raise_exceptions=True,
    )
    return result, result.to_pandas()


def write_outputs(output_dir: Path, detail_df: pd.DataFrame, metadata: dict) -> None:
    detail_csv_path = output_dir / "ragas_detail.csv"
    detail_json_path = output_dir / "ragas_detail.json"
    report_md_path = output_dir / "ragas_report.md"

    detail_df.to_csv(detail_csv_path, index=False, encoding="utf-8-sig")
    detail_df.to_json(detail_json_path, orient="records", force_ascii=False, indent=2)

    context_recall_column = next(
        (
            column
            for column in detail_df.columns
            if column in ("llm_context_recall", "context_recall")
            or column.endswith("context_recall")
        ),
        None,
    )
    if context_recall_column is None:
        raise ValueError(
            f"未找到 context recall 对应列，当前列如下: {list(detail_df.columns)}"
        )

    factual_column = next(
        (
            column
            for column in detail_df.columns
            if column.startswith("factual_correctness")
        ),
        None,
    )

    summary = {
        "context_recall": float(detail_df[context_recall_column].mean()),
    }
    has_faithfulness = "faithfulness" in detail_df.columns
    if has_faithfulness:
        summary["faithfulness"] = float(detail_df["faithfulness"].mean())
    if factual_column is not None:
        summary["factual_correctness"] = float(detail_df[factual_column].mean())

    report_lines = [
        "# RAGAS 评估报告",
        "",
        f"- 生成时间: {metadata['generated_at']}",
        f"- 爬取目录: `{metadata['crawl_dir']}`",
        f"- 向量库目录: `{metadata['vector_store_dir']}`",
        f"- 已索引文档数: {metadata['indexed_doc_count']}",
        f"- 评估样例数: {metadata['case_count']}",
        f"- 使用已有样本: {metadata['used_existing_rows']}",
        f"- 启用事实正确性: {metadata['include_factual_correctness']}",
        "",
        "## 指标汇总",
        "",
        "| 指标 | 分数 |",
        "| --- | ---: |",
        f"| {context_recall_column} | {summary['context_recall']:.4f} |",
    ]
    if has_faithfulness:
        report_lines.append(f"| faithfulness | {summary['faithfulness']:.4f} |")
    if factual_column is not None:
        report_lines.append(
            f"| factual_correctness | {summary['factual_correctness']:.4f} |"
        )

    report_lines.extend(
        [
            "",
            "## 逐条明细",
            "",
        ]
    )

    if has_faithfulness and factual_column is not None:
        report_lines.extend(
            [
                f"| 来源文件 | 问题 | 召回标题 | {context_recall_column} | faithfulness | factual_correctness |",
                "| --- | --- | --- | ---: | ---: | ---: |",
            ]
        )
    elif has_faithfulness:
        report_lines.extend(
            [
                f"| 来源文件 | 问题 | 召回标题 | {context_recall_column} | faithfulness |",
                "| --- | --- | --- | ---: | ---: |",
            ]
        )
    else:
        report_lines.extend(
            [
                f"| 来源文件 | 问题 | 召回标题 | {context_recall_column} |",
                "| --- | --- | --- | ---: |",
            ]
        )

    for _, row in detail_df.iterrows():
        question = str(row["user_input"]).replace("\n", " ")
        titles = str(row.get("retrieved_titles", "")).replace("\n", " ")
        if has_faithfulness and factual_column is not None:
            report_lines.append(
                "| {source_file} | {question} | {titles} | {context_recall:.4f} | {faithfulness:.4f} | {factual_correctness:.4f} |".format(
                    source_file=row["source_file"],
                    question=question,
                    titles=titles,
                    context_recall=float(row[context_recall_column]),
                    faithfulness=float(row["faithfulness"]),
                    factual_correctness=float(row[factual_column]),
                )
            )
        elif has_faithfulness:
            report_lines.append(
                "| {source_file} | {question} | {titles} | {context_recall:.4f} | {faithfulness:.4f} |".format(
                    source_file=row["source_file"],
                    question=question,
                    titles=titles,
                    context_recall=float(row[context_recall_column]),
                    faithfulness=float(row["faithfulness"]),
                )
            )
        else:
            report_lines.append(
                "| {source_file} | {question} | {titles} | {context_recall:.4f} |".format(
                    source_file=row["source_file"],
                    question=question,
                    titles=titles,
                    context_recall=float(row[context_recall_column]),
                )
            )

    report_md_path.write_text("\n".join(report_lines), encoding="utf-8")
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rows-file",
        type=str,
        help="直接使用指定的 evaluation_rows.json；不传时默认读取最新一份",
    )
    parser.add_argument(
        "--skip-faithfulness",
        action="store_true",
        help="跳过 faithfulness 指标",
    )
    parser.add_argument(
        "--skip-factual-correctness",
        action="store_true",
        help="跳过 factual_correctness 指标",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not VECTOR_STORE_DIR.exists():
        raise FileNotFoundError(
            f"向量库目录不存在: {VECTOR_STORE_DIR}，请先执行 evaluation/build_vector_index.py"
        )

    markdown_files = sorted(CRAWL_DIR.glob("*.md"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_ROOT / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    used_existing_rows = True

    if args.rows_file:
        rows_file = Path(args.rows_file)
    else:
        rows_file = get_latest_rows_file()
    rows = load_existing_rows(rows_file)

    result, detail_df = evaluate_rows(
        rows,
        include_faithfulness=not args.skip_faithfulness,
        include_factual_correctness=not args.skip_factual_correctness,
    )
    detail_df = merge_detail_rows(rows, detail_df)

    metadata = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "crawl_dir": str(CRAWL_DIR),
        "vector_store_dir": str(VECTOR_STORE_DIR),
        "indexed_doc_count": len(markdown_files),
        "case_count": len(rows),
        "ragas_result_repr": str(result),
        "used_existing_rows": used_existing_rows,
        "rows_file": str(rows_file),
        "include_faithfulness": not args.skip_faithfulness,
        "include_factual_correctness": not args.skip_factual_correctness,
    }
    write_outputs(output_dir, detail_df, metadata)

    print("RAGAS 评估完成")
    print(f"向量库目录: {VECTOR_STORE_DIR}")
    print(f"输出目录: {output_dir}")
    print(f"评估结果: {result}")


if __name__ == "__main__":
    main()
