# Workload report (draw 1, seed 1)

- Full repository: 1104 rules with support >= 0.95 and >= 50 activated cases, over 28 of 28 activities; 373 activity pairs.
- Questions: 100; distinct primary constraints: 100; activities per question: {2: 18, 3: 29, 4: 31, 5: 18, 6: 4}.
- Rules relevant to at least one question: 398 of 1104 (36.1%); activity pairs covered: 193 of 373.
- Activities used by at least one question: 28 of 28.
- Measures: {'top5_resources': 20, 'distinct_resources': 15, 'count_cases': 28, 'avg_waiting_time': 22, 'avg_time_to_activation': 15}
- Primary templates: {'not_co_existence': 24, 'not_succession': 39, 'responded_existence': 8, 'precedence': 11, 'alt_response': 4, 'chain_response': 1, 'alt_precedence': 9, 'response': 4}
- Conditions: {'net_worth_gt': 29, 'within_days': 12, 'resource_eq': 11}; questions without condition: 53
- Satisfied cases with the full repository: min 50, median 3240, max 198233.
- Monotonicity check (more rules never give more satisfied cases): 0 violations.

| rules in repository | mean constraints per question | min | median | max |
|---|---|---|---|---|
| 100 | 4.9 | 1 | 3 | 21 |
| 250 | 6.29 | 1 | 4 | 26 |
| 500 | 8.08 | 1 | 6 | 35 |
| 750 | 9.72 | 1 | 6 | 43 |
| 1000 | 11.13 | 1 | 8 | 49 |
| 1104 | 11.8 | 2 | 9 | 50 |
