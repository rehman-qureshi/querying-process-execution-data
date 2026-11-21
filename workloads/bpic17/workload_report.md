# Workload report (draw 1, seed 1)

- Full repository: 796 rules with support >= 0.95 and >= 50 activated cases, over 24 of 24 activities; 263 activity pairs.
- Questions: 100; distinct primary constraints: 100; activities per question: {2: 6, 3: 25, 4: 30, 5: 24, 6: 15}.
- Rules relevant to at least one question: 663 of 796 (83.3%); activity pairs covered: 228 of 263.
- Activities used by at least one question: 24 of 24.
- Measures: {'top5_resources': 20, 'count_cases': 25, 'avg_time_to_activation': 15, 'avg_waiting_time': 25, 'distinct_resources': 15}
- Primary templates: {'precedence': 26, 'response': 8, 'alt_precedence': 15, 'responded_existence': 13, 'alt_response': 7, 'not_succession': 21, 'chain_precedence': 4, 'chain_response': 2, 'not_co_existence': 4}
- Conditions: {'net_worth_gt': 26, 'resource_eq': 10, 'within_days': 12}; questions without condition: 57
- Satisfied cases with the full repository: min 50, median 1106, max 21870.
- Monotonicity check (more rules never give more satisfied cases): 0 violations.

| rules in repository | mean constraints per question | min | median | max |
|---|---|---|---|---|
| 100 | 4.15 | 1 | 3 | 15 |
| 200 | 6.62 | 1 | 5 | 24 |
| 400 | 11.68 | 1 | 9 | 53 |
| 600 | 16.4 | 1 | 13 | 70 |
| 796 | 20.95 | 1 | 16 | 88 |
