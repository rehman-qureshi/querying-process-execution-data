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
    print(f"Length of cases: {len(grouped)}")
    for case_id, trace in grouped:
        # Extract activities of this trace
        activities = trace["concept:name"].tolist()
        isConform=False
        for constraint in constraints:
            if constraint.get("type") == "Binary": 
                first_events = constraint['source']
                second_events = constraint['target']
                
                isConform=has_alternate_precedence(activities, first_events, second_events)
                # If the trace is violated by at least one constraint then there is not need to check this trace anymore.
                if isConform==False:
                    break

            elif constraint.get("type") == "Unary":
                if constraint.get("template")=="AtMostOne":
                    
                    first_events = constraint['activity']
                    isConform=has_at_most_one(activities, first_events)
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
        
        # if isConform is True then conforming_traces, otherwise violating_traces 
        if isConform:
            conforming_traces[case_id] = trace
            
        else:
            violating_traces[case_id] = trace
    # Display the result
    print(f"Conforming traces: {len(conforming_traces)}")
    print(f"Violating traces: {len(violating_traces)}")
    
    # Compute a average time for procurement process to clear an invoice

    return None
  
