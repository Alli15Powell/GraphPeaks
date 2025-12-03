# ------------------------------------------------------------
# Detection Pipeline (Threshold + Wavelet)
# ------------------------------------------------------------
import numpy as np
from constants import APEX_MIN_HEIGHT, APEX_MIN_SEPARATION, ALPHA
from scipy.signal import find_peaks

# ============================================================
# ------------------ Wavelet Implementations ------------------
# ============================================================

def _ricker_wavelet(width):
    """Discrete Ricker (Mexican-hat) wavelet."""
    A = 2 / (np.sqrt(3 * width) * (np.pi ** 0.25))
    points = int(10 * width)
    x = np.linspace(-points / 2, points / 2, points)
    xsq = (x / width) ** 2
    return A * (1 - xsq) * np.exp(-xsq / 2)


def _cwt(data, widths):
    """Custom Continuous Wavelet Transform using Ricker kernel."""
    cwt_matrix = np.zeros((len(widths), len(data)))
    for i, w in enumerate(widths):
        wavelet = _ricker_wavelet(w)
        conv = np.convolve(data, wavelet, mode="same")
        cwt_matrix[i, :] = conv
    return cwt_matrix


# ============================================================
# ---------------- Threshold Mode Helper Functions ------------
# ============================================================

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
            pL = i
            pR = i
            v = data[i]

            while pR + 1 <= end and data[pR + 1] == v:
                pR += 1

            left = data[pL - 1] if pL > start else -float('inf')
            right = data[pR + 1] if pR < end else -float('inf')

            if pR > pL:
                if v > left and v > right:
                    rep = (pL + pR) // 2
                    cands.append([rep, v])
                i = pR + 1
                continue

            left = data[i - 1] if i > start else -float('inf')
            right = data[i + 1] if i < end else -float('inf')
            if data[i] > left and data[i] >= right:
                cands.append([i, data[i]])

            i += 1

        local_max_per_island.append(cands)

    return local_max_per_island


def width_per_island(data, islands, local_max, ALPHA):
    widths_per_island = []
    halves_by_island = []

    for n, (start, end) in enumerate(islands):
        widths = []
        halves_map = {}

        for idx, val in local_max[n]:
            threshold = ALPHA * val

            left_half = 0
            j = idx - 1
            while j >= start and data[j] >= threshold:
                left_half += 1
                j -= 1

            right_half = 0
            j = idx + 1
            while j <= end and data[j] >= threshold:
                right_half += 1
                j += 1

            width = left_half + right_half + 1
            widths.append(width)
            halves_map[idx] = (left_half, right_half)

        if len(widths) == 1:
            W_region = widths[0]
        elif len(widths) > 1:
            widths.sort()
            mid = len(widths) // 2
            W_region = int((widths[mid - 1] + widths[mid]) / 2) if len(widths) % 2 == 0 else widths[mid]
        else:
            W_region = (end - start + 1)

        W_region = max(3, min(W_region, end - start + 1))
        widths_per_island.append(W_region)
        halves_by_island.append(halves_map)

    return widths_per_island, halves_by_island


def radius_from_width(width_per_island):
    radius_per_island = []
    for n in width_per_island:
        radius = max(2, round(n / 3))
        radius_per_island.append(radius)
    return radius_per_island


def flatten_candidates(local_max):
    global_candidates = []
    for region_id, n in enumerate(local_max):
        for index, value in n:
            global_candidates.append([index, value, region_id])
    return global_candidates


def apex_min_separation(global_candidates, radius_per_island):
    cands = sorted(global_candidates, key=lambda p: (-p[1], p[0]))
    kept = []
    for idx, val, region_id in cands:
        R = max(2, int(radius_per_island[region_id]))
        keep = True
        for k_idx, k_val, k_region in kept:
            if k_region != region_id:
                continue
            if abs(idx - k_idx) < R:
                keep = False
                break
        if keep:
            kept.append([idx, val, region_id])
    kept.sort(key=lambda p: (p[2], p[0]))
    return kept


# ============================================================
# --------------------- Threshold Pipeline --------------------
# ============================================================

def run_pipeline(data, mode="threshold"):
    if mode == "wavelet":
        return run_wavelet_mode(data)

    islands = islands_of_activity(data)
    local_max = find_local_maxima(islands, data)
    W_by_island, halves_by_island = width_per_island(data, islands, local_max, ALPHA)
    R_by_island = radius_from_width(W_by_island)
    global_cands = flatten_candidates(local_max)
    kept = apex_min_separation(global_cands, R_by_island)

    rows = []
    for (index, value, region_id) in kept:
        left_half, right_half = halves_by_island[region_id].get(index, (0, 0))
        start_idx = index - left_half
        end_idx = index + right_half
        width_idx = end_idx - start_idx + 1

        rows.append({
            "index": int(index),
            "value": float(value),
            "region_id": int(region_id),
            "W_region": int(W_by_island[region_id]),
            "R_region": int(R_by_island[region_id]),
            "span_idx": (int(start_idx), int(end_idx)),
            "width_idx": int(width_idx),
        })

    return {
        "islands": islands,
        "local_max": local_max,
        "W_by_island": W_by_island,
        "R_by_island": R_by_island,
        "kept_rows": rows,
        "wavelet_summary": None,
        "cwt_matrix": None,
        "widths": None,
    }


# ============================================================
# ------------------------ Wavelet Mode ------------------------
# ============================================================

def run_wavelet_mode(data, widths=np.arange(1, 50)):
    """
    Full wavelet-based peak detection + visualization support:
        - CWT matrix (for heatmap)
        - wavelet summary curve
        - peak detection using wavelet summary
    """

    # 1. Compute CWT
    cwt_matrix = _cwt(data, widths)

    # 2. Wavelet energy / summary curve
    cwt_sum = np.sum(np.abs(cwt_matrix), axis=0)

    # 3. Peak detection on wavelet summary
    prominence = np.median(cwt_sum) * 0.5
    peaks, _ = find_peaks(cwt_sum, prominence=prominence)

    # 4. Create UI rows just like threshold mode
    rows = []
    for p in peaks:
        rows.append({
            "index": int(p),
            "value": float(data[p]),
            "region_id": -1,       # wavelet mode doesn't have islands
            "W_region": 0,
            "R_region": 0,
            "span_idx": (int(p), int(p)),
            "width_idx": 1,
        })

    return {
        "islands": [],
        "local_max": [],
        "W_by_island": [],
        "R_by_island": [],
        "kept_rows": rows,
        "wavelet_summary": cwt_sum,
        "cwt_matrix": cwt_matrix,
        "widths": widths,
    }
