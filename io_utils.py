#Purpose: Read/write CSV
import numpy as np
import csv

def load_csv(path):
    with open(path, 'r', newline='') as f:
        first_line = f.readline()
        delimiter = '\t' if '\t' in first_line else ','
        f.seek(0)
        reader = csv.reader(f, delimiter=delimiter)

        x_vals, y_vals = [], []
        for row in reader:
            if not row:
                continue
            nums = [float(v) for v in row if v.strip()]
            if len(nums) == 1:
                y_vals.append(nums[0])
            elif len(nums) >= 2:
                x_vals.append(nums[0])
                y_vals.append(nums[1])
        if len(x_vals) == 0 and len(y_vals) > 0:
            x_vals = list(range(len(y_vals)))
        
        # convert to numpy
        x_arr = np.array(x_vals, dtype=float)
        y_arr = np.array(y_vals, dtype=float)

        # sort by x ascending
        order = np.argsort(x_arr)
        x_arr = x_arr[order]
        y_arr = y_arr[order]

        # aggregate duplicates (SUM is typical for position counts)
        uniq_x, idx_start = np.unique(x_arr, return_index=True)
        agg_y = []
        for i, x0 in enumerate(uniq_x):
            j0 = idx_start[i]
            j1 = idx_start[i + 1] if i + 1 < len(idx_start) else len(x_arr)
            agg_y.append(y_arr[j0:j1].sum())
        return np.array(x_vals), np.array(y_vals)

def export_peaks_csv(path, rows):
    fieldnames = ['index', 'value', 'region_id', 'W_region', 'R_region']

    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)