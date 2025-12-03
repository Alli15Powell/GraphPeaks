# ------------------------------------------------------------
# Main Window for GraphPeaks / Peak Finder GUI
# ------------------------------------------------------------
# Responsibilities:
#  - Load CSV/TXT files
#  - Control peak detection pipeline (threaded)
#  - Display plot (with tile mode for large datasets)
#  - Display peaks in a table
#  - Jump to peak when user clicks a row
#  - Export peaks to CSV (including tile_index)
#  - Auto full vs visible-region detection
#  - Wavelet summary + heatmap visualization
# ------------------------------------------------------------

import os
import csv
import math

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTableView, QMessageBox,
    QLabel, QSpinBox, QComboBox, QApplication,
    QCheckBox, QSlider
)
from PyQt5.QtCore import Qt
from detection_threads_utils import DetectionWorker, get_visible_range
from plot_widget import PlotWidget
from io_utils import load_csv
from detect import run_pipeline
from models import PeaksTableModel
import constants as C


class MainWindow(QMainWindow):

    # --------------------------------------------------------
    # Called when threaded detection completes
    # --------------------------------------------------------
    def on_detection_done(self, result, offset):
        """
        `offset` is the starting index of the analyzed slice
        from visible-region detection. We restore global indices.
        """
        for row in result["kept_rows"]:
            row["index"] += offset

        # Save peak results
        self.rows = result["kept_rows"]
        self.islands = result.get("islands", [])
        self.W_by_island = result.get("W_by_island", [])
        self.R_by_island = result.get("R_by_island", [])

        # ---- Wavelet visualization support ----
        wavelet_summary = result.get("wavelet_summary")
        cwt_matrix = result.get("cwt_matrix")
        widths = result.get("widths")

        self.plot.set_wavelet_data(
            summary=wavelet_summary,
            cwt_matrix=cwt_matrix,
            widths=widths
        )

        # Assign tile index
        self._assign_tile_indices()

        # Update table
        self.update_table()

        # Draw peaks
        if hasattr(self.plot, "set_keptPeaks"):
            self.plot.set_keptPeaks(self.rows)
        self.plot.set_peaks(self.rows)

        self.detector = None
        self.statusBar().showMessage(f"Detected {len(self.rows)} peaks", 3000)



    # --------------------------------------------------------
    # Constructor
    # --------------------------------------------------------
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Peak Finder")

        # Data state
        self.x = None
        self.y = None
        self.rows = []
        self.islands = []
        self.W_by_island = []
        self.R_by_island = []
        self.current_csv_path = None

        # Tile state
        self.tile_mode = False
        self.tile_size = C.TILE_SIZE
        self.num_tiles = 1
        self.current_tile = 1
        self.x_full = None
        self.y_full = None

        # ------------------------
        # Layout
        # ------------------------
        central = QWidget(self)
        main_layout = QVBoxLayout(central)
        self.setCentralWidget(central)

        # ------------------------
        # Controls
        # ------------------------
        controls = QHBoxLayout()

        btn_open = QPushButton("Open CSV/TXT...", self)
        btn_run = QPushButton("Run", self)
        btn_export = QPushButton("Export Peaks", self)

        self.mode_box = QComboBox(self)
        self.mode_box.addItems(["threshold", "wavelet"])
        controls.addWidget(QLabel("Mode:"))
        controls.addWidget(self.mode_box)

        self.full_run_box = QCheckBox("Full Dataset")
        controls.addWidget(self.full_run_box)

        self.tile_box = QComboBox(self)
        self.tile_box.addItems(["auto", "on", "off"])
        controls.addWidget(QLabel("Tile Mode:"))
        controls.addWidget(self.tile_box)

        # Marker threshold
        self.maxMarkerSpin = QSpinBox(self)
        self.maxMarkerSpin.setRange(0, 1_000_000_000)
        self.maxMarkerSpin.setValue(0)
        self.maxMarkerSpin.setPrefix("Show ≥ ")
        self.maxMarkerSpin.setSuffix(" counts")
        controls.addWidget(self.maxMarkerSpin)

        # Layer toggles (raw / wavelet summary / CWT heatmap)
        self.toggle_raw = QCheckBox("Raw")
        self.toggle_raw.setChecked(True)
        self.toggle_raw.stateChanged.connect(
            lambda s: self.plot.toggle_raw(s == Qt.Checked)
        )
        controls.addWidget(self.toggle_raw)

        self.toggle_summary = QCheckBox("Wavelet Curve")
        self.toggle_summary.setChecked(False)
        self.toggle_summary.stateChanged.connect(
            lambda s: self.plot.toggle_wavelet_summary(s == Qt.Checked)
        )
        controls.addWidget(self.toggle_summary)

        self.toggle_heatmap = QCheckBox("CWT Heatmap")
        self.toggle_heatmap.setChecked(False)
        self.toggle_heatmap.stateChanged.connect(
            lambda s: self.plot.toggle_cwt_heatmap(s == Qt.Checked)
        )
        controls.addWidget(self.toggle_heatmap)

        # Buttons
        controls.addWidget(btn_open)
        controls.addWidget(btn_run)
        controls.addWidget(btn_export)

        # Tile slider/spin
        self.tile_slider = QSlider(Qt.Horizontal, self)
        self.tile_spin = QSpinBox(self)
        self.tile_slider.setMinimum(1)
        self.tile_spin.setMinimum(1)
        self.tile_slider.setEnabled(False)
        self.tile_spin.setEnabled(False)
        controls.addWidget(QLabel("Tile:"))
        controls.addWidget(self.tile_slider, 1)
        controls.addWidget(self.tile_spin)

        main_layout.addLayout(controls)

        # ------------------------
        # Plot widget
        # ------------------------
        self.plot = PlotWidget(self)
        main_layout.addWidget(self.plot)

        # ------------------------
        # Table
        # ------------------------
        self.table = QTableView(self)
        self.table_model = PeaksTableModel([])
        self.table.setModel(self.table_model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        main_layout.addWidget(self.table)

        self.table.clicked.connect(self.on_table_clicked)

        self.statusBar().showMessage("Ready")

        # Connect events
        btn_open.clicked.connect(self.on_open_csv)
        btn_run.clicked.connect(self.on_run)
        btn_export.clicked.connect(self.on_export)

        self.mode_box.currentTextChanged.connect(self.on_mode_changed)
        self.tile_slider.valueChanged.connect(self.on_tile_slider_changed)
        self.tile_spin.valueChanged.connect(self.on_tile_spin_changed)

        self.detector = None



    # ------------------------------------------------------------
    # Tile Mode
    # ------------------------------------------------------------
    def configure_tiles(self):
        if self.y is None:
            return

        n = len(self.y)
        self.x_full = self.x
        self.y_full = self.y

        # No tiling needed
        if n <= self.tile_size or self.tile_box.currentText() == "off":
            self.tile_mode = False
            self.num_tiles = 1
            self.current_tile = 1

            self.tile_slider.setEnabled(False)
            self.tile_spin.setEnabled(False)
            self.plot.set_series(self.x_full, self.y_full)
            return

        # Enable tiling
        self.tile_mode = True
        self.num_tiles = math.ceil(n / self.tile_size)
        self.current_tile = 1

        self.tile_slider.setEnabled(True)
        self.tile_spin.setEnabled(True)
        self.tile_slider.setMaximum(self.num_tiles)
        self.tile_spin.setMaximum(self.num_tiles)

        self.tile_slider.blockSignals(True)
        self.tile_spin.blockSignals(True)
        self.tile_slider.setValue(1)
        self.tile_spin.setValue(1)
        self.tile_slider.blockSignals(False)
        self.tile_spin.blockSignals(False)

        self.update_tile_plot()
        self.statusBar().showMessage(
            f"Tile mode: {self.num_tiles} tiles of {self.tile_size:,} pts"
        )



    # ------------------------------------------------------------
    # Draw tile
    # ------------------------------------------------------------
    def update_tile_plot(self):
        if not self.tile_mode or self.x_full is None:
            if self.x is not None:
                self.plot.set_series(self.x, self.y)
                if self.rows:
                    self.plot.set_keptPeaks(self.rows)
                    self.plot.set_peaks(self.rows)
            return

        tile_idx = self.current_tile - 1
        start = tile_idx * self.tile_size
        end = min(len(self.y_full), start + self.tile_size)

        self.plot.set_series(self.x_full, self.y_full)
        self.plot.set_view_window(start, end)

        if self.rows:
            self.plot.set_keptPeaks(self.rows)
            self.plot.set_peaks(self.rows)



    # ------------------------------------------------------------
    # Tile slider/spin
    # ------------------------------------------------------------
    def on_tile_slider_changed(self, value):
        if value != self.current_tile:
            self.current_tile = value
            self.tile_spin.blockSignals(True)
            self.tile_spin.setValue(value)
            self.tile_spin.blockSignals(False)
            self.update_tile_plot()

    def on_tile_spin_changed(self, value):
        if value != self.current_tile:
            self.current_tile = value
            self.tile_slider.blockSignals(True)
            self.tile_slider.setValue(value)
            self.tile_slider.blockSignals(False)
            self.update_tile_plot()



    # ------------------------------------------------------------
    # Mode changed
    # ------------------------------------------------------------
    def on_mode_changed(self, mode):
        self.statusBar().showMessage(f"Mode: {mode}", 1500)



    # ------------------------------------------------------------
    # Assign tile indices
    # ------------------------------------------------------------
    def _assign_tile_indices(self):
        if not self.rows:
            return
        for row in self.rows:
            idx = row["index"]
            row["tile"] = (idx // self.tile_size) + 1



    # ------------------------------------------------------------
    # Update table
    # ------------------------------------------------------------
    def update_table(self):
        self.table_model.setPeaks(self.rows)
        self.table.resizeColumnsToContents()



    # ------------------------------------------------------------
    # Click → jump to peak AND center on it
    # ------------------------------------------------------------
    def on_table_clicked(self, index):
        r = index.row()
        if r < 0:
            return

        peak = self.rows[r]
        apex_idx = peak["index"]

        # Determine tile
        tile_idx0 = apex_idx // self.tile_size
        self.current_tile = tile_idx0 + 1

        # Sync slider + spin
        self.tile_slider.blockSignals(True)
        self.tile_spin.blockSignals(True)
        self.tile_slider.setValue(self.current_tile)
        self.tile_spin.setValue(self.current_tile)
        self.tile_slider.blockSignals(False)
        self.tile_spin.blockSignals(False)

        # Draw tile
        self.update_tile_plot()

        # ---- NEW FEATURE: center plot on selected peak ----
        if hasattr(self.plot, "center_on_index"):
            self.plot.center_on_index(apex_idx)



    # ------------------------------------------------------------
    # Export visible peaks
    # ------------------------------------------------------------
    def on_export(self):
        if not self.rows:
            QMessageBox.warning(self, "Nothing to export", "Run detection first")
            return

        visible = self.plot.getShownPeaks()
        if not visible:
            QMessageBox.warning(self, "Nothing to export", "No peaks pass threshold")
            return

        base = os.path.splitext(os.path.basename(self.current_csv_path))[0]
        marker_min = self.plot.marker_min_height
        suggested = f"{base}_peaks_min{marker_min}.csv"
        path = os.path.join(os.path.dirname(self.current_csv_path), suggested)

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Export Peaks", path,
            "CSV Files (*.csv);;All Files (*)"
        )
        if not save_path:
            return

        with open(save_path, "w", newline="", encoding="utf-8") as f:
            W = csv.writer(f)
            W.writerow([
                "span_start", "span_end", "width",
                "apex_index", "apex_value",
                "island_id", "tile_index"
            ])

            for row in visible:
                s, e = row["span_idx"]
                W.writerow([
                    s + 1, e + 1,
                    row["width_idx"],
                    row["index"] + 1,
                    row["value"],
                    row.get("region_id"),
                    row.get("tile")
                ])

        self.statusBar().showMessage(f"Exported {len(visible)} peaks", 3000)



    # ------------------------------------------------------------
    # Load CSV
    # ------------------------------------------------------------
    def on_open_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open CSV",
            "", "Data files (*.csv *.txt);;All Files (*)"
        )
        if not path:
            return

        x, y = load_csv(path)
        self.x = x
        self.y = y
        self.current_csv_path = path

        # Reset state
        self.rows = []
        self.plot.set_keptPeaks([])
        self.plot.set_peaks([])
        self.plot.set_wavelet_data(None, None, None)

        self.configure_tiles()
        self.update_table()

        self.statusBar().showMessage(f"Loaded {len(x):,} points", 3000)



    # ------------------------------------------------------------
    # Run detection
    # ------------------------------------------------------------
    def on_run(self):
        if self.x is None:
            QMessageBox.warning(self, "No data", "Load a CSV first")
            return

        mode = self.mode_box.currentText()

        if mode == "threshold":
            C.APEX_MIN_HEIGHT = self.maxMarkerSpin.value()

        total_len = len(self.y)

        # Auto-scope
        start_idx, end_idx = get_visible_range(self.plot.ax, total_len)
        window_len = end_idx - start_idx

        if self.full_run_box.isChecked() or window_len >= 0.9 * total_len:
            y_slice = self.y
            offset = 0
            desc = f"full dataset ({total_len:,} pts)"
        else:
            y_slice = self.y[start_idx:end_idx]
            offset = start_idx
            desc = (
                f"visible region {start_idx:,}–{end_idx - 1:,} "
                f"({window_len:,} pts)"
            )

        self.statusBar().showMessage(f"Processing {desc} using {mode}...")
        QApplication.processEvents()

        # Start worker
        self.detector = DetectionWorker(y_data=y_slice, mode=mode)
        self.detector.finished.connect(lambda res, off=offset: self.on_detection_done(res, off))
        self.detector.error.connect(lambda e: QMessageBox.critical(self, "Detection error", str(e)))
        self.detector.start()



# ------------------------------------------------------------
# Run standalone
# ------------------------------------------------------------
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
