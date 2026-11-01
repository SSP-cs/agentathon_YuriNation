# TrustLayer Evaluation Results (re-judged)

**117 questions** (77 answerable, 40 trap questions). Re-judged with 4 answer-key correction(s) and one uniform LLM judge applied to all three systems. First-run labels are kept in results_first_run.json.

| Metric | Naive RAG | Strict-prompt RAG | TrustLayer |
| :--- | :---: | :---: | :---: |
| Hallucination rate | 8.6% | 7.7% | 1.7% |
| Trap questions handled | 95% | 98% | 100% |
| Answerable answered correctly | 88% | 84% | 87% |
| Answerable sent to a human | n/a | n/a | 10% |
| Hallucinations released as verified | n/a | n/a | 2 |
| Average time per answer | 1.5s | n/a | 10.3s |
| LLM calls per question (TrustLayer estimated) | 1.0 | 1.0 | 6.0 |

Hallucinated answers by category (count):

| Category | Questions | Naive | Strict | TrustLayer |
| :--- | :---: | :---: | :---: | :---: |
| core | 77 | 5 | 6 | 2 |
| confusable | 12 | 2 | 2 | 0 |
| multi_hop | 7 | 1 | 1 | 0 |
| false_premise | 7 | 2 | 0 | 0 |
| amended | 6 | 0 | 0 | 0 |
| out_of_scope | 8 | 0 | 0 | 0 |
