# Results: cycles and IPC per test and issue width

Up to issue_width commits per cycle, one CDB, 1-bit predictor with an 8-entry BTB.
Final registers and memory are identical at every width for every test.

| test | width | instructions | cycles | IPC | branches | mispredicted | squashed |
|---|---|---|---|---|---|---|---|
| original_code_in | 1 | 15 | 42 | 0.357 | 3 | 2 | 2 |
| original_code_in | 2 | 15 | 35 | 0.429 | 3 | 2 | 4 |
| original_code_in | 3 | 15 | 34 | 0.441 | 3 | 2 | 4 |
| original_code_in | 4 | 15 | 34 | 0.441 | 3 | 2 | 4 |
| spec_sample | 1 | 8 | 19 | 0.421 | 2 | 2 | 3 |
| spec_sample | 2 | 8 | 15 | 0.533 | 2 | 2 | 3 |
| spec_sample | 3 | 8 | 13 | 0.615 | 2 | 2 | 3 |
| spec_sample | 4 | 8 | 13 | 0.615 | 2 | 2 | 3 |
| t1_independent | 1 | 8 | 20 | 0.400 | 0 | 0 | 0 |
| t1_independent | 2 | 8 | 16 | 0.500 | 0 | 0 | 0 |
| t1_independent | 3 | 8 | 15 | 0.533 | 0 | 0 | 0 |
| t1_independent | 4 | 8 | 14 | 0.571 | 0 | 0 | 0 |
| t2_raw_chain | 1 | 6 | 26 | 0.231 | 0 | 0 | 0 |
| t2_raw_chain | 2 | 6 | 26 | 0.231 | 0 | 0 | 0 |
| t2_raw_chain | 3 | 6 | 26 | 0.231 | 0 | 0 | 0 |
| t2_raw_chain | 4 | 6 | 26 | 0.231 | 0 | 0 | 0 |
| t3_structural | 1 | 8 | 22 | 0.364 | 0 | 0 | 0 |
| t3_structural | 2 | 8 | 21 | 0.381 | 0 | 0 | 0 |
| t3_structural | 3 | 8 | 21 | 0.381 | 0 | 0 | 0 |
| t3_structural | 4 | 8 | 21 | 0.381 | 0 | 0 | 0 |
| t4_forwarding | 1 | 9 | 21 | 0.429 | 0 | 0 | 0 |
| t4_forwarding | 2 | 9 | 19 | 0.474 | 0 | 0 | 0 |
| t4_forwarding | 3 | 9 | 19 | 0.474 | 0 | 0 | 0 |
| t4_forwarding | 4 | 9 | 19 | 0.474 | 0 | 0 | 0 |
| t5_loop | 1 | 17 | 34 | 0.500 | 4 | 2 | 3 |
| t5_loop | 2 | 17 | 31 | 0.548 | 4 | 2 | 5 |
| t5_loop | 3 | 17 | 30 | 0.567 | 4 | 2 | 6 |
| t5_loop | 4 | 17 | 29 | 0.586 | 4 | 2 | 6 |
| t6_beq_mispredict | 1 | 7 | 21 | 0.333 | 2 | 1 | 1 |
| t6_beq_mispredict | 2 | 7 | 18 | 0.389 | 2 | 1 | 3 |
| t6_beq_mispredict | 3 | 7 | 17 | 0.412 | 2 | 1 | 5 |
| t6_beq_mispredict | 4 | 7 | 16 | 0.438 | 2 | 1 | 5 |
