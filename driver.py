
import sys
from load_data import load_data_function 
import warnings
from compute_average_time import compute_average_time_function

# Ignore warnings related to rustxes when reading XES files
warnings.filterwarnings(
    "ignore",
    message=r".*rustxes.*"
)
# Main function to load data and check conformance
if __name__ == "__main__":

    if len(sys.argv) != 3:
        print("Usage: python driver.py <events_logs_path> <declarative_constraints_path>")
        sys.exit(1)

    events_logs_path = sys.argv[1]
    declarative_constraints_path = sys.argv[2]


    event_logs, declarative_constraints = load_data_function(events_logs_path, declarative_constraints_path)

    # Display declarative constraints so that user can select which constraints to use for the analysis.
    if declarative_constraints:
        print("\nDeclarative Constraints:")
        for constraint in declarative_constraints:
            if constraint.get("type")=="Unary":
             print(f"{constraint['id']}. {constraint['template']}({{{', '.join(constraint['activity'])}}}) ")
            else:
             print(f"{constraint['id']}. {constraint['template']}({{{', '.join(constraint['source'])}}}, {{{', '.join(constraint['target'])}}}) ")
    
    # Research Question - Q1: How long does it take for the procurement process to clear an invoice on average?
    average_time=0.00
    id_list=["C1","C10"]
    
    selected_constraints = [constraint for constraint in declarative_constraints if constraint["id"] in id_list]
    print(f"Selected constraints are {selected_constraints}")
    average_time=compute_average_time_function(event_logs,selected_constraints) 
    print(f"How long does it take for the procurement process to clear an invoice on average? {average_time}")
    