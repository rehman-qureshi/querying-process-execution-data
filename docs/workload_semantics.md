# Semantics used by the reference executor (declare_workload.py)

A question is represented as **C** (1-4 constraints from the repository), optional **conditions** (apply to the
primary = first constraint) and one **measure**. Execution follows the paper: activated cases -> satisfied cases
(L_conform) -> measure.

## Templates (A = 1st argument, B = 2nd argument)
| Template | Activation event | Satisfied for an activation if | Partner event |
|---|---|---|---|
| Response | A | a B occurs later | first B after A |
| Alternate Response | A | a B occurs later and no other A lies in between | first B after A |
| Chain Response | A | next event is B | next event |
| Precedence | B | an A occurred earlier | closest A before B |
| Alternate Precedence | B | an A occurred earlier and no other B lies in between | closest A before B |
| Chain Precedence | B | previous event is A | previous event |
| Responded Existence | A | B occurs anywhere in the case | none |
| Not Co-Existence | A | B does not occur in the case | none |
| Not Succession | A | B never occurs after A | none |

## Conditions (on the primary constraint)
- `net_worth_gt`: activation event has `Cumulative net worth (EUR)` > value. Events failing it are not activations.
- `resource_eq`: activation event has `org:resource` = value. Events failing it are not activations.
- `within_days`: partner event within value days of the activation event (only for templates with a partner);
  an activation without such a partner violates the constraint.

## Cases
- Activated: >= 1 activation event passes the conditions (and, for composite C, every constraint is activated).
- Satisfied (L_conform): activated and no violating activation in any constraint of C.
- Coverage = activated / all cases; Support = satisfied / activated.

## Measures (computed over satisfied cases, on the primary constraint's activation events)
- `count_cases`: |L_conform|.
- `avg_waiting_time`: mean |t(partner) - t(activation)| using the first activation per case (partner templates only).
- `avg_time_to_activation`: mean time from the first event of the case to the first activation event.
- `top5_resources`: 5 resources performing the activation activity in most satisfied cases (each case counted once per resource).
- `distinct_resources`: number of distinct resources performing the activation event.

## Modelling choices to keep or change
- Not Co-Existence uses A only as activation (the textbook version activates on A and B).
- Several activations in one case: the case is satisfied only if all passing activations are satisfied.
- Only the repository's control-flow constraints are stored; conditions and measures are parameters of the question's
  representation (like the brackets in Table 2 of the paper).
