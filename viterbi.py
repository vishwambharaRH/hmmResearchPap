import utils
from emission_probability import compute_emission_probabilities
from transition_probability import compute_transition_probabilities

RADIUS = 20
N = 10
WINDOW = 50

# Viterbi algorithm
# kwargs: filename to write in, radius to look segments from, n max number of states considered at time t
# window size
def viterbi(observations, **kwargs):
    radius = kwargs.get('radius', RADIUS)
    filename = kwargs.get('filename', None)
    window = kwargs.get('window', WINDOW)
    n = kwargs.get('n', N)

    print(f'Running viterbi. Window size: {window}, Max states: {n}, Max radius: {radius}')

    result_sequence = []
    
    # --- Initialize the first step ---
    print("Processing first observation...")
    segments, emission_probabilities, point = compute_emission_probabilities(observations[0], radius, n)
    
    # --- CRITICAL CHECK ---
    # If the very first point can't be matched, we can't proceed.
    if not segments:
        print("ERROR: Could not find any road segments for the starting GPS point. Aborting.")
        print("This likely means the GPS data is not in the area covered by your map file.")
        return None

    for i, segment in enumerate(segments):
        segments[i]['previous'] = None
        segments[i]['direction'] = None
    
    segments_table = [segments]
    probabilities_table = [emission_probabilities]
    
    # --- Process the rest of the observations ---
    for t, obs in enumerate(observations[1:], 1):
        print(f"Processing observation {t + 1}/{len(observations)}...")
        
        previous_point = point
        segments, emission_probabilities, point = compute_emission_probabilities(obs, radius, n)

        # --- CRITICAL CHECK ---
        # If no segments are found for the current point, skip it and issue a warning.
        if not segments:
            print(f"  WARNING: No road segments found for observation {t + 1}. Skipping this point.")
            # We can't calculate a path for this step, so we might need a more complex
            # strategy here in the future, but for now, we'll just hold the previous state.
            segments_table.append(segments_table[t-1])
            probabilities_table.append(probabilities_table[t-1])
            continue

        transition_probabilities = compute_transition_probabilities(previous_point,
                                                                  point,
                                                                  segments_table[t-1],
                                                                  segments)
        
        current_segments = []
        current_probabilities = []
        for i, emission_probability in enumerate(emission_probabilities):
            candidates = []
            for j, previous_probability in enumerate(probabilities_table[t-1]):
                prob = previous_probability * transition_probabilities[j][i] * emission_probability
                candidates.append(prob)
            
            idx, highest_probability = max(enumerate(candidates), key=lambda x: x[1])
            current_probabilities.append(highest_probability)
            
            new_segment = segments[i].copy()
            new_segment['previous'] = idx
            new_segment['direction'] = utils.calculate_direction(segments_table[t-1][idx], new_segment)
            current_segments.append(new_segment)

        segments_table.append(current_segments)
        probabilities_table.append(current_probabilities)

    # --- Backtrack to find the most likely path ---
    print("All observations processed. Finding the most likely path...")
    
    final_path = []
    # Find the best segment at the very end of the path
    last_idx, _ = max(enumerate(probabilities_table[-1]), key=lambda x: x[1])

    # Trace backwards from the end to the beginning
    for t in range(len(observations) - 1, -1, -1):
        segment = segments_table[t][last_idx]
        final_path.append(segment)
        last_idx = segment['previous']

    result_sequence = final_path[::-1] # Reverse the path to get it in the correct order

    # --- Write output to file ---
    node_ids = utils.get_node_ids(result_sequence)
    if filename is not None:
        print(f"Writing results to {filename}...")
        utils.write_to_file(node_ids, filename)
    
    return node_ids

def run_viterbi(observations_filename, **kwargs):
    observations = []
    print(f"Reading observations from {observations_filename}...")
    with open(observations_filename) as f:
        # Skip header
        next(f, None)
        for line in f:
            parts = line.strip().split(',')
            # Ensure we have enough parts to unpack
            if len(parts) >= 8:
                observations.append((float(parts[3]), float(parts[4]), float(parts[7]), float(parts[6])))
    
    start = kwargs.pop('start', 0)
    end = kwargs.pop('end', len(observations))
    
    print(f"Found {len(observations)} total observations. Processing from {start} to {end}.")
    return viterbi(observations[start:end], **kwargs)

if __name__ == '__main__':
    # --- IMPORTANT ---
    # Make sure this input file corresponds to the map you are using.
    # Since we have a SoCal map, we should use a SoCal GPS track.
    # For now, we'll use the existing file for debugging.
    input_file = 'gps_data/AroundPA.csv'
    output_file = 'matched_files/AroundPA_matched.csv'
    
    print(f"Starting map matching for {input_file}...")
    run_viterbi(input_file, filename=output_file)
    print("--- Matching process complete. ---")

