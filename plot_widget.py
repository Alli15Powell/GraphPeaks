# ------------------------------------------------------------
# PlotWidget: matplotlib plot embedded in PyQt5
# ------------------------------------------------------------
# Handles:
#   - Drawing coverage data (raw)
#   - Drawing wavelet-summary curve
#   - Drawing CWT heatmap (optional)
#   - Drawing peaks
#   - Tile-mode (via x-limits)
#   - Marker filtering
#   - Zoom (NavigationToolbar)
#   - Center-on-peak
#   - Dynamic downsampling for huge views
# ------------------------------------------------------------

import numpy as np
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
from matplotlib import gridspec


class PlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.max_points_per_view = 200_000

        # --------------------------------------------------------
        # Figure structure: raw+summary on top, CWT heatmap below
        # --------------------------------------------------------
        self.fig = Figure(figsize=(7, 5), dpi=100)
        gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1])
        self.ax = self.fig.add_subplot(gs[0])
        self.ax_cwt = self.fig.add_subplot(gs[1])

        self.canvas = FigureCanvas(self.fig)

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)

        # Toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)

        # Data
        self._x_full = None
        self._y_full = None

        # Peaks
        self.keptPeaks = []
        self.markers = []
        self.marker_min_height = 0

        # Wavelet visuals
        self.wavelet_summary = None
        self.cwt_matrix = None
        self.cwt_widths = None

        # Layer toggles
        self.show_raw = True
        self.show_wavelet_summary = False
        self.show_cwt_heatmap = False

        self.ax.set_title("Coverage Plot")
        self.ax.set_ylabel("Counts")
        self.ax_cwt.set_ylabel("Wavelet Width")
        self.ax_cwt.set_xlabel("Position")

    # --------------------------------------------------------
    # Visible index range helper
    # --------------------------------------------------------
    def _get_visible_indices(self, xlim=None):
        if self._x_full is None:
            return 0, 0

        n = len(self._x_full)
        if xlim is None:
            xmin, xmax = self.ax.get_xlim()
        else:
            xmin, xmax = xlim

        start = max(0, int(np.floor(xmin)))
        end = min(n, int(np.ceil(xmax)))
        if end <= start:
            end = min(n, start + 1)

        return start, end

    # --------------------------------------------------------
    # Wavelet data setter
    # --------------------------------------------------------
    def set_wavelet_data(self, summary=None, cwt_matrix=None, widths=None):
        self.wavelet_summary = summary
        self.cwt_matrix = cwt_matrix
        self.cwt_widths = widths
        self.redraw()

    # --------------------------------------------------------
    # Layer toggles
    # --------------------------------------------------------
    def toggle_raw(self, checked: bool):
        self.show_raw = checked
        self.redraw()

    def toggle_wavelet_summary(self, checked: bool):
        self.show_wavelet_summary = checked
        self.redraw()

    def toggle_cwt_heatmap(self, checked: bool):
        self.show_cwt_heatmap = checked
        self.redraw()

    # --------------------------------------------------------
    # Load full series
    # --------------------------------------------------------
    def set_series(self, x, y):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)

        if x.shape != y.shape:
            raise ValueError("x and y must have the same length")

        self._x_full = x
        self._y_full = y
        n = len(x)

        self.redraw(xlim_override=(0, max(1, n)))

    # --------------------------------------------------------
    # Tile index window
    # --------------------------------------------------------
    def set_view_window(self, start_idx, end_idx):
        if self._x_full is None:
            return

        n = len(self._x_full)
        start_idx = max(0, int(start_idx))
        end_idx = min(n, int(end_idx))

        if end_idx <= start_idx:
            end_idx = start_idx + 1

        self.redraw(xlim_override=(start_idx, end_idx))

    # --------------------------------------------------------
    # Center on peak
    # --------------------------------------------------------
    def center_on_index(self, idx, window_size=None):
        if self._x_full is None:
            return

        n = len(self._x_full)
        idx = max(0, min(n - 1, int(idx)))

        if window_size is None:
            try:
                xmin, xmax = self.ax.get_xlim()
                current_width = int(xmax - xmin)
            except:
                current_width = n
            window_size = max(50, current_width // 2)

        half = window_size // 2
        left = max(0, idx - half)
        right = min(n, idx + half)
        if right <= left:
            right = left + 1

        self.redraw(xlim_override=(left, right))

    # --------------------------------------------------------
    # Master redraw
    # --------------------------------------------------------
    def redraw(self, xlim_override=None):
        if self._x_full is None:
            return

        n = len(self._x_full)

        # Determine x-limits
        if xlim_override is not None:
            xmin, xmax = xlim_override
        else:
            try:
                xmin, xmax = self.ax.get_xlim()
            except:
                xmin, xmax = (0, n)

        xmin = max(0, xmin)
        xmax = min(n, xmax)
        if xmax <= xmin:
            xmax = xmin + 1

        # Visible index slice
        start, end = self._get_visible_indices((xmin, xmax))
        span = end - start

        # Dynamic downsampling
        step = 1
        if span > self.max_points_per_view:
            step = int(np.ceil(span / self.max_points_per_view))

        x_view = self._x_full[start:end:step]
        y_view = self._y_full[start:end:step]

        # Clear axes
        self.ax.clear()
        self.ax_cwt.clear()

        # -------------------
        # 1. Raw signal
        # -------------------
        if self.show_raw:
            self.ax.plot(
                x_view, y_view,
                color="black",
                linewidth=1.0,
                label="Raw Signal"
            )

        # -------------------
        # 2. Wavelet summary
        # -------------------
        if self.show_wavelet_summary and self.wavelet_summary is not None:
            ws = self.wavelet_summary[start:end:step]

            if len(ws) == len(x_view):
                if self.show_raw:
                    raw_seg = self._y_full[start:end]
                    raw_max = np.max(raw_seg) if np.max(raw_seg) != 0 else 1.0
                    ws_scale = np.max(ws) if np.max(ws) != 0 else 1.0
                    ws = ws * (raw_max / ws_scale)

                self.ax.plot(
                    x_view, ws,
                    linestyle="--",
                    color="blue",
                    linewidth=1.0,
                    label="Wavelet Summary"
                )

        # -------------------
        # 3. Peaks
        # -------------------
        self.set_peaks(
            self.keptPeaks,
            direct_call=True,
            visible_range=(start, end)
        )

        # -------------------
        # 4. CWT heatmap
        # -------------------
        if self.show_cwt_heatmap and self.cwt_matrix is not None:
            matrix_slice = self.cwt_matrix[:, start:end:step]

            if matrix_slice.shape[1] == len(x_view):
                self.ax_cwt.imshow(
                    matrix_slice,
                    aspect="auto",
                    origin="lower",
                    cmap="inferno",
                    extent=[
                        x_view[0], x_view[-1],
                        self.cwt_widths[0], self.cwt_widths[-1]
                    ],
                )
                self.ax_cwt.set_ylabel("Width")
                self.ax_cwt.set_xlabel("Position")
                self.ax_cwt.set_visible(True)

        else:
            self.ax_cwt.set_visible(False)

        # Legend
        try:
            self.ax.legend(loc="upper right", fontsize=8)
        except:
            pass

        self.ax.set_xlim(xmin, xmax)
        self.canvas.draw_idle()

    # --------------------------------------------------------
    # Peaks
    # --------------------------------------------------------
    def set_keptPeaks(self, kept):
        self.keptPeaks = kept or []

    def set_peaks(self, peaks, direct_call=False, visible_range=None):
        for m in self.markers:
            m.remove()
        self.markers = []

        if peaks is None or self._x_full is None:
            if not direct_call:
                self.canvas.draw_idle()
            return

        start, end = visible_range or self._get_visible_indices()

        for row in peaks:
            if row["value"] < self.marker_min_height:
                continue

            idx = row["index"]
            if idx < start or idx >= end:
                continue

            x = self._x_full[idx]
            y = self._y_full[idx]

            m = self.ax.plot(
                x, y,
                marker="o",
                markersize=6,
                color="red",
            )[0]
            self.markers.append(m)

        if not direct_call:
            self.canvas.draw_idle()

    # --------------------------------------------------------
    # Export helper
    # --------------------------------------------------------
    def getShownPeaks(self):
        return [
            r for r in self.keptPeaks
            if r["value"] >= self.marker_min_height
        ]

    # --------------------------------------------------------
    # Marker threshold
    # --------------------------------------------------------
    def set_marker_min_height(self, v):
        self.marker_min_height = v
        self.set_peaks(self.keptPeaks)
