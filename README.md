# Querying Process Execution Data

This project loads an XES event log and a JSON declarative-constraint repository, then lets the user run one of the configured business questions against the log.

## Requirements

- Python 3.12
- The Python dependencies listed in [`requirements.txt`](requirements.txt)

Create an environment and install the dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

From the repository root, provide the paths to an XES event log and a constraint JSON file:

```powershell
python driver.py "C:\path\to\process_execution_data.xes" "declarative_repository.json"
```

The program displays the constraints and prompts for an ID (for example, `Q1` through `Q6`). Enter `e` to exit. The event log is sorted by case ID and event timestamp before the queries run.

## Repository contents

- `driver.py` — command-line entry point.
- `load_data.py` — reads and prepares the XES log and JSON constraints.
- `execute_declarative_representation.py` — implements the business-question queries.
- `declarative_repository.json` — the six configured question definitions.
- `evaluation/` — scripts and measurement values used to generate the performance plots.

### Usage

Download the event log as [`process_execution_data.xes`](https://zenodo.org/records/17295283) file in the current folder. 

Save the downloaded XES file locally and use its path as the first argument to `driver.py`, as shown above. The loader reads the XES event log directly

The evaluation plot scripts use measurement values embedded in their Python source. They regenerate the figures, but do not rerun the process queries or reproduce the original benchmark measurements.

## Evaluation plots

From the repository root, generate the plots with:

```powershell
python evaluation\performance_analysis.py
```

The PDF figures are written to `evaluation/` and are excluded from Git.
