# --- Emission Feature Weights ---
# Used to score how well a single road segment matches a single GPS point.
EMISSION_WEIGHTS = {
    # (Feature Name: Weight)
    'distance': 0.60,    # Segment-Location distance is the most critical factor.
    'orientation': 0.35, # The alignment of the road with the vehicle's heading is also very important.
    'speed_limit': 0.05, # The speed limit is a minor factor, mostly useful as a tie-breaker.
}

# --- Transition Feature Weights ---
# Used to score the likelihood of moving from a previous road segment to a new one.
TRANSITION_WEIGHTS = {
    # (Feature Name: Weight)
    'distance_diff': 0.8, # The consistency of travel distance is the best indicator of a valid transition.
    'backtrack': 0.2,     # Preventing backtracking is important but secondary to distance matching.
}
