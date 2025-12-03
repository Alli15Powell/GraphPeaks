# detection_threads_utils.py
# ------------------------------------------------------------
# Helper utilities for GraphPeaks:
#   - DetectionWorker: run detection in a background thread
#   - get_visible_range: map current x-limits to index range
#   - downsample_line: optional downsampling for huge plots
# ------------------------------------------------------------

from PyQt5.QtCore import QThread, pyqtSignal
import numpy as np

from detect import run_pipeline


class DetectionWorker(QThread):
    """
    QThread wrapper around run_pipeline() so the GUI doesn't freeze
    on large datasets. Emits:
        - finished(result_dict)
        - error(exception)
    """
    finished = pyqtSignal(dict)
    error = pyqtSignal(Exception)

    def __init__(self, y_data, mode="threshold", extra_kwargs=None, parent=None):
        super().__init__(parent)
        self.y_data = y_data
        self.mode = mode
        self.extra_kwargs = extra_kwargs or {}

    def run(self):
        try:
            result = run_pipeline(self.y_data, mode=self.mode, **self.extra_kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(e)


def get_visible_range(ax, total_len):
    """
    Given a Matplotlib Axes and total data length, return the integer
    index range (start, end) corresponding to the current x-limits.

    If anything goes wrong, fall back to the full range (0, total_len).
    """
    try:
        xmin, xmax = ax.get_xlim()
        xmin = max(0, int(xmin))
        xmax = min(total_len, int(xmax))
        if xmax <= xmin:
            xmax = min(total_len, xmin + 1)
        return xmin, xmax
    except Exception:
        return (0, total_len)


def downsample_line(x, y, max_points=50_000):
    """
    Optional utility: downsample (x, y) to at most ~2*max_points using
    min/max pooling per bucket. Preserves overall shape while reducing
    plot load for massive datasets.
    """
    x = np.asarray(x)
    y = np.asarray(y)
    n = len(x)

    if max_points <= 0 or n <= max_points:
        return x, y

    bucket_size = int(np.ceil(n / max_points))
    xs = []
    ys = []

    for i in range(0, n, bucket_size):
        xb = x[i:i + bucket_size]
        yb = y[i:i + bucket_size]
        if xb.size == 0:
            continue

        # min point
        idx_min = int(np.argmin(yb))
        xs.append(xb[idx_min])
        ys.append(yb[idx_min])

        # max point
        idx_max = int(np.argmax(yb))
        xs.append(xb[idx_max])
        ys.append(yb[idx_max])

    return np.array(xs), np.array(ys)
