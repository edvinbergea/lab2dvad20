import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from itertools import chain
import json

def analyze(results):
    zipped_results = [list(chain.from_iterable(r)) for r in zip(*results)]
    means, percentile95, percentile99, percentile5, percentile1 = [], [], [], [], []

    for r in zipped_results: 
        means.append(np.nanmean(r))
        percentile95.append(np.nanpercentile(r, 95))
        percentile99.append(np.nanpercentile(r, 99))
        percentile5.append(np.nanpercentile(r, 5))
        percentile1.append(np.nanpercentile(r, 1))

    return [means, percentile95, percentile99, percentile5, percentile1]

def plotResults(saved_results, entry_name):
    data = saved_results["data"][entry_name]
    title = data["title"]

    xaxis = np.arange(1, len(data["mean"])+1)
    p5 = data["p5"]
    p95 = data["p95"]
    p1 = data["p1"]
    p99 = data["p99"]

    fig, ax = plt.subplots(figsize=(8,6))
    ax.bar(xaxis, np.array(data["mean"]))
    box_width = 0.55
    for xi, lo5, hi95, lo1, hi99 in zip(xaxis, p5, p95, p1, p99):
        rect = plt.Rectangle(
            (xi - box_width/2, lo5),
            box_width,
            hi95 - lo5,
            facecolor=(1,1,1,0),
            edgecolor="black",
            linewidth=1.2,
            zorder=3
        )
        ax.add_patch(rect)

        ax.plot([xi, xi], [lo1, lo5], color="black", linewidth=1.0, zorder=2)
        ax.plot([xi, xi], [hi95, hi99], color="black", linewidth=1.0, zorder=2)
        cap_w = box_width * 0.6
        ax.plot([xi - cap_w/2, xi + cap_w/2], [lo1, lo1], color="black", linewidth=1.0, zorder=2)
        ax.plot([xi - cap_w/2, xi + cap_w/2], [hi99, hi99], color="black", linewidth=1.0, zorder=2)

    ax.set_xlabel("Traffic Intensity (flows/s)")
    ax.set_ylabel("Flow Completion Time (s)")
    ax.set_title("title")
    plt.savefig(title, dpi=300, bbox_inches="tight")

def displayResults(results):
    zresults = zip(*results)
    form = ["Mean: ", "95th: ", "99th: ", "Max: ", "Min: "]
    print("--- Results ---")
    i = 1
    for line in zresults:
        print(f"{i} flows/s: {zip(form, line)}")
        i+=1

def saveResults(results, saved_results, config):
    data_dict = {
        "title": f"{'Web search' if config["flow_type"] == 1 else 'Data mining'}, {config["delay"]}, ({config["l1_bw"]},{config["l2_bw"]},{config["l3_bw"]}) Mbps",
        "mean": results[0],
        "p95": results[1],
        "p99": results[2],
        "p5": results[3],
        "p1": results[4]
    }
    saved_results["data"][f"e{len(saved_results["data"])}"] = data_dict
    
    with open("saved_results.json", "w") as f:
        json.dump(saved_results, f, indent=4)