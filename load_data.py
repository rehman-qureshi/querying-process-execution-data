import json
from typing import Any

import pandas as pd
import pm4py


def load_events_logs(file_path: str) -> pd.DataFrame:
    """Load an XES event log and sort events by case and timestamp."""
    event_log = pm4py.read_xes(file_path)
    events = pm4py.convert_to_dataframe(event_log)

    if events.empty:
        raise ValueError(
            "The events logs dataframe is empty. Please check the input file."
        )

    return events.sort_values(
        by=["case:concept:name", "time:timestamp"],
        ascending=[True, True],
    ).reset_index(drop=True)


def load_declarative_constraints(file_path: str) -> list[dict[str, Any]]:
    """Load the declarative constraints from a JSON repository."""
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    return data["constraints"]


def load_data_function(
    events_logs_path: str, declarative_constraints_path: str
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Load the event log and its declarative constraints."""
    event_logs = load_events_logs(events_logs_path)
    declarative_constraints = load_declarative_constraints(declarative_constraints_path)

    return event_logs, declarative_constraints