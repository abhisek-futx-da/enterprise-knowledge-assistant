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

## End-to-end answers (`groq` `qwen/qwen3.8-27b`)

- Answer contains expected fact: 1.00
- Cites the expected document: 1.00
- Out-of-scope questions correctly refused: 1.00
- Median per question: 15.4 s, 1912 tokens (reasoning effort: provider default)

| Question | Kind | Correct | Answer type | Seconds | Tokens | Answer |
|---|---|---|---|---|---|---|
| How many days of paid annual leave do full-time employees get? | in_scope | yes | grounded | 1.9 | 1908 | Full-time employees receive 24 days of paid annual leave per calendar year [S1]. |
| How much unused leave can I carry over to next year? | in_scope | yes | grounded | 1.1 | 1957 | Up to 5 unused annual leave days may be carried over to the next year [S1]. |
| How long is the probation period for new joiners? | in_scope | yes | grounded | 1.0 | 2087 | The probation period for new joiners is 90 days [S1]. |
| What is the notice period for a manager after confirmation? | in_scope | yes | grounded | 4.4 | 2093 | After confirmation, the notice period for managers is 90 days [S1]. |
| How many weeks of parental leave does a primary caregiver receive? | in_scope | yes | grounded | 15.5 | 1898 | A primary caregiver receives 26 weeks of paid parental leave [S1]. |
| What is the daily limit for business meal reimbursement? | in_scope | yes | grounded | 14.2 | 1705 | The daily limit for business meal reimbursement is $60 per person per day [S1]. |
| How much money do I get each year for training and courses? | in_scope | yes | grounded | 15.4 | 1933 | You receive an annual learning budget of $1,500 for courses, books, and conferences [S1]. |
| How many days a week can I work from home? | in_scope | yes | grounded | 17.7 | 2055 | You can work from home up to three days per week after completing probation [S1]. |
| What is the minimum password length? | in_scope | yes | grounded | 15.4 | 1915 | The minimum password length is 14 characters [S1]. |
| Within how many hours must a security incident be reported? | in_scope | yes | grounded | 15.5 | 1892 | A suspected security incident must be reported within 2 hours of discovery [S1]. |
| What are the data classification levels? | in_scope | yes | grounded | 16.5 | 1936 | Company data is classified into four levels: Public, Internal, Confidential and Restricted [S1]. |
| When must a lost laptop be reported? | in_scope | yes | grounded | 16.1 | 1938 | A lost laptop must be reported to the IT helpdesk within 1 hour [S1]. |
| How often are production access rights reviewed? | in_scope | yes | grounded | 14.6 | 1795 | Production access rights are reviewed every quarter by the system owner [S1]. |
| What does error code E-417 mean? | in_scope | yes | grounded | 17.5 | 2134 | Error code E-417 means a thermal sensor fault [S1]. |
| What happens with E-102? | in_scope | yes | grounded | 18.7 | 2251 | Error code E-102 means the grid connection was lost [S1]. The battery switches to backup mode automatically and returns to normal operation when the grid is res |
| How much energy can the HX-200 store? | in_scope | yes | grounded | 17.7 | 2161 | The HX-200 stores 12.5 kWh of usable energy [S1]. |
| How long is the battery covered under warranty? | in_scope | yes | grounded | 18.2 | 2150 | The battery is covered under warranty for 10 years or 6,000 full cycles, whichever comes first [S1]. |
| Which firmware version is the latest? | in_scope | yes | grounded | 15.4 | 1853 | The current firmware version is 4.2.1 [S1]. |
| What is the hotel limit per night in London? | in_scope | yes | grounded | 15.4 | 1858 | The hotel limit per night in London is $320 [S1]. |
| What cabin class may I fly on a 4 hour flight? | in_scope | yes | grounded | 17.4 | 2044 | You may fly in Economy class on a 4-hour flight, as this class is required for flights shorter than 6 hours [S1]. |
| How far in advance must I book business trips? | in_scope | yes | grounded | 15.2 | 1861 | Business trips must be booked at least 14 days before departure [S1]. |
| What is the daily per diem when travelling? | in_scope | yes | grounded | 15.6 | 1873 | Travellers receive a per diem of $75 per day for meals and incidentals [S1]. |
| What is the capital of Australia? | out_of_scope | yes | refused | 3.1 | 370 | I don't know based on your documents. |
| Who won the football world cup in 2022? | out_of_scope | yes | refused | 3.4 | 392 | I don't know based on your documents. |
| What is the company's stock price today? | out_of_scope | yes | refused | 10.4 | 1341 | I don't know based on your documents. |
| What is the dental insurance coverage limit? | out_of_scope | yes | refused | 2.7 | 378 | I don't know based on your documents. |
