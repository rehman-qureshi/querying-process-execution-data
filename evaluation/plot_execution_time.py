from pathlib import Path
import matplotlib.pyplot as plt

DATA_SIZES = [5, 25, 50, 100, 217]
DATA_SIZE_LABELS = ["5K", "25K", "50K", "100K", "217K"]
EXECUTION_TIMES_SECONDS = {
    "Q1": [1.2277, 5.742833, 11.1776, 22.268, 49.0068],
    "Q2": [0.4602, 2.1901, 4.4289, 9.128866, 23.349],
    "Q3": [0.40343, 2.06983, 4.2987, 8.7803, 18.403],
    "Q4": [0.5695, 2.414866, 4.5664, 9.09433, 20.52066],
    "Q5": [0.9271, 4.749066, 9.7054, 18.7977, 40.04633],
    "Q6": [0.3901, 1.8722, 3.3624, 6.406, 14.5353],
}
COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"]
MARKERS = ["o", "s", "^", "D", "v", "P"]

def plot_execution_time_function() -> None:
    # Ensure no lingering figures cause overlap
    plt.close("all")

    style = {
        "font.family": "serif",
        "font.size": 9,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 8,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }

    with plt.rc_context(style):
        fig, ax = plt.subplots(figsize=(6.4, 4.2))

        for (query, values), color, marker in zip(
            EXECUTION_TIMES_SECONDS.items(), COLORS, MARKERS
        ):
            ax.plot(
                DATA_SIZES,
                values,
                label=query,
                color=color,
                marker=marker,
                markersize=5,
                markeredgecolor="white",
                markeredgewidth=0.7,
                linewidth=1.8,
            )

        ax.set_xlabel("Data Size [Number of traces]")
        ax.set_ylabel("Execution time [seconds]")
        ax.set_xticks(DATA_SIZES, DATA_SIZE_LABELS)
        ax.set_xlim(0, 230)
        ax.set_ylim(0, 55)
        ax.set_yticks(range(0, 56, 10))
        ax.set_axisbelow(True)
        ax.grid(axis="y", color="#D9DEE7", linewidth=0.7)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(length=3, color="#555555")

        # Place legend cleanly inside the upper-left open space
        ax.legend(
            title="Business Question",
            loc="upper left",
            frameon=True,
            framealpha=0.9,
            edgecolor="#D9DEE7",
            labelspacing=0.4,
            handletextpad=0.5,
        )
        
        # Balanced margins matching your memory plot for consistency
        fig.subplots_adjust(left=0.12, right=0.95, bottom=0.15, top=0.92)

        output_path = Path(__file__).with_name("execution_time.pdf")
        fig.savefig(output_path, format="pdf", bbox_inches="tight")
        plt.close(fig)
        print(f"Saved clean {output_path}")
