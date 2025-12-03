#Configuration Parameters
APEX_MIN_SEPARATION = 2 #This is our minimum distance required between distinct maxima so we don't call everything a peak apex
APEX_MIN_HEIGHT = 10 #Minimum y-value required to consider a point a valid peak
ALPHA = 0.5 #if peaks are spiky .4 or peaks rly broad .6
# Configuration Parameters (existing)
APEX_MIN_SEPARATION = 2
APEX_MIN_HEIGHT = 10
ALPHA = 0.5

def radius_rule(width: int) -> int:
    return max(2, round(width/3))

# --- NEW: tiling ---
TILE_SIZE = 500_000  # rows per tile

def radius_rule(width: int) -> int:
    return max(2, round(width/3))