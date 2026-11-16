import argparse
import warnings

from execute_declarative_representation import (
    execute_declarative_representation_function,
)
from load_data import load_data_function


warnings.filterwarnings(
    "ignore",
    message=r".*rustxes.*"
)


def main() -> None:
    """Load the input files and run selected business questions."""
    parser = argparse.ArgumentParser(
        description="Query process execution data using declarative constraints."
    )
    parser.add_argument(
        "process_execution_data_path",
        help="Path to the input XES event log.",
    )
    parser.add_argument(
        "declarative_repository_path",
        help="Path to the constraints JSON file.",
    )
    args = parser.parse_args()

    process_execution_data, declarative_constraints = load_data_function(
        args.process_execution_data_path,
        args.declarative_repository_path,
    )

    # Display the declarative form of each configured question.
    if declarative_constraints:
        print("\nDeclarative Representation of each business question:")
        for constraint in declarative_constraints:
            print(
                f"{constraint['id']}: "
                f"{{{constraint['template']}({constraint['source']}, "
                f"{constraint['target']})[{constraint['subscript']}]}}"
            )

    while True:
        selected_option = input(
            "\nEnter the ID of the business question to run, or e to exit: "
        ).strip()

        if selected_option == "e":
            print("Exiting the program ...")
            break

        constraint = next(
            (
                item
                for item in declarative_constraints
                if item["id"] == selected_option
            ),
            None,
        )
        if constraint is None:
            print("Invalid ID for a business question. Please try again.")
            continue

        print(f"You selected Business Question: {selected_option}")
        execute_declarative_representation_function(process_execution_data, constraint)


if __name__ == "__main__":
    main()
