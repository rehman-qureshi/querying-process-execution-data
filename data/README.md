# Event logs (not included)

The event logs are not copied into this repository. Download them as described below and place the CSV files in this
folder (they are git-ignored). The runner reads a CSV once and caches it as `log_cache.npz`.

## BPIC19 (procurement): 3-way matching, invoice before goods receipt

Source: Qureshi, A. R. A.: *BPIC19 event logs: 3-way matching, invoice before goods receipt*, Zenodo,
https://zenodo.org/records/17295283 (DOI 10.5281/zenodo.17295283, CC BY 4.0).
The log is derived from the BPI Challenge 2019 dataset and contains 217,406 of the 251,734 cases of the original log.

1. Download `BPIC19_3way_IbeforeGR_standardPO_complete.xes` (about 560 MB).
2. Convert it to CSV and save it as `data/process_execution_data.csv`, for example with PM4Py:

       import pm4py
       log = pm4py.read_xes("BPIC19_3way_IbeforeGR_standardPO_complete.xes")
       df = pm4py.convert_to_dataframe(log)
       df.to_csv("data/process_execution_data.csv", index=False)

3. Check: 217,406 traces, 1,214,244 events, 28 activities.

Columns used by the runner: `case:concept:name` (case), `concept:name` (activity), `time:timestamp`,
`org:resource`, `Cumulative net worth (EUR)` (data condition).

## BPIC17 (finance): loan applications

Source: BPI Challenge 2017, 4TU.ResearchData (https://doi.org/10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b).
Export the log to CSV and save it as `data/event_log_BPIC17.csv`. Only rows with `lifecycle:transition = complete`
are used (the runner filters them): 31,509 traces, 475,306 events, 24 activities.

Columns used: `case:concept:name`, `concept:name`, `time:timestamp`, `org:resource`,
`case:RequestedAmount` (data condition), `lifecycle:transition` (filter).