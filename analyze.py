import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from itertools import chain
import json
from util import open_config, open_saved
from scipy import stats


def conf_interval(data, conf=0.95):
    mean = np.mean(data)
    sem = stats.sem(data)  # Standard error of the mean
    interval = stats.t.interval(conf, len(data)-1, loc=mean, scale=sem)
    return interval

def analyze(results):
    zipped_results = [list(chain.from_iterable(r)) for r in zip(*results)]
    means, conf_ints, maxs, mins = [], [], [], []

    for r in zipped_results: 
        conf_ints.append(conf_interval(r))
        means.append(np.nanmean(r))
        maxs.append(max(r))
        mins.append(min(r))

    return [means, conf_ints, maxs, mins]


def save_results(results):
    config = open_config()
    data_dict = {
        "title": f"{'Web search' if config["traffic_type"] == 1 else 'Data mining'}, 20 Mbps, 1ms",
        "mean": results[0],
        "conf95": results[1],
        "max": results[2],
        "min": results[3],
    }
    saved = open_saved()
    saved["data"][f"e{len(saved["data"])}"] = data_dict
    
    with open("saved.json", "w") as f:
        json.dump(saved, f, indent=4)


def display_results(results):
    zresults = zip(*results)
    form = ["Mean: ", "conf95: ", "max: ", "min: "]
    print("--- Results ---")
    for i, line in enumerate(zresults, start=1):
        formatted = []
        for label, val in zip(form, line):
            if isinstance(val, tuple):
                val_str = f"({round(val[0], 3)}, {round(val[1], 3)})"
            else:
                val_str = f"{round(val, 3)}"
            formatted.append(f"{label}{val_str}")
        print(f"{i} flows/s: {formatted}")


def plotResults(entry_name):
    saved_results = open_saved()
    data = saved_results["data"][entry_name]
    title = data["title"]
    mean = np.asarray(data["mean"], dtype=float)
    xaxis = np.arange(1, len(mean) + 1)
    
    # Debug: Check what conf95 actually contains
    conf95_data = data["conf95"]
    print(f"DEBUG: conf95 type = {type(conf95_data)}")
    print(f"DEBUG: conf95 = {conf95_data}")
    
    # Handle different possible formats
    if isinstance(conf95_data, (list, tuple)) and len(conf95_data) == 2:
        # Expected format: (low_list, high_list)
        low, high = map(lambda v: np.asarray(v, dtype=float), conf95_data)
    elif isinstance(conf95_data, (list, tuple)) and len(conf95_data) > 0:
        # Maybe it's a list of (low, high) pairs per data point?
        conf95_array = np.asarray(conf95_data, dtype=float)
        if conf95_array.ndim == 2 and conf95_array.shape[1] == 2:
            low = conf95_array[:, 0]
            high = conf95_array[:, 1]
        else:
            raise ValueError(f"Unexpected conf95 format: shape={conf95_array.shape}")
    else:
        raise ValueError(f"Cannot parse conf95: type={type(conf95_data)}, len={len(conf95_data) if hasattr(conf95_data, '__len__') else 'N/A'}")
    
    mini = np.asarray(data["min"], dtype=float)
    maxi = np.asarray(data["max"], dtype=float)
    
    # sanity check
    n = len(mean)
    assert all(len(arr) == n for arr in (low, high, mini, maxi)), "Length mismatch in inputs"
    
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # mean bars behind everything else
    ax.bar(xaxis, mean, zorder=1)
    
    box_width = 0.55
    for xi, lo, hi, mn, mx in zip(xaxis, low, high, mini, maxi):
        # 95% CI box
        rect = plt.Rectangle(
            (xi - box_width/2, lo),
            box_width,
            hi - lo,
            facecolor=(1, 1, 1, 0),
            edgecolor="black",
            linewidth=1.2,
            zorder=3
        )
        ax.add_patch(rect)
        
        # whiskers to min/max
        ax.plot([xi, xi], [mn, lo], color="black", linewidth=1.0, zorder=2)
        ax.plot([xi, xi], [hi, mx], color="black", linewidth=1.0, zorder=2)
        
        cap_w = box_width * 0.6
        ax.plot([xi - cap_w/2, xi + cap_w/2], [mn, mn], color="black", linewidth=1.0, zorder=2)
        ax.plot([xi - cap_w/2, xi + cap_w/2], [mx, mx], color="black", linewidth=1.0, zorder=2)
    
    ax.set_xlabel("Traffic Intensity (flows/s)")
    ax.set_ylabel("Flow Completion Time (s)")
    ax.set_title(title)
    fig.tight_layout()
    plt.savefig(title, dpi=300, bbox_inches="tight")
