#The GUI. Creates main window, contains controls, embeds PlotWidget and a QTableView for peaks,
#connects signals, handles file dialogs, status msgs, export, and simple validation
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QTableView, QMessageBox, QStatusBar, QLabel,
    QSpinBox, QDoubleSpinBox, QComboBox, QApplication
)
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QCheckBox
import os
from io_utils import save_tiles
from plot_widget import PlotWidget
from io_utils import load_data, export_peaks_csv
import constants as C
from detection_thread_utils import DetectionWorker, get_visible_range, downsample_line


class MainWindow(QMainWindow):

    def on_detection_done(self, result, offset):
        # Apply offset to peak indices
        for row in result["kept_rows"]:
            row["index"] += offset

        self.rows = result["kept_rows"]
        self.islands = result.get("islands", [])
        self.W_by_island = result.get("W_by_island", [])
        self.R_by_island = result.get("R_by_island", [])

        self.plot.set_islands(self.islands)
        self.plot.set_peaks(self.rows)
        self.statusBar().showMessage(f"Detected {len(self.rows)} peaks", 3000)

    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Peak Finder")

        # Persistent attributes
        self.x = None
        self.y = None
        self.rows = []
        self.islands = []
        self.W_by_island = []
        self.R_by_island = []
        self.current_csv_path = None

        # Main layout setup
        central = QWidget(self)
        ly = QVBoxLayout(central)
        central.setLayout(ly)
        self.setCentralWidget(central)

        # Plot widget
        self.plot = PlotWidget(self)
        ly.addWidget(self.plot)

        # Status bar
        self.statusBar().showMessage("Ready")

        # Controls layout
        controls = QHBoxLayout()

        # Buttons
        btn_open = QPushButton("Open File...", self)
        btn_run = QPushButton("Run", self)

        # Detection mode selector
        self.mode_box = QComboBox(self)
        self.mode_box.addItems(["threshold", "wavelet"])
        controls.addWidget(QLabel("Mode:"))
        controls.addWidget(self.mode_box)

        # Full dataset toggle
        self.full_run_box = QCheckBox("Full Dataset")
        self.full_run_box.setChecked(False)
        controls.addWidget(self.full_run_box)


        # Tile Mode Selector
        self.tile_box = QComboBox(self)
        self.tile_box.addItems(["auto", "on", "off"])
        controls.addWidget(QLabel("Tile Mode:"))
        controls.addWidget(self.tile_box)

        # --- Threshold control (re-added) ---
        controls.addWidget(QLabel("Min Height:"))
        self.threshold_box = QDoubleSpinBox(self)
        self.threshold_box.setRange(0, 1e9)
        self.threshold_box.setDecimals(1)
        self.threshold_box.setValue(C.APEX_MIN_HEIGHT)
        controls.addWidget(self.threshold_box)

        # Add buttons to layout
        controls.addWidget(btn_open)
        controls.addWidget(btn_run)

        # Insert control bar above plot
        ly.insertLayout(0, controls)

        # Wire up signals
        btn_open.clicked.connect(self.on_open_file)
        btn_run.clicked.connect(self.on_run)
        self.mode_box.currentTextChanged.connect(self.on_mode_changed)  # enable/disable threshold

        # Async detection thread object
        self.detector = None

        # For downsampled overview mode
        self.overview_enabled = True
        self.overview_threshold = 50_000  # threshold for number of points to trigger overview mode



    # ------------------
    # Open the data file
    # ------------------
    # ------------------
    # Handle mode change (enable/disable threshold control)
    # ------------------
    def on_mode_changed(self, mode):
        if mode == "wavelet":
            self.threshold_box.setEnabled(False)
        else:
            self.threshold_box.setEnabled(True)

    def on_open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            "",
            "Data files (*.csv *.txt *.xls *.xlsx)"
        )
        if not path:
            return

        # Load data based on extension
        x, y = load_data(path)
        self.x, self.y = x, y
        self.current_csv_path = path

        # Clear old results
        self.rows = []
        self.islands = []
        self.W_by_island = []
        self.R_by_island = []

        # If very large, activate tile mode
        if len(y) > 5_000_000:
            tile_dir = os.path.join(os.getcwd(), "tiles")
            save_tiles(y, tile_size=10000, out_dir=tile_dir)
            self.plot.enable_tile_mode(tile_dir)
            self.statusBar().showMessage(f"Loaded {len(y):,} points using tile mode", 3000)
        else:
            self.plot.set_series(x, y)
            self.statusBar().showMessage(f"Loaded {len(x)} points from {path}", 3000)


    # ------------------
    # Run detection
    # ------------------
    def on_run(self):
        if self.x is None:
            QMessageBox.warning(self, "No data", "Load a data file first.")
            return

        mode = self.mode_box.currentText()
        tile_pref = self.tile_box.currentText()

        # Threshold config
        if mode == "threshold":
            C.APEX_MIN_HEIGHT = self.threshold_box.value()

        # Clear previous visuals
        self.plot.set_islands([])
        self.plot.set_peaks([])

        # Check whether to run on full dataset or just visible range
        if self.full_run_box.isChecked():
            y_slice = self.y
            offset = 0
        else:
            start_idx, end_idx = get_visible_range(self.plot.ax, len(self.y))
            y_slice = self.y[start_idx:end_idx]
            offset = start_idx


        if self.full_run_box.isChecked():
            self.statusBar().showMessage(f"Running {mode} detection on full dataset...")
        else:
            self.statusBar().showMessage(
                f"Running {mode} detection on {end_idx - start_idx:,} visible points..."
            )

        QApplication.processEvents()

        # Async detection setup
        self.detector = DetectionWorker(y_data=y_slice, mode=mode)
        self.detector.finished.connect(lambda res: self.on_detection_done(res, offset))
        self.detector.error.connect(lambda e: QMessageBox.critical(self, "Error", str(e)))
        self.detector.start()



if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
