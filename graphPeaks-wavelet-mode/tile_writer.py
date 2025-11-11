# tile_writer.py
import numpy as np
import os

def save_tiles(y_data, tile_size=10000, out_dir="tiles"):
    os.makedirs(out_dir, exist_ok=True)
    n = len(y_data)
    for i in range(0, n, tile_size):
        chunk = y_data[i:i + tile_size]
        np.save(os.path.join(out_dir, f"tile_{i}.npy"), chunk)
