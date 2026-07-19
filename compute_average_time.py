import pandas as pd
from datetime import timedelta

def has_alternate_precedence(events, A_list, B_list):
    """Return True if the trace satisfies AlternatePrecedence(A,B).

    Alternate Precedence means:
    - Every occurrence of an event in B_list must be preceded by at least an event in A_list.
    - Between two consecutive B events there must be at least one A event.

    This implementation treats traces with no B events as not satisfying the constraint,
    because this script classifies cases with first event but no second event as False.
    """
    last_relevant = None
    has_b = False

    for e in events:
        if e in A_list:
            last_relevant = "A"
        elif e in B_list:
            has_b = True
            # B must be preceded by an A, and the last relevant event must be A
            if last_relevant != "A":
                return False
            last_relevant = "B"

    return has_b
#---------------------------------------------
def has_at_most_one(events, A_list):
    """Return True if the trace satisfies AtMostOne(A).

    At Most One means:
    - For every event type listed in A_list, there can be at most one occurrence in the trace.
    """
    for a in A_list:
        if events.count(a) > 1:
            return False
    return True
# -----------------------------
def has_end(events, A_list):
    """Return True if the trace satisfies End(A).

    End means:
    - The last event in the trace must be an event in A_list.
    """
    return events[-1] in A_list if events else False
#---------------------------------------------
# Function to compute average time
def compute_average_time_function(event_logs,constraints):
    print("In average time function")
    
    # Preprocess event logs
       
    grouped = event_logs.groupby("case:concept:name")
    conforming_traces={}
    violating_traces={}
    activation_binary=[]
    activation_unary=[]
    completion_time_per_trace={}
    print(f"Length of cases: {len(grouped)}")
    for case_id, trace in grouped:
        # Extract activities of this trace
        activities = trace["concept:name"].tolist()
        isConform=False
        for constraint in constraints:
            if constraint.get("type") == "Binary": 
                first_events = constraint['source']
                second_events = constraint['target']
                 
                activation_binary = [second_events] if isinstance(second_events, str) else second_events
                isConform=has_alternate_precedence(activities, first_events, second_events)
                # If the trace is violated by at least one constraint then there is not need to check this trace anymore.
                if isConform==False:
                    break

            elif constraint.get("type") == "Unary":
                if constraint.get("template")=="AtMostOne":

                    first_events = constraint['activity']
                    isConform=has_at_most_one(activities, first_events)
                    
                    activation_unary = [first_events] if isinstance(first_events, str) else first_events
                    # If the trace is violated by at least one constraint then there is not need to check this trace anymore.
                    if isConform==False:
                        break
                
                elif constraint.get("template")=="End":

                    first_events = constraint['activity']
                    isConform=has_end(activities, first_events)
                    # If the trace is violated by at least one constraint then there is not need to check this trace anymore.
                    if isConform==False:
                        break
               
                else:
                    print("\nThis constraint template is not supported.")     
            else:
                print("\nThis constraint type is not supported.")
        
        #if isConform is True then conforming_traces, otherwise violating_traces 
        if isConform:
            conforming_traces[case_id] = trace
                                      
            unary_matching = trace[trace["concept:name"].isin(activation_unary)] 
            binary_matching = trace[trace["concept:name"].isin(activation_binary)]

            if not unary_matching.empty and not binary_matching.empty:
                timestamp_unary=pd.to_datetime(unary_matching.iloc[0]["time:timestamp"])
                timestamp_binary=pd.to_datetime(binary_matching.iloc[0]["time:timestamp"])
                completion_time=(timestamp_binary-timestamp_unary).total_seconds()
                completion_time_per_trace[case_id]=completion_time    
        else:
            violating_traces[case_id] = trace
    # Display the result
    print(f"Conforming traces: {len(conforming_traces)}")
    print(f"Violating traces: {len(violating_traces)}")
    # Compute total time
    total_completion_time = sum(completion_time_per_trace.values())
    # Compute average time
    average_completion_time = total_completion_time / len(completion_time_per_trace) if completion_time_per_trace else None
    # Compute maximum completion time
    #max_completion_time=max(completion_time_per_trace)
    max_key = max(completion_time_per_trace, key=completion_time_per_trace.get)
    max_value = completion_time_per_trace[max_key]
    # Compute minimum completion time
    #min_completion_time=min(completion_time_per_trace)
    min_key = min(completion_time_per_trace, key=completion_time_per_trace.get)
    min_value = completion_time_per_trace[min_key]
    # timedelta function (from datetime library) is used to represent seconds into readable format
    print(f"total_completion_time: {timedelta(seconds=total_completion_time)}")
    print(f"average_completion_time: {timedelta(seconds=average_completion_time)}")
    print(f"max_completion_time: {timedelta(seconds=max_value)}")
    print(f"min_completion_time: {timedelta(seconds=min_value)}")
    
    # Return a average time for procurement process to clear an invoice
    return average_completion_time
  
