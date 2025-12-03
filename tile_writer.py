# tile_writer.py
import os
import numpy as np
import pandas as pd

def save_tiles(y_data, tile_size=500000, out_dir="tiles"):
    os.makedirs(out_dir, exist_ok=True)
    total = len(y_data)
    for i in range(0, total, tile_size):
        tile = y_data[i:i + tile_size]
        df = pd.DataFrame({'y': tile})
        filename = os.path.join(out_dir, f"tile_{i//tile_size:05d}.csv")
        df.to_csv(filename, index=False)
