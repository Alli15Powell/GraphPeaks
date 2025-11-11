#Detection Pipeline
import numpy as np
import matplotlib.pyplot as plt
from constants import APEX_MIN_HEIGHT, APEX_MIN_SEPARATION, ALPHA
from scipy.signal import find_peaks

# --- lightweight internal wavelet implementation ---
def _ricker_wavelet(width):
    """Discrete Ricker (Mexican-hat) wavelet."""
    A = 2 / (np.sqrt(3 * width) * (np.pi ** 0.25))
    points = int(10 * width)
    x = np.linspace(-points / 2, points / 2, points)
    xsq = (x / width) ** 2
    return A * (1 - xsq) * np.exp(-xsq / 2)

def _cwt(data, widths):
    """Very small custom Continuous Wavelet Transform using Ricker kernel."""
    cwt_matrix = np.zeros((len(widths), len(data)))
    for i, w in enumerate(widths):
        wavelet = _ricker_wavelet(w)
        conv = np.convolve(data, wavelet, mode="same")
        cwt_matrix[i, :] = conv
    return cwt_matrix

# ----------------------------------------------------
# threshold-based helper functions
# ----------------------------------------------------
def islands_of_activity(data):
    new_start = True
    islands = []
    start = None
    for index, value in enumerate(data):
        if value >= APEX_MIN_HEIGHT and new_start:
            start = index
            new_start = False
        elif value < APEX_MIN_HEIGHT and not new_start:
            end = index - 1
            new_start = True
            islands.append([start, end])
    if not new_start and start is not None:
        islands.append([start, len(data) - 1])
    return islands

def find_local_maxima(islands, data):
    local_max_per_island = []
    for start, end in islands:
        cands = []
        i = start
        while i <= end:
            pL = i; pR = i; v = data[i]
            while pR + 1 <= end and data[pR + 1] == v:
                pR += 1
            left = data[pL - 1] if pL > start else -float('inf')
            right = data[pR + 1] if pR < end else -float('inf')
            if pR > pL:
                if v > left and v > right:
                    cands.append([(pL + pR)//2, v])
                i = pR + 1; continue
            left = data[i - 1] if i > start else -float('inf')
            right = data[i + 1] if i < end else -float('inf')
            if data[i] > left and data[i] >= right:
                cands.append([i, data[i]])
            i += 1
        local_max_per_island.append(cands)
    return local_max_per_island

def width_per_island(data, islands, local_max, ALPHA):
    widths_per_island = []
    for n, (start, end) in enumerate(islands):
        widths = []
        for idx, val in local_max[n]:
            thr = ALPHA * val
            left = 0; j = idx - 1
            while j >= start and data[j] >= thr: left += 1; j -= 1
            right = 0; j = idx + 1
            while j <= end and data[j] >= thr: right += 1; j += 1
            widths.append(left + right + 1)
        if widths:
            widths.sort(); mid = len(widths)//2
            W = int((widths[mid-1]+widths[mid])/2) if len(widths)%2==0 else widths[mid]
        else:
            W = (end - start + 1)
        W = max(3, min(W, end - start + 1))
        widths_per_island.append(W)
    return widths_per_island

def radius_from_width(width_per_island):
    return [max(2, round(w/3)) for w in width_per_island]

def flatten_candidates(local_max):
    return [[i,v,r] for r, arr in enumerate(local_max) for i,v in arr]

def apex_min_separation(global_candidates, radius_per_island):
    cands = sorted(global_candidates, key=lambda p:(-p[1],p[0]))
    kept = []
    for idx,val,rid in cands:
        R = max(2,int(radius_per_island[rid])); keep=True
        for k_i, k_v, k_r in kept:
            if k_r==rid and abs(idx-k_i)<R:
                keep=False; break
        if keep: kept.append([idx,val,rid])
    kept.sort(key=lambda p:(p[2],p[0]))
    return kept

# ----------------------------------------------------
# main pipeline
# ----------------------------------------------------
def run_pipeline(data, mode="threshold"):
    if mode == "wavelet":
        return run_wavelet_mode(data)

    islands = islands_of_activity(data)
    local_max = find_local_maxima(islands, data)
    W_by_island = width_per_island(data, islands, local_max, ALPHA)
    R_by_island = radius_from_width(W_by_island)
    global_cands = flatten_candidates(local_max)
    kept = apex_min_separation(global_cands, R_by_island)

    rows = [{
        "index": int(i), "value": float(v), "region_id": int(r),
        "W_region": int(W_by_island[r]), "R_region": int(R_by_island[r])
    } for (i,v,r) in kept]

    return {"islands": islands, "local_max": local_max,
            "W_by_island": W_by_island, "R_by_island": R_by_island,
            "kept_rows": rows}

# ----------------------------------------------------
# wavelet mode (independent of SciPy CWT)
# ----------------------------------------------------
def run_wavelet_mode(data, widths=np.arange(1,50)):
    """Adaptive peak detection using local Ricker CWT."""
    cwt_matrix = _cwt(data, widths)
    cwt_sum = np.sum(np.abs(cwt_matrix), axis=0)
    peaks,_ = find_peaks(cwt_sum, prominence=np.median(cwt_sum)*0.5)
    rows=[{"index":int(p),"value":float(data[p]),"region_id":-1,
           "W_region":0,"R_region":0} for p in peaks]
    return {"kept_rows": rows}
