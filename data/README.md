# Event logs (not included)

The two public BPI Challenge logs are not copied into this repository. Download them from the 4TU repository and
export them as CSV (e.g. with PM4Py: `pm4py.convert_to_dataframe` and `to_csv`).

| Log | Used file name | Notes |
|---|---|---|
| BPIC19 (purchase-to-pay) | `data/process_execution_data.csv` | 217,406 traces, 1,214,244 events, 28 activities. Columns used: `case:concept:name`, `concept:name`, `time:timestamp`, `org:resource`, `Cumulative net worth (EUR)` (data condition). |
| BPIC17 (loan applications) | `data/event_log_BPIC17.csv` | Raw export. Only rows with `lifecycle:transition = complete` are used: 31,509 traces, 475,306 events, 24 activities. Columns used: `case:concept:name`, `concept:name`, `time:timestamp`, `org:resource`, `case:RequestedAmount` (data condition). |

Place the CSV files in this folder (they are git-ignored). The runner reads the CSV once and caches it as `log_cache.npz`.
