# graphPeaks
Notes from meeting:
The intention is to graph the file produced from the alignment program. We take a list of values
and, state significant peaks. 
There are reads that a noisy at the cutoffs which we can view visually but need to program this find.
The local environemnt matters since some read files have peaks in the thousand counts but others have peaks
in the 100s. Analyzing the file before finding peaks is essential to figure out the threshold.
Additionally, ensure splitpin peaks are two seperate peaks not just one peak. 

Logic as of 11/1/2025
Identify signal peaks from numeric data series such as read counts or intensities. 
1. Find "islands" of activity where read counts are above apex_min_height. Each island is a pair of indices [start, end]
2. Detect local maxima per island. Within each island we examine every index and compare its value to left and right neighbors (edges treated as -inf)
   For flat tops we collapse the plateau into one candidate at its center. Then record each candidate peak as (index, value)
3. Measyre Peak Widths. For each candidate, we compute threshold = ALPHA * value. Step left and right from the peak while the data stays >= threshold
   The total number of points spanned gives the width and the median width across all peaks in the island defines the island's representative width
4. Compute Supression Radius via converting each width w into a suppression radius which defines how close two peaks can be before one is supressed
5. Combine all islands' candidate peaks into a single global list of [index, value, region_id] where region_id identifies the island of origin
6. NMS sorts candidates by descending value and for each candidate we look up its radius from its island and discard it if another stronger kept peak
   from the same island is within R. The remaining peaks are the final detected apices
...


Update (11/2025): Added Wavelet Detection Mode

A new wavelet-based detection mode has been added to make peak detection more adaptive across different datasets.

How it works:

Uses the Continuous Wavelet Transform (CWT) via scipy.signal.find_peaks_cwt.

Automatically identifies peaks of varying widths and shapes without a fixed height threshold.

More robust to noise and signal scale changes (e.g., datasets with counts in 100s vs 1000s).

How to use it:

Open the program (app.py or python app.py).

Load a CSV or text file containing numeric data.

In the control bar, choose the detection Mode: “wavelet” from the dropdown.

Click Run — detected peaks will be plotted with the same visualization features.

Switch back to threshold mode to compare results.

Notes:

Wavelet mode doesn’t use island segmentation — it detects peaks directly from signal shape.

You can toggle between modes without reloading data.

The threshold mode remains the default.


Updates (November 2025)
Performance and Usability Improvements

Visible Region–Only Detection
Users can now run peak detection on just the visible portion of the graph. This significantly improves responsiveness when working with large datasets.

Full Dataset Toggle
A new checkbox allows you to choose between analyzing the entire dataset or only the currently zoomed-in view.

Tile Mode for Large Files
Files exceeding 5 million points automatically trigger a tile-based loading mode to prevent memory overload and UI freezing.

Threaded Detection
Peak detection now runs on a background thread, keeping the interface responsive during computation.

Adjustable Threshold Control
When using threshold mode, a numeric input allows for manual tuning of the peak height threshold before analysis.
