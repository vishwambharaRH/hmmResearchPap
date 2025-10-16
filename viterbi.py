import math
import copy
import utils
from emission_probability import compute_emission_probabilities
from transition_probability import compute_transition_probabilities

RADIUS = 20
N = 10
WINDOW = 50  # currently unused; consider using as beam/window size

NEG_INF = float('-inf')

def _to_log_probs(probs):
    """Convert list of probabilities to log-probabilities, safe for zeros."""
    logs = []
    for p in probs:
        if p is None:
            logs.append(NEG_INF)
        else:
            # guard tiny values
            if p <= 0.0:
                logs.append(NEG_INF)
            else:
                logs.append(math.log(p))
    return logs

def viterbi(observations, **kwargs):
    radius = kwargs.get('radius', RADIUS)
    filename = kwargs.get('filename', None)
    window = kwargs.get('window', WINDOW)
    n = kwargs.get('n', N)

    if not observations:
        print("No observations provided to viterbi().")
        return None

    print(f'Running viterbi. Window size: {window}, Max states: {n}, Max radius: {radius}')

    # --- Initialize the first step ---
    print("Processing first observation...")
    segments, emission_probabilities, point = compute_emission_probabilities(observations[0], radius, n)

    if not segments:
        print("ERROR: Could not find any road segments for the starting GPS point. Aborting.")
        return None

    # prepare segments and set previous pointers to None
    for seg in segments:
        seg['previous'] = None
        seg['direction'] = None

    # tables: at index t we store candidate segments and log-probabilities
    segments_table = [segments]
    probabilities_table = [_to_log_probs(emission_probabilities)]

    # Keep track of which original observation indices map to DP entries
    dp_index_to_obs_index = [0]  # dp index 0 corresponds to observations[0]

    # --- Process rest of observations ---
    for t_obs_index, obs in enumerate(observations[1:], start=1):
        print(f"Processing observation {t_obs_index + 1}/{len(observations)}...")

        prev_point = point
        segments, emission_probabilities, point = compute_emission_probabilities(obs, radius, n)

        # if no segments found: try a single retry with larger radius (simple heuristic)
        if not segments:
            print(f"  WARNING: No segments for observation {t_obs_index + 1}. Retrying with larger radius...")
            segments, emission_probabilities, point = compute_emission_probabilities(obs, radius * 2, n)

        if not segments:
            # Mark this observation as skipped: do not append duplicate objects.
            print(f"  WARNING: Still no segments found for observation {t_obs_index + 1}. Skipping this observation.")
            # We do NOT append to segments_table/probabilities_table.
            # Map this observation index to None so we know it's skipped.
            dp_index_to_obs_index.append(None)
            continue

        # compute transition probabilities matrix: shape (len(prev_segments), len(segments))
        transition_probs = compute_transition_probabilities(prev_point, point, segments_table[-1], segments)
        # convert emission and transition to logs
        log_emissions = _to_log_probs(emission_probabilities)

        prev_log_probs = probabilities_table[-1]
        num_prev = len(prev_log_probs)
        num_curr = len(log_emissions)

        # initialize current log-prob list and backpointers
        current_log_probs = [NEG_INF] * num_curr
        current_segments = []

        # For each current candidate i, choose best previous j maximizing prev_log + log(trans[j][i]) + log(emission[i])
        for i in range(num_curr):
            best_log = NEG_INF
            best_prev_idx = None
            for j in range(num_prev):
                trans_p = transition_probs[j][i] if j < len(transition_probs) and i < len(transition_probs[j]) else 0.0
                if trans_p <= 0.0:
                    trans_log = NEG_INF
                else:
                    trans_log = math.log(trans_p)

                if prev_log_probs[j] == NEG_INF or trans_log == NEG_INF or log_emissions[i] == NEG_INF:
                    candidate_log = NEG_INF
                else:
                    candidate_log = prev_log_probs[j] + trans_log + log_emissions[i]

                if candidate_log > best_log:
                    best_log = candidate_log
                    best_prev_idx = j

            # store results for candidate i
            current_log_probs[i] = best_log
            new_segment = copy.deepcopy(segments[i])
            new_segment['previous'] = best_prev_idx
            # compute direction if best_prev_idx exists
            if best_prev_idx is not None:
                new_segment['direction'] = utils.calculate_direction(segments_table[-1][best_prev_idx], new_segment)
            else:
                new_segment['direction'] = None
            current_segments.append(new_segment)

        segments_table.append(current_segments)
        probabilities_table.append(current_log_probs)
        dp_index_to_obs_index.append(t_obs_index)  # DP step corresponds to this observation

    # If no DP steps beyond the first were added (edge case), return the single best start candidate
    if len(probabilities_table) == 0:
        print("No DP states computed. Aborting.")
        return None

    # --- Backtrack: find best final dp index (last non-skipped DP step) ---
    # find last dp index that corresponds to a real DP step (dp_index_to_obs_index not None)
    last_dp = None
    for k in range(len(dp_index_to_obs_index)-1, -1, -1):
        if dp_index_to_obs_index[k] is not None:
            last_dp = k
            break

    if last_dp is None:
        print("ERROR: No valid DP states to backtrack.")
        return None

    # pick best candidate at final DP
    last_probs = probabilities_table[last_dp]
    last_idx, best_val = max(enumerate(last_probs), key=lambda x: x[1])

    # walk back pointers
    final_path = []
    cur_dp = last_dp
    cur_idx = last_idx
    visited = set()
    while cur_idx is not None and cur_dp >= 0:
        # safety: guard indexing errors
        if cur_dp >= len(segments_table):
            break
        segs = segments_table[cur_dp]
        if cur_idx < 0 or cur_idx >= len(segs):
            print("Backtracking index out of range; stopping.")
            break

        segment = segs[cur_idx]
        final_path.append(segment)

        # detect cycles: if (cur_dp, cur_idx) repeats, break
        key = (cur_dp, cur_idx)
        if key in visited:
            print("Detected cycle during backtracking; stopping.")
            break
        visited.add(key)

        # move to previous DP step and index
        prev_idx = segment.get('previous', None)
        cur_idx = prev_idx
        cur_dp -= 1

        # If prev_idx is None, we've reached start — stop.
        if cur_idx is None:
            break

    final_path = final_path[::-1]  # reverse

    node_ids = utils.get_node_ids(final_path)
    if filename is not None:
        print(f"Writing results to {filename}...")
        utils.write_to_file(node_ids, filename)

    return node_ids
