# ------------------------------------------------------------
# Qt table model for peaks
# ------------------------------------------------------------
# Displays:
#   - Tile index
#   - Apex index / value
#   - Span start/end
#   - Width
#   - Island/region id
#   - W_region
#   - R_region
# ------------------------------------------------------------

from PyQt5.QtCore import QAbstractTableModel, Qt, QVariant


class PeaksTableModel(QAbstractTableModel):
    def __init__(self, peaks=None, parent=None):
        super().__init__(parent)
        self._peaks = peaks or []

        # UPDATED HEADERS — now includes W_region and R_region
        self._headers = [
            "Tile",
            "Apex Index",
            "Apex Value",
            "Span Start",
            "Span End",
            "Width",
            "Island ID",
            "W_region",
            "R_region",
        ]

    # --------------------------------------------------------
    # Basic model API
    # --------------------------------------------------------
    def rowCount(self, parent=None):
        return len(self._peaks)

    def columnCount(self, parent=None):
        return len(self._headers)

    # --------------------------------------------------------
    # Data for each cell
    # --------------------------------------------------------
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role not in (Qt.DisplayRole, Qt.EditRole):
            return QVariant()

        row = index.row()
        col = index.column()
        if row < 0 or row >= len(self._peaks):
            return QVariant()

        peak = self._peaks[row]

        # Safely extract values from the dict
        span_start, span_end = peak.get("span_idx", (None, None))

        # Calculate width if missing
        width = peak.get("width_idx")
        if width is None and span_start is not None and span_end is not None:
            width = span_end - span_start + 1

        apex_index = peak.get("index")  # 0-based internally
        apex_value = peak.get("value")

        island_id = peak.get("region_id", peak.get("island_id", None))

        tile = peak.get("tile", None)

        # NEW FIELDS
        W_region = peak.get("W_region", None)
        R_region = peak.get("R_region", None)

        # ----- Column Mapping -----
        if col == 0:   # Tile
            return "" if tile is None else str(tile)

        elif col == 1:  # Apex index
            return "" if apex_index is None else str(apex_index + 1)

        elif col == 2:  # Apex value
            return "" if apex_value is None else str(apex_value)

        elif col == 3:  # Span start
            return "" if span_start is None else str(span_start + 1)

        elif col == 4:  # Span end
            return "" if span_end is None else str(span_end + 1)

        elif col == 5:  # Width
            return "" if width is None else str(width)

        elif col == 6:  # Island ID
            return "" if island_id is None else str(island_id)

        elif col == 7:  # NEW: W_region
            return "" if W_region is None else str(W_region)

        elif col == 8:  # NEW: R_region
            return "" if R_region is None else str(R_region)

        return QVariant()

    # --------------------------------------------------------
    # Headers
    # --------------------------------------------------------
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return QVariant()

        if orientation == Qt.Horizontal:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        else:
            # 1-based row numbering
            return str(section + 1)

        return QVariant()

    # --------------------------------------------------------
    # Replace peak list
    # --------------------------------------------------------
    def setPeaks(self, peaks):
        self.beginResetModel()
        self._peaks = peaks or []
        self.endResetModel()
