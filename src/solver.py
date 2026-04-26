import re
import sys
import json
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
        # quote unquoted keys (all string values already use double quotes in the JS)
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
# Guess selection — greedy entropy (minimise expected remaining candidates)
# ---------------------------------------------------------------------------

def score_guess(guess, candidates):
    buckets = {}
    for c in candidates:
        fb = get_feedback(guess, c)
        buckets[fb] = buckets.get(fb, 0) + 1
    n = len(candidates)
    return sum(count * count for count in buckets.values()) / n

def best_guess(candidates, all_animals):
    if len(candidates) <= 2:
        return candidates[0]
    best, best_score = None, float('inf')
    for g in all_animals:
        s = score_guess(g, candidates)
        if s < best_score:
            best_score, best = s, g
    return best

# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

FIELD_LABELS = ('cost', 'size', 'tags', 'conts', 'appeal', 'cons')

def format_feedback(guess, feedback):
    parts = []
    labels = ('cost', 'size', 'tags', 'conts', 'appeal', 'cons')
    values = (guess['cost'], guess['size'], guess['tags'],
              guess['continents'], guess['appeal'], guess['conservation'])
    symbols = {'exact': '=', 'low': '^', 'high': 'v',
               'partial': '~', 'none': 'x'}
    for label, val, fb in zip(labels, values, feedback):
        if isinstance(val, list):
            display = ','.join(val) if val else '—'
        else:
            display = str(val)
        parts.append(f'{label}:{display}{symbols[fb]}')
    return '  '.join(parts)

def solve(target, all_animals, verbose=False):
    candidates = list(all_animals)
    guesses = []
    for attempt in range(1, 9):
        guess = best_guess(candidates, all_animals)
        feedback = get_feedback(guess, target)
        guesses.append(guess['name'])
        if verbose:
            remaining_before = len(candidates)
            candidates = filter_candidates(candidates, guess, feedback)
            if guess['name'] == target['name']:
                print(f"Guess {attempt}: {guess['name']:<30} SOLVED in {attempt} guess{'es' if attempt > 1 else ''}!")
            else:
                fb_str = format_feedback(guess, feedback)
                print(f"Guess {attempt}: {guess['name']:<30}    {fb_str}  ({len(candidates)} remain)")
        else:
            if guess['name'] == target['name']:
                return attempt, guesses
            candidates = filter_candidates(candidates, guess, feedback)
        if guess['name'] == target['name']:
            return attempt, guesses
    return None, guesses  # failed (shouldn't happen with 8 guesses)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_solve(name, all_animals):
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
    solve(target, all_animals, verbose=True)

def cmd_benchmark(all_animals):
    print(f"Benchmarking {len(all_animals)} animals...\n")
    counts = {}
    worst_animals = []
    total = 0
    for target in all_animals:
        n, _ = solve(target, all_animals, verbose=False)
        if n is None:
            print(f"  FAILED: {target['name']}")
            continue
        counts[n] = counts.get(n, 0) + 1
        total += n
        worst = max(counts.keys())
        if n == worst:
            worst_animals = [a['name'] for a in all_animals
                             if solve(a, all_animals)[0] == worst]

    solved = sum(counts.values())
    avg = total / solved if solved else 0
    worst_n = max(counts.keys())
    # re-collect worst-case animals cleanly
    worst_list = []
    for target in all_animals:
        n, _ = solve(target, all_animals, verbose=False)
        if n == worst_n:
            worst_list.append(target['name'])

    print(f"Solved {solved}/{len(all_animals)} animals")
    print(f"Average guesses: {avg:.2f}")
    print(f"Worst case: {worst_n} ({', '.join(worst_list)})")
    dist = '  '.join(f"{k}:{counts.get(k,0)}" for k in sorted(counts))
    print(f"Distribution: {dist}")

def main():
    all_animals = load_animals()
    if not all_animals:
        print("Failed to load animals — check animals.js exists in the repo root.")
        sys.exit(1)

    if len(sys.argv) >= 3 and sys.argv[1] == '--solve':
        cmd_solve(' '.join(sys.argv[2:]), all_animals)
    elif len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] == '--benchmark'):
        cmd_benchmark(all_animals)
    else:
        print("Usage:")
        print("  python solver.py                    # benchmark all animals")
        print("  python solver.py --solve <name>     # solve one animal")

if __name__ == '__main__':
    main()
