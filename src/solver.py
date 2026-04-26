import re
import sys
import math
import json
import argparse
import multiprocessing
from pathlib import Path

# ---------------------------------------------------------------------------
# Load animals
# ---------------------------------------------------------------------------

def load_animals():
    src = Path(__file__).parent.parent / 'animals.js'
    text = src.read_text(encoding='utf-8')
    animals = []
    for m in re.finditer(r'\{([^}]+)\}', text):
        block = '{' + m.group(1) + '}'
        block = re.sub(r'(\w+):', r'"\1":', block)
        try:
            a = json.loads(block)
            if 'id' in a and 'name' in a:
                animals.append(a)
        except json.JSONDecodeError:
            pass
    return animals

# ---------------------------------------------------------------------------
# Feedback simulation (mirrors compareNum / compareArr in index.html)
# ---------------------------------------------------------------------------

def compare_num(g, t):
    if g == t:   return 'exact'
    if g < t:    return 'low'    # need to guess higher
    return               'high'  # need to guess lower

def compare_arr(g, t):
    t_set = set(t)
    overlap = [x for x in g if x in t_set]
    if len(overlap) == len(t) and len(g) == len(t):
        return 'exact'
    if overlap:
        return 'partial'
    return 'none'

def get_feedback(guess, target):
    return (
        compare_num(guess['cost'],         target['cost']),
        compare_num(guess['size'],         target['size']),
        compare_arr(guess['tags'],         target['tags']),
        compare_arr(guess['continents'],   target['continents']),
        compare_num(guess['appeal'],       target['appeal']),
        compare_num(guess['conservation'], target['conservation']),
    )

# ---------------------------------------------------------------------------
# Candidate filtering
# ---------------------------------------------------------------------------

def is_consistent(candidate, guess, feedback):
    cost_fb, size_fb, tags_fb, conts_fb, appeal_fb, cons_fb = feedback

    def num_ok(cval, gval, fb):
        if fb == 'exact':   return cval == gval
        if fb == 'low':     return cval > gval
        return                     cval < gval

    def arr_ok(cval, gval, fb):
        g_set = set(gval)
        overlap = [x for x in cval if x in g_set]
        exact = len(overlap) == len(gval) and len(cval) == len(gval)
        if fb == 'exact':   return exact
        if fb == 'partial': return bool(overlap) and not exact
        return                     not overlap

    return (
        num_ok(candidate['cost'],         guess['cost'],         cost_fb) and
        num_ok(candidate['size'],         guess['size'],         size_fb) and
        arr_ok(candidate['tags'],         guess['tags'],         tags_fb) and
        arr_ok(candidate['continents'],   guess['continents'],   conts_fb) and
        num_ok(candidate['appeal'],       guess['appeal'],       appeal_fb) and
        num_ok(candidate['conservation'], guess['conservation'], cons_fb)
    )

def filter_candidates(candidates, guess, feedback):
    return [c for c in candidates if is_consistent(c, guess, feedback)]

# ---------------------------------------------------------------------------
# Scoring functions — both normalised to "lower is better"
# ---------------------------------------------------------------------------

def score_candidates(guess, candidates):
    """Expected remaining candidates. Lower = better."""
    buckets = {}
    for c in candidates:
        fb = get_feedback(guess, c)
        buckets[fb] = buckets.get(fb, 0) + 1
    n = len(candidates)
    return sum(count * count for count in buckets.values()) / n

def score_entropy(guess, candidates):
    """Negative entropy. Lower = better (i.e. higher entropy = more informative)."""
    buckets = {}
    for c in candidates:
        fb = get_feedback(guess, c)
        buckets[fb] = buckets.get(fb, 0) + 1
    n = len(candidates)
    return sum((count / n) * math.log2(count / n) for count in buckets.values())

SCORE_FNS = {
    'candidates': score_candidates,
    'entropy':    score_entropy,
}

# ---------------------------------------------------------------------------
# Guess selection with memoization
# ---------------------------------------------------------------------------

_best_guess_cache = {}

def best_guess(candidates, all_animals, score_fn):
    if len(candidates) <= 2:
        return candidates[0]
    key = (frozenset(c['id'] for c in candidates), score_fn)
    if key in _best_guess_cache:
        return _best_guess_cache[key]
    best, best_score = None, float('inf')
    for g in all_animals:
        s = score_fn(g, candidates)
        if s < best_score:
            best_score, best = s, g
    _best_guess_cache[key] = best
    return best

# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

def format_feedback(guess, feedback):
    labels = ('cost', 'size', 'tags', 'conts', 'appeal', 'cons')
    values = (guess['cost'], guess['size'], guess['tags'],
              guess['continents'], guess['appeal'], guess['conservation'])
    symbols = {'exact': '=', 'low': '^', 'high': 'v', 'partial': '~', 'none': 'x'}
    parts = []
    for label, val, fb in zip(labels, values, feedback):
        display = ','.join(val) if isinstance(val, list) else str(val)
        parts.append(f'{label}:{display}{symbols[fb]}')
    return '  '.join(parts)

def solve(target, all_animals, score_fn, verbose=False):
    candidates = list(all_animals)
    guesses = []
    for attempt in range(1, 9):
        guess = best_guess(candidates, all_animals, score_fn)
        feedback = get_feedback(guess, target)
        guesses.append(guess['name'])
        if verbose:
            candidates = filter_candidates(candidates, guess, feedback)
            if guess['name'] == target['name']:
                print(f"Guess {attempt}: {guess['name']:<30} SOLVED in {attempt} guess{'es' if attempt > 1 else ''}!")
            else:
                print(f"Guess {attempt}: {guess['name']:<30}    {format_feedback(guess, feedback)}  ({len(candidates)} remain)")
        else:
            if guess['name'] == target['name']:
                return attempt, guesses
            candidates = filter_candidates(candidates, guess, feedback)
        if guess['name'] == target['name']:
            return attempt, guesses
    return None, guesses

# ---------------------------------------------------------------------------
# Multiprocessing worker (module-level for picklability on Windows)
# ---------------------------------------------------------------------------

_worker_animals = None
_worker_algorithm = None

def _worker_init(animals, algorithm):
    global _worker_animals, _worker_algorithm
    _worker_animals = animals
    _worker_algorithm = algorithm

def _solve_worker(target_id):
    target = next(a for a in _worker_animals if a['id'] == target_id)
    n, _ = solve(target, _worker_animals, SCORE_FNS[_worker_algorithm])
    return target_id, n

# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_solve(name, all_animals, score_fn):
    matches = [a for a in all_animals if a['name'].lower() == name.lower()]
    if not matches:
        close = [a for a in all_animals if name.lower() in a['name'].lower()]
        if close:
            print(f"Animal '{name}' not found. Did you mean: {', '.join(a['name'] for a in close[:5])}?")
        else:
            print(f"Animal '{name}' not found.")
        sys.exit(1)
    target = matches[0]
    print(f"Target: {target['name']}\n")
    solve(target, all_animals, score_fn, verbose=True)

def cmd_benchmark(all_animals, algorithm):
    print(f"Benchmarking {len(all_animals)} animals (algorithm={algorithm})...\n")
    ids = [a['id'] for a in all_animals]
    with multiprocessing.Pool(
        initializer=_worker_init,
        initargs=(all_animals, algorithm),
    ) as pool:
        results = pool.map(_solve_worker, ids)

    id_to_name = {a['id']: a['name'] for a in all_animals}
    counts, total, failed = {}, 0, []
    for target_id, n in results:
        if n is None:
            failed.append(id_to_name[target_id])
        else:
            counts[n] = counts.get(n, 0) + 1
            total += n

    for name in failed:
        print(f"  FAILED: {name}")

    solved = sum(counts.values())
    avg = total / solved if solved else 0
    worst_n = max(counts.keys())
    worst_list = [id_to_name[tid] for tid, n in results if n == worst_n]
    print(f"Solved {solved}/{len(all_animals)} animals")
    print(f"Average guesses: {avg:.2f}")
    print(f"Worst case: {worst_n} ({', '.join(worst_list)})")
    print(f"Distribution: {'  '.join(f'{k}:{counts.get(k,0)}' for k in sorted(counts))}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Arkle puzzle solver')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--solve', metavar='NAME', help='show optimal solution for one animal')
    group.add_argument('--benchmark', action='store_true', help='solve all animals and print stats (default)')
    parser.add_argument('--algorithm', choices=['candidates', 'entropy'], default='candidates',
                        help='scoring strategy: candidates (default) or entropy')
    args = parser.parse_args()

    all_animals = load_animals()
    if not all_animals:
        print("Failed to load animals — check animals.js exists in the repo root.")
        sys.exit(1)

    if args.solve:
        cmd_solve(args.solve, all_animals, SCORE_FNS[args.algorithm])
    else:
        cmd_benchmark(all_animals, args.algorithm)

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
