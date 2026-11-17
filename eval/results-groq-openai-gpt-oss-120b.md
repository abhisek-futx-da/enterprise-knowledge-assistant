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

## End-to-end answers (`groq` `openai/gpt-oss-120b`)

- Answer contains expected fact: 1.00
- Cites the expected document: 1.00
- Out-of-scope questions correctly refused: 1.00
- Median per question: 16.4 s, 2403 tokens (reasoning effort: provider default)

| Question | Kind | Correct | Answer type | Seconds | Tokens | Answer |
|---|---|---|---|---|---|---|
| How many days of paid annual leave do full-time employees get? | in_scope | yes | grounded | 3.0 | 2378 | Full-time employees receive 24 days of paid annual leave per calendar year [S1]. |
| How much unused leave can I carry over to next year? | in_scope | yes | grounded | 2.7 | 2438 | You may carry over up to 5 unused annual leave days to the next year [S1]. |
| How long is the probation period for new joiners? | in_scope | yes | grounded | 2.9 | 2512 | The probation period for new joiners is 90 days[S1]. |
| What is the notice period for a manager after confirmation? | in_scope | yes | grounded | 5.8 | 2527 | After confirmation, a manager’s notice period is 90 days [S1]. |
| How many weeks of parental leave does a primary caregiver receive? | in_scope | yes | grounded | 18.1 | 2377 | Primary caregivers receive 26 weeks of paid parental leave [S1]. |
| What is the daily limit for business meal reimbursement? | in_scope | yes | grounded | 18.5 | 2471 | Business meals are reimbursed up to $60 per person per day [S2]. |
| How much money do I get each year for training and courses? | in_scope | yes | grounded | 17.7 | 2460 | Each employee receives an annual learning budget of $1,500 for courses, books, and conferences [S1]. |
| How many days a week can I work from home? | in_scope | yes | grounded | 19.7 | 2479 | Employees may work remotely up to three days per week after completing probation [S1]. |
| What is the minimum password length? | in_scope | yes | grounded | 17.0 | 2305 | The minimum password length is 14 characters [S1]. |
| Within how many hours must a security incident be reported? | in_scope | yes | grounded | 18.6 | 2388 | Any suspected security incident must be reported within 2 hours of discovery [S1]. |
| What are the data classification levels? | in_scope | yes | grounded | 16.7 | 2370 | The data classification levels are Public, Internal, Confidential, and Restricted [S1]. |
| When must a lost laptop be reported? | in_scope | yes | grounded | 16.4 | 2393 | A lost laptop must be reported to the IT helpdesk within 1 hour [S1]. |
| How often are production access rights reviewed? | in_scope | yes | grounded | 11.8 | 2271 | Production access rights are reviewed every quarter by the system owner [S1]. |
| What does error code E-417 mean? | in_scope | yes | grounded | 17.3 | 2722 | Error code E-417 indicates a thermal sensor fault; you should switch the unit off at the isolator, wait 10 minutes, then turn it back on, and if the code return |
| What happens with E-102? | in_scope | yes | grounded | 20.6 | 2655 | E-102 means the grid connection was lost; the battery automatically switches to backup mode and returns to normal operation when the grid is restored [S1]. |
| How much energy can the HX-200 store? | in_scope | yes | grounded | 15.7 | 2546 | The HX-200 stores 12.5 kWh of usable energy[S1]. |
| How long is the battery covered under warranty? | in_scope | yes | grounded | 17.9 | 2608 | The battery is covered for 10 years (or 6,000 full cycles, whichever comes first) [S1]. |
| Which firmware version is the latest? | in_scope | yes | grounded | 17.2 | 2372 | The latest firmware version is 4.2.1 [S1]. |
| What is the hotel limit per night in London? | in_scope | yes | grounded | 16.2 | 2367 | The hotel limit in London is $320 per night [S1]. |
| What cabin class may I fly on a 4 hour flight? | in_scope | yes | grounded | 18.7 | 2618 | You may fly in economy class on a 4-hour flight [S1]. |
| How far in advance must I book business trips? | in_scope | yes | grounded | 16.5 | 2413 | Business trips must be booked through the Wayfarer travel portal at least 14 days before departure[S1]. |
| What is the daily per diem when travelling? | in_scope | yes | grounded | 15.0 | 2475 | Travellers receive a per-diem of $75 per day for meals and incidentals while travelling[S1]. |
| What is the capital of Australia? | out_of_scope | yes | refused | 5.1 | 662 | I don't know based on your documents. |
| Who won the football world cup in 2022? | out_of_scope | yes | refused | 2.5 | 640 | I don't know based on your documents. |
| What is the company's stock price today? | out_of_scope | yes | refused | 13.9 | 1823 | I don't know based on your documents. |
| What is the dental insurance coverage limit? | out_of_scope | yes | refused | 11.1 | 1706 | I don't know based on your documents. |
