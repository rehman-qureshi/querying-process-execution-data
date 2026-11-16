from datetime import timedelta
from typing import Any

import pandas as pd


CASE_ID_COLUMN = "case:concept:name"
ACTIVITY_COLUMN = "concept:name"
TIMESTAMP_COLUMN = "time:timestamp"


def has_alternate_precedence(events: list[str], A: str, B: str) -> bool:
    """Return whether a trace satisfies AlternatePrecedence(A, B)."""
    last_relevant = None
    has_b = False

    for event in events:
        if event == A:
            last_relevant = "A"
        elif event == B:
            has_b = True
            if last_relevant != "A":
                return False
            last_relevant = "B"

    return has_b


def _completion_time(
    trace: pd.DataFrame,
    case_id: Any,
    first_activity: str,
    second_activity: str,
) -> float | None:
    initial_times = trace.loc[
        trace[ACTIVITY_COLUMN] == first_activity, TIMESTAMP_COLUMN
    ]
    final_times = trace.loc[
        trace[ACTIVITY_COLUMN] == second_activity, TIMESTAMP_COLUMN
    ]
    if initial_times.empty or final_times.empty:
        return None

    initial_time = pd.to_datetime(initial_times.iloc[0])
    final_time = pd.to_datetime(final_times.iloc[-1])
    if final_time < initial_time:
        print(
            f"Warning: In case {case_id}, the final time {final_time} is earlier "
            f"than the initial time {initial_time}. This trace will be skipped."
        )
        return None

    return (final_time - initial_time).total_seconds()


def _format_duration(seconds: float | None) -> str:
    if seconds is None or pd.isna(seconds):
        return "N/A"
    return str(timedelta(seconds=seconds))


def _print_completion_time_statistics(completion_times: list[float]) -> float | None:
    total_completion_time = sum(completion_times)
    if completion_times:
        average_completion_time = total_completion_time / len(completion_times)
        max_completion_time = max(completion_times)
        min_completion_time = min(completion_times)
        std_dev_completion_time = pd.Series(completion_times).std()
    else:
        average_completion_time = None
        max_completion_time = None
        min_completion_time = None
        std_dev_completion_time = None

    print(f"total_completion_time: {_format_duration(total_completion_time)}")
    print(f"average_completion_time: {_format_duration(average_completion_time)}")
    print(f"max_completion_time: {_format_duration(max_completion_time)}")
    print(f"min_completion_time: {_format_duration(min_completion_time)}")
    print(f"std_dev_completion_time: {_format_duration(std_dev_completion_time)}")
    return average_completion_time


def compute_average_time_function_Q1(
    process_execution_data: pd.DataFrame, constraint: dict[str, Any]
) -> float | None:
    grouped = process_execution_data.groupby(CASE_ID_COLUMN)
    completion_times = []
    activated_traces = 0
    first_activity = constraint["source"]
    second_activity = constraint["target"]
    print(f"Length of cases: {len(grouped)}")

    for case_id, trace in grouped:
        activities = trace[ACTIVITY_COLUMN].tolist()
        activity_set = set(activities)

        if constraint["type"] == "Binary":
            if first_activity in activity_set and second_activity in activity_set:
                activated_traces += 1
            conforms = has_alternate_precedence(
                activities, first_activity, second_activity
            )
        else:
            print("\nThis constraint type is not supported.")
            conforms = False

        if conforms:
            completion_time = _completion_time(
                trace, case_id, first_activity, second_activity
            )
            if completion_time is not None:
                completion_times.append(completion_time)

    print(f"Conforming traces: {len(completion_times)}")
    print(f"Activated traces: {activated_traces}")
    return _print_completion_time_statistics(completion_times)


def find_resources_function_Q2(
    process_execution_data: pd.DataFrame, constraint: dict[str, Any]
) -> None:
    grouped = process_execution_data.groupby(CASE_ID_COLUMN)
    activated_traces = 0
    conforming_traces = 0
    resource_names = []
    first_activity = constraint["source"]
    second_activity = constraint["target"]
    print(f"Length of cases: {len(grouped)}")

    for _, trace in grouped:
        activities = trace[ACTIVITY_COLUMN].tolist()
        activity_set = set(activities)

        if constraint.get("type") == "Binary":
            if first_activity in activity_set and second_activity in activity_set:
                activated_traces += 1
            conforms = has_alternate_precedence(
                activities, first_activity, second_activity
            )
        else:
            print("\nThis constraint type is not supported.")
            conforms = False

        if conforms:
            conforming_traces += 1
            resource_names.append(
                trace.loc[trace[ACTIVITY_COLUMN] == second_activity, "User"].iloc[-1]
            )

    print(f"Conforming traces: {conforming_traces}")
    print(f"Violating traces: {len(grouped) - conforming_traces}")
    print(f"Activated traces: {activated_traces}")

    top_resources = (
        pd.Series(resource_names)
        .value_counts()
        .drop(labels="NONE", errors="ignore")
        .head(5)
    )
    print(f"Top 5 resources for activity '{second_activity}':")
    print(top_resources)


def compute_average_time_function_Q3(
    process_execution_data: pd.DataFrame, constraint: dict[str, Any]
) -> None:
    grouped = process_execution_data.groupby(CASE_ID_COLUMN)
    activated_traces = 0
    conforming_traces = 0
    first_activity = constraint["source"]
    second_activity = constraint["target"]
    print(f"Length of cases: {len(grouped)}")

    for case_id, trace in grouped:
        activities = trace[ACTIVITY_COLUMN].tolist()
        activity_set = set(activities)
        conforms = False

        if constraint.get("type") == "Binary":
            if second_activity in activity_set:
                completion_time = _completion_time(
                    trace, case_id, first_activity, second_activity
                )
                if completion_time is not None and completion_time <= 259200:
                    activated_traces += 1
                    conforms = has_alternate_precedence(
                        activities, first_activity, second_activity
                    )
        else:
            print("\nThis constraint type is not supported.")

        if conforms:
            conforming_traces += 1

    print(f"Activated traces: {activated_traces}")
    print(f"Conforming traces: {conforming_traces}")


def compute_average_time_function_Q4(
    process_execution_data: pd.DataFrame, constraint: dict[str, Any]
) -> float | None:
    grouped = process_execution_data.groupby(CASE_ID_COLUMN)
    activated_traces = 0
    completion_times = []
    first_activity = constraint["source"]
    second_activity = constraint["target"]
    print(f"Length of cases: {len(grouped)}")

    for case_id, trace in grouped:
        activities = trace[ACTIVITY_COLUMN].tolist()
        activity_set = set(activities)
        activated = False
        conforms = False

        if constraint.get("type") == "Binary":
            if first_activity in activity_set:
                numerical_value = trace.loc[
                    trace[ACTIVITY_COLUMN] == first_activity,
                    "Cumulative net worth (EUR)",
                ].iloc[0]
                try:
                    numerical_value = float(numerical_value)
                except (ValueError, TypeError):
                    numerical_value = None

                if (
                    numerical_value is not None
                    and numerical_value > 500
                    and first_activity in activity_set
                ):
                    activated = True
                    conforms = has_alternate_precedence(
                        activities, first_activity, second_activity
                    )
        else:
            print("\nThis constraint type is not supported.")

        if activated:
            activated_traces += 1
            if conforms:
                completion_time = _completion_time(
                    trace, case_id, first_activity, second_activity
                )
                if completion_time is not None:
                    completion_times.append(completion_time)

    print(f"Activated traces: {activated_traces}")
    print(f"Conforming traces: {len(completion_times)}")
    return _print_completion_time_statistics(completion_times)


def compute_average_time_function_Q5(
    process_execution_data: pd.DataFrame, constraint: dict[str, Any]
) -> float | None:
    grouped = process_execution_data.groupby(CASE_ID_COLUMN)
    activated_traces = 0
    completion_times = []
    first_activity = constraint["source"]
    second_activity = constraint["target"]
    print(f"Length of cases: {len(grouped)}")

    for case_id, trace in grouped:
        activities = trace[ACTIVITY_COLUMN].tolist()
        activity_set = set(activities)

        if constraint.get("type") == "Binary":
            if first_activity in activity_set and second_activity in activity_set:
                activated_traces += 1
            conforms = has_alternate_precedence(
                activities, first_activity, second_activity
            )
        else:
            print("\nThis constraint type is not supported.")
            conforms = False

        if conforms:
            completion_time = _completion_time(
                trace, case_id, first_activity, second_activity
            )
            if completion_time is not None:
                completion_times.append(completion_time)

    print(f"Conforming traces: {len(completion_times)}")
    print(f"Activated traces: {activated_traces}")
    return _print_completion_time_statistics(completion_times)


def find_resources_function_Q6(
    process_execution_data: pd.DataFrame, constraint: dict[str, Any]
) -> None:
    grouped = process_execution_data.groupby(CASE_ID_COLUMN)
    activated_traces = 0
    conforming_traces = 0
    matching_resources = []
    first_activity = constraint["source"]
    second_activity = constraint["target"]
    print(f"Length of cases: {len(grouped)}")

    for _, trace in grouped:
        activities = trace[ACTIVITY_COLUMN].tolist()
        activity_set = set(activities)

        if constraint.get("type") == "Binary":
            if first_activity in activity_set and second_activity in activity_set:
                activated_traces += 1
            conforms = has_alternate_precedence(
                activities, first_activity, second_activity
            )
        else:
            print("\nThis constraint type is not supported.")
            conforms = False

        if conforms:
            conforming_traces += 1
            matching_resources.extend(
                trace.loc[
                    trace[ACTIVITY_COLUMN] == second_activity, "User"
                ].tolist()
            )

    print(f"Conforming traces: {conforming_traces}")
    print(f"Activated traces: {activated_traces}")

    resource_series = pd.Series(matching_resources)
    resource_counts = resource_series.value_counts()
    print(f"Resource counts for activity '{second_activity}':")
    print(resource_counts)
    unique_resources = resource_series.dropna().unique()
    print(f"Distinct resources: {len(unique_resources)}")
    print(unique_resources)


QUERY_FUNCTIONS = {
    "Q1": compute_average_time_function_Q1,
    "Q2": find_resources_function_Q2,
    "Q3": compute_average_time_function_Q3,
    "Q4": compute_average_time_function_Q4,
    "Q5": compute_average_time_function_Q5,
    "Q6": find_resources_function_Q6,
}


def execute_declarative_representation_function(
    process_execution_data: pd.DataFrame, constraint: dict[str, Any]
) -> None:
    query_function = QUERY_FUNCTIONS.get(constraint.get("id"))
    if query_function is not None:
        query_function(process_execution_data, constraint)
