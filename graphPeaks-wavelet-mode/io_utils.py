import pandas as pd
import numpy as np
import os

# -------------------------------------------------
# Universal file loader for CSV, TXT, and Excel
# -------------------------------------------------
def load_data(path):
    """
    Load data from .csv, .txt, .xls, or .xlsx files.
    Returns two numpy arrays (x, y).
    """
    ext = os.path.splitext(path)[1].lower()

    if ext in [".csv"]:
        df = pd.read_csv(path)
    elif ext in [".txt"]:
        # Try tab or space-delimited text
        try:
            df = pd.read_csv(path, sep="\t", header=None)
        except Exception:
            df = pd.read_csv(path, delim_whitespace=True, header=None)
    elif ext in [".xls", ".xlsx"]:
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    # Handle single-column or two-column files
    if df.shape[1] == 1:
        df.reset_index(inplace=True)
        df.columns = ["x", "y"]
    elif df.shape[1] >= 2:
        df.columns = ["x", "y"] + list(df.columns[2:])
    else:
        raise ValueError("File has no valid data columns.")

    x = np.asarray(df.iloc[:, 0])
    y = np.asarray(df.iloc[:, 1])
    return x, y


# -------------------------------------------------
# Optional: Export detected peaks to CSV
# -------------------------------------------------
def export_peaks_csv(rows, out_path):
    """Save peaks as CSV."""
    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
