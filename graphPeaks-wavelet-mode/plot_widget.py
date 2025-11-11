from PyQt5.QtWidgets import QWidget, QVBoxLayout
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import numpy as np
import os

class PlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # ---- Layout and Canvas ----
        self.fig = Figure(dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        layout = QVBoxLayout(self)
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        # ---- Default Plot Elements ----
        self.series_line = None
        self.island_patches = []
        self.peak_lines = None
        self.peak_dots = None
        self.peak_labels = []

        self.ax.set_xlabel("Index")
        self.ax.set_ylabel("Value")
        self.ax.grid(True)

        self.canvas.mpl_connect("button_press_event", self.on_canvas_click)
        self.ax.callbacks.connect("xlim_changed", self.on_zoom)

        # Tile settings
        self.tile_mode = False
        self.tile_dir = None
        self.tile_size = 10000

    def enable_tile_mode(self, tile_dir, tile_size=10000):
        self.tile_mode = True
        self.tile_dir = tile_dir
        self.tile_size = tile_size
        self.series_line = None
        self.ax.set_xlim(0, tile_size * 2)
        self.update_visible_tiles()

    def on_zoom(self, ax):
        if self.tile_mode:
            self.update_visible_tiles()

    def update_visible_tiles(self):
        if not self.tile_dir:
            return
        xmin, xmax = map(int, self.ax.get_xlim())
        start = (xmin // self.tile_size) * self.tile_size
        end = ((xmax // self.tile_size) + 1) * self.tile_size

        x_all, y_all = [], []
        for i in range(start, end, self.tile_size):
            path = os.path.join(self.tile_dir, f"tile_{i}.npy")
            if os.path.exists(path):
                y = np.load(path)
                x = np.arange(i, i + len(y))
                x_all.append(x)
                y_all.append(y)

        self.ax.clear()
        if x_all and y_all:
            self.ax.plot(np.concatenate(x_all), np.concatenate(y_all), linewidth=1.0)
        self.ax.set_xlabel("Index")
        self.ax.set_ylabel("Value")
        self.ax.grid(True)
        self.canvas.draw_idle()

    def set_series(self, x, y):
        self.tile_mode = False  # disable tiles for static view
        if len(x) != len(y):
            raise ValueError("x and y must be the same length")
        if self.series_line is None:
            line, = self.ax.plot(x, y, linewidth=1.0)
            self.series_line = line
        else:
            self.series_line.set_data(x, y)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw_idle()

    def set_islands(self, islands):
        for p in self.island_patches:
            p.remove()
        self.island_patches = []
        for start, end in islands:
            patch = self.ax.axvspan(start, end, alpha=0.15)
            self.island_patches.append(patch)
        self.canvas.draw_idle()

    def set_peaks(self, kept_rows):
        if self.peak_lines:
            self.peak_lines.remove()
            self.peak_lines = None
        if self.peak_dots:
            self.peak_dots.remove()
            self.peak_dots = None
        for txt in self.peak_labels:
            txt.remove()
        self.peak_labels = []

        x_idx = [row["index"] for row in kept_rows]
        y_val = [row["value"] for row in kept_rows]

        self.peak_lines = self.ax.vlines(x_idx, 0.0, y_val, linewidths=1.0)
        self.peak_dots = self.ax.scatter(x_idx, y_val, s=20, zorder=3)
        self.canvas.draw_idle()

    def center_on_index(self, idx):
        xmin, xmax = self.ax.get_xlim()
        width = xmax - xmin
        half = max(10, width * 0.1)
        self.ax.set_xlim(idx - half, idx + half)
        self.canvas.draw_idle()

    def on_canvas_click(self, event):
        if event.inaxes != self.ax or self.peak_dots is None:
            return
        x_click, y_click = event.xdata, event.ydata
        if x_click is None or y_click is None:
            return
        offsets = self.peak_dots.get_offsets()
        x_peaks, y_peaks = offsets[:, 0], offsets[:, 1]
        nearest_i = abs(x_peaks - x_click).argmin()
        xi, yi = x_peaks[nearest_i], y_peaks[nearest_i]
        for label in self.peak_labels:
            label.remove()
        self.peak_labels = []
        txt = self.ax.text(xi, yi, f"{int(xi)}, {int(yi)}", fontsize=8, color="red",
                           va="bottom", ha="center",
                           bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.7),
                           zorder=4, clip_on=True)
        self.peak_labels.append(txt)
        self.canvas.draw_idle()
        if event.button == 3:
            for lbl in self.peak_labels:
                lbl.remove()
            self.peak_labels = []
            self.canvas.draw_idle()
