import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from itertools import chain
import json
from util import open_config, open_saved
from scipy import stats
import math


def conf_interval(data, conf=0.95):
    mean = np.mean(data)
    sem = stats.sem(data)
    interval = stats.t.interval(conf, len(data)-1, loc=mean, scale=sem)
    return interval

def analyze(results):
    zipped_results = [list(chain.from_iterable(r)) for r in zip(*results)]
    means, conf95, conf99 = [], [], []

    for r in zipped_results: 
        clean_r = [v for v in r if not math.isnan(v)]
        conf95.append(conf_interval(clean_r, 0.95))
        conf99.append(conf_interval(clean_r, 0.99))
        means.append(np.mean(clean_r))

    return [means, conf95, conf99]


def save_results(results):
    config = open_config()
    data_dict = {
        "title": f"{'Web search' if config["traffic_type"] == 1 else 'Data mining'}, {config["bw"]} Mbps, {config["delay"]}",
        "mean": results[0],
        "conf95": results[1],
        "conf99": results[2],
    }
    saved = open_saved()
    saved["data"][f"e{len(saved["data"])}"] = data_dict
    
    with open("saved.json", "w") as f:
        json.dump(saved, f, indent=4)


def display_results(results):
    zresults = zip(*results)
    form = ["Mean: ", "conf95: ", "conf99: "]
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
   
    conf95_data = data["conf95"]

    if isinstance(conf95_data, (list, tuple)) and len(conf95_data) == 2:
        # Expected format: (low_list, high_list)
        low95, high95 = map(lambda v: np.asarray(v, dtype=float), conf95_data)
    elif isinstance(conf95_data, (list, tuple)) and len(conf95_data) > 0:
        # Maybe it's a list of (low, high) pairs per data point?
        conf95_array = np.asarray(conf95_data, dtype=float)
        if conf95_array.ndim == 2 and conf95_array.shape[1] == 2:
            low95 = conf95_array[:, 0]
            high95 = conf95_array[:, 1]
        else:
            raise ValueError(f"Unexpected conf95 format: shape={conf95_array.shape}")
    else:
        raise ValueError(f"Cannot parse conf95: type={type(conf95_data)}, len={len(conf95_data) if hasattr(conf95_data, '__len__') else 'N/A'}")
   
    # Handle conf99 the same way
    conf99_data = data["conf99"]
    if isinstance(conf99_data, (list, tuple)) and len(conf99_data) == 2:
        low99, high99 = map(lambda v: np.asarray(v, dtype=float), conf99_data)
    elif isinstance(conf99_data, (list, tuple)) and len(conf99_data) > 0:
        conf99_array = np.asarray(conf99_data, dtype=float)
        if conf99_array.ndim == 2 and conf99_array.shape[1] == 2:
            low99 = conf99_array[:, 0]
            high99 = conf99_array[:, 1]
        else:
            raise ValueError(f"Unexpected conf99 format: shape={conf99_array.shape}")
    else:
        raise ValueError(f"Cannot parse conf99: type={type(conf99_data)}, len={len(conf99_data) if hasattr(conf99_data, '__len__') else 'N/A'}")
   
    # sanity check
    n = len(mean)
    assert all(len(arr) == n for arr in (low95, high95, low99, high99)), "Length mismatch in inputs"
   
    fig, ax = plt.subplots(figsize=(8, 6))
   
    # mean bars behind everything else
    ax.bar(xaxis, mean, zorder=1)
   
    box_width = 0.55
    for xi, lo95, hi95, lo99, hi99 in zip(xaxis, low95, high95, low99, high99):
        # 95% CI box
        rect = plt.Rectangle(
            (xi - box_width/2, lo95),
            box_width,
            hi95 - lo95,
            facecolor=(1, 1, 1, 0),
            edgecolor="black",
            linewidth=1.2,
            zorder=3
        )
        ax.add_patch(rect)
       
        # whiskers to 99% CI
        ax.plot([xi, xi], [lo99, lo95], color="black", linewidth=1.0, zorder=2)
        ax.plot([xi, xi], [hi95, hi99], color="black", linewidth=1.0, zorder=2)
       
        cap_w = box_width * 0.6
        ax.plot([xi - cap_w/2, xi + cap_w/2], [lo99, lo99], color="black", linewidth=1.0, zorder=2)
        ax.plot([xi - cap_w/2, xi + cap_w/2], [hi99, hi99], color="black", linewidth=1.0, zorder=2)
   
    ax.set_xlabel("Traffic Intensity (flows/s)")
    ax.set_ylabel("Flow Completion Time (s)")
    ax.set_title(title)
    fig.tight_layout()
    plt.savefig(title, dpi=300, bbox_inches="tight")
