
import sys
from load_data import load_data_function 
import warnings

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
    
    