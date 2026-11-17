"""Evaluation: retrieval quality (vector vs BM25 vs hybrid) and, optionally, end-to-end answers.

    python -m eval.run_eval              # retrieval only: no API key, no cost
    python -m eval.run_eval --with-llm   # also runs the full agent with the configured LLM

A retrieved chunk counts as relevant when it comes from the expected file AND contains one of the
expected answer strings, so "right document, wrong section" is a miss.
"""
import argparse
import asyncio
import json
import os
import re
import statistics
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp(prefix='eka-eval-')}/eval.db")
os.environ.setdefault("REDIS_URL", "")

from langchain_core.callbacks import get_usage_metadata_callback  # noqa: E402

from app.agent.graph import normalize_text, run_agent  # noqa: E402
from app.agent.llm import get_llm  # noqa: E402
from app.agent.prompts import REFUSAL  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.ingestion.pipeline import ingest_document  # noqa: E402
from app.models import Document, User  # noqa: E402
from app.retrieval.search import search, vector_search  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402

K = 5


def load_cases() -> list[dict]:
    return [json.loads(line) for line in (ROOT / "dataset.jsonl").read_text().splitlines() if line.strip()]


def seed_corpus() -> User:
    init_db()
    db = SessionLocal()
    user = User(email=f"eval-{uuid.uuid4().hex[:6]}@example.com", hashed_password=hash_password("eval-password"))
    db.add(user)
    db.commit()
    for path in sorted((ROOT / "corpus").iterdir()):
        doc = Document(owner_id=user.id, filename=path.name, content_type="text/plain")
        db.add(doc)
        db.commit()
        ingest_document(doc.id, path.read_bytes())
    db.close()
    return user


def is_relevant(hit, case) -> bool:
    return hit.filename == case["expected_file"] and any(s in hit.text for s in case["expected_answer_contains"])


def retrieval_eval(user: User, cases: list[dict]) -> dict:
    db = SessionLocal()
    in_scope = [c for c in cases if c["expected_file"]]
    out_scope = [c for c in cases if not c["expected_file"]]
    report = {}
    for mode in ("vector", "bm25", "hybrid"):
        hit1, hitk, rr = [], [], []
        for case in in_scope:
            hits = search(db, user.id, case["question"], K, mode)
            ranks = [i for i, h in enumerate(hits, start=1) if is_relevant(h, case)]
            hit1.append(bool(ranks and ranks[0] == 1))
            hitk.append(bool(ranks))
            rr.append(1 / ranks[0] if ranks else 0.0)
        report[mode] = {"hit@1": statistics.mean(hit1), f"hit@{K}": statistics.mean(hitk), "mrr": statistics.mean(rr)}

    def best_cosine(case):
        hits = vector_search(db, user.id, case["question"], 1)
        return hits[0].vector_score if hits else 0.0

    report["gate"] = {
        "in_scope_best_cosine_min": min(best_cosine(c) for c in in_scope),
        "out_of_scope_best_cosine_max": max(best_cosine(c) for c in out_scope),
        "min_relevance": get_settings().min_relevance,
        "out_of_scope_blocked_by_gate": sum(best_cosine(c) < get_settings().min_relevance for c in out_scope),
        "out_of_scope_total": len(out_scope),
    }
    db.close()
    return report


async def answer_eval(user: User, cases: list[dict]) -> dict:
    async def no_tools(token):
        return []

    token, llm = create_access_token(user), get_llm()
    rows = []
    for case in cases:
        start = time.perf_counter()
        with get_usage_metadata_callback() as usage:
            out = await run_agent(question=case["question"], history=[], user_id=user.id, token=token,
                                  llm=llm, tool_loader=no_tools)
        cost = {"seconds": time.perf_counter() - start,
                "tokens": sum(u.get("total_tokens", 0) for u in usage.usage_metadata.values())}
        if case["expected_file"]:
            correct = any(s in normalize_text(out["answer"]) for s in case["expected_answer_contains"])
            cited_right = any(c["filename"] == case["expected_file"] for c in out["citations"])
            rows.append({"q": case["question"], "kind": "in_scope", "correct": correct, "cited_right": cited_right,
                         "type": out["answer_type"], "answer": out["answer"], **cost})
        else:
            rows.append({"q": case["question"], "kind": "out_of_scope", "correct": out["answer"] == REFUSAL,
                         "cited_right": None, "type": out["answer_type"], "answer": out["answer"], **cost})
        sys.stderr.write(f"[{len(rows)}/{len(cases)}] {'ok ' if rows[-1]['correct'] else 'MISS'} {case['question']}\n")
    ins = [r for r in rows if r["kind"] == "in_scope"]
    outs = [r for r in rows if r["kind"] == "out_of_scope"]
    return {
        "answer_accuracy": statistics.mean(r["correct"] for r in ins),
        "citation_accuracy": statistics.mean(r["cited_right"] for r in ins),
        "correct_refusals": statistics.mean(r["correct"] for r in outs),
        "median_seconds": statistics.median(r["seconds"] for r in rows),
        "median_tokens": statistics.median(r["tokens"] for r in rows),
        "rows": rows,
    }


def to_markdown(retrieval: dict, answers: dict | None) -> str:
    s = get_settings()
    lines = [
        "# Evaluation results", "",
        f"Corpus: `eval/corpus` (4 documents). Cases: `eval/dataset.jsonl`. Embeddings: `{s.embedding_provider}` "
        f"`{s.embedding_model}`. Chunk size {s.chunk_size}, overlap {s.chunk_overlap}, k={K}.", "",
        "## Retrieval", "", f"| Mode | hit@1 | hit@{K} | MRR |", "|---|---|---|---|",
    ]
    for mode in ("vector", "bm25", "hybrid"):
        r = retrieval[mode]
        lines.append(f"| {mode} | {r['hit@1']:.2f} | {r[f'hit@{K}']:.2f} | {r['mrr']:.2f} |")
    g = retrieval["gate"]
    lines += [
        "", "## Relevance gate", "",
        f"- Lowest best-match cosine for an in-scope question: {g['in_scope_best_cosine_min']:.3f}",
        f"- Highest best-match cosine for an out-of-scope question: {g['out_of_scope_best_cosine_max']:.3f}",
        f"- `MIN_RELEVANCE` = {g['min_relevance']}: blocks {g['out_of_scope_blocked_by_gate']}/"
        f"{g['out_of_scope_total']} out-of-scope questions before the LLM is called "
        "(the rest are left to the grader and verifier).",
    ]
    if answers:
        lines += [
            "", f"## End-to-end answers (`{s.llm_provider}` `{s.llm_model}`)", "",
            f"- Answer contains expected fact: {answers['answer_accuracy']:.2f}",
            f"- Cites the expected document: {answers['citation_accuracy']:.2f}",
            f"- Out-of-scope questions correctly refused: {answers['correct_refusals']:.2f}",
            f"- Median per question: {answers['median_seconds']:.1f} s, {answers['median_tokens']:.0f} tokens"
            f" (reasoning effort: {s.llm_reasoning_effort or 'provider default'})", "",
            "| Question | Kind | Correct | Answer type | Seconds | Tokens | Answer |", "|---|---|---|---|---|---|---|",
        ]
        lines += [
            f"| {r['q']} | {r['kind']} | {'yes' if r['correct'] else 'no'} | {r['type']} | {r['seconds']:.1f} | {r['tokens']} | "
            f"{r['answer'][:160].replace('|', '/').replace(chr(10), ' ')} |"
            for r in answers["rows"]
        ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-llm", action="store_true")
    args = parser.parse_args()
    cases = load_cases()
    user = seed_corpus()
    retrieval = retrieval_eval(user, cases)
    answers = asyncio.run(answer_eval(user, cases)) if args.with_llm else None
    md = to_markdown(retrieval, answers)
    s = get_settings()
    name = f"results-{s.llm_provider}-{re.sub(r'[^a-z0-9.]+', '-', s.llm_model.lower())}.md" if answers else "results.md"
    (ROOT / name).write_text(md)
    sys.stdout.write(md)


if __name__ == "__main__":
    main()
