# Evaluation results

Corpus: `eval/corpus` (4 documents). Cases: `eval/dataset.jsonl`. Embeddings: `fastembed` `BAAI/bge-small-en-v1.5`. Chunk size 800, overlap 120, k=5.

## Retrieval

| Mode | hit@1 | hit@5 | MRR |
|---|---|---|---|
| vector | 1.00 | 1.00 | 1.00 |
| bm25 | 0.86 | 0.95 | 0.90 |
| hybrid | 0.95 | 1.00 | 0.98 |

## Relevance gate

- Lowest best-match cosine for an in-scope question: 0.623
- Highest best-match cosine for an out-of-scope question: 0.544
- `MIN_RELEVANCE` = 0.55: blocks 4/4 out-of-scope questions before the LLM is called (the rest are left to the grader and verifier).
