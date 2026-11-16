from pathlib import Path
import matplotlib.pyplot as plt

DATA_SIZES = [5, 25, 50, 100, 217]
DATA_SIZE_LABELS = ["5K", "25K", "50K", "100K", "217K"]
MEMORY_USAGE_MB = {
    "Q1": [11.676, 74.603, 124.57, 170.216, 198.933],
    "Q2": [15.006, 22.716, 24.143, 45.233, 48.613],
    "Q3": [11.606, 74.74, 177.05, 356.45, 614.646],
    "Q4": [13.6033, 73.5833, 174.2766, 324.0366, 429.21],
    "Q5": [15.956, 78.836, 145.153, 171.086, 185.37],
    "Q6": [12.56, 78.963, 175.53, 168.743, 160.183],
}
COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"]
MARKERS = ["o", "s", "^", "D", "v", "P"]

def plot_memory_usage_function() -> None:
    # Close any lingering/open figures to prevent overlapping plots
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
            MEMORY_USAGE_MB.items(), COLORS, MARKERS
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
        ax.set_ylabel("Memory usage [MB]")
        ax.set_xticks(DATA_SIZES, DATA_SIZE_LABELS)
        ax.set_xlim(0, 230)
        ax.set_ylim(0, 700)
        ax.set_yticks(range(0, 701, 100))
        ax.set_axisbelow(True)
        ax.grid(axis="y", color="#D9DEE7", linewidth=0.7)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(length=3, color="#555555")

        ax.legend(
            title="Business Question",
            loc="upper left",
            frameon=True,
            framealpha=0.9,
            edgecolor="#D9DEE7",
            labelspacing=0.4,
            handletextpad=0.5,
        )
        
        fig.subplots_adjust(left=0.12, right=0.95, bottom=0.15, top=0.92)

        output_path = Path(__file__).with_name("memory_usage.pdf")
        fig.savefig(output_path, format="pdf", bbox_inches="tight")
        plt.close(fig)
        print(f"Saved clean {output_path}")
