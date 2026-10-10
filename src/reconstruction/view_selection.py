"""Choose which k of the n supplied images to use, according to a view arrangement.

Arrangements (Feature 3 of the project spec). Images are assumed to be listed in capture order around the
object (as in the bundled DTU subsets). The overlap-based arrangements use measured pairwise matches, so
they do not rely on that assumption.

- uniform:      evenly spaced through the capture order
- non_uniform:  a contiguous block, i.e. views bunched on one side of the object
- high_overlap: greedy; each new view maximises matches with the views already chosen
- low_overlap:  greedy; each new view minimises matches with the views already chosen
- random:       seeded random subset (reproducible)
- auto:         all images when k == n, otherwise uniform
"""

from typing import Dict, List, Sequence

import numpy as np

ARRANGEMENTS = ("auto", "uniform", "non_uniform", "high_overlap", "low_overlap", "random")


def _match_matrix(names: Sequence[str], pairs: Sequence[Dict]) -> np.ndarray:
    idx = {n: i for i, n in enumerate(names)}
    m = np.zeros((len(names), len(names)), dtype=np.float64)
    for p in pairs:
        a, b = idx.get(p["a"]), idx.get(p["b"])
        if a is not None and b is not None:
            m[a, b] = m[b, a] = p["matches"]
    return m


def select_views(names: Sequence[str], k: int, arrangement: str,
                 pairs: Sequence[Dict] = (), seed: int = 0) -> List[str]:
    """Return k image names (in capture order) chosen by `arrangement`."""
    n = len(names)
    k = max(1, min(k, n))
    if arrangement not in ARRANGEMENTS:
        raise ValueError(f"Unknown view arrangement '{arrangement}'. Allowed: {ARRANGEMENTS}")
    if k == n:
        return list(names)

    if arrangement in ("auto", "uniform"):
        chosen = sorted(set(int(round(x)) for x in np.linspace(0, n - 1, k)))
        # linspace + rounding can collide for small n; top up deterministically
        for i in range(n):
            if len(chosen) >= k:
                break
            if i not in chosen:
                chosen.append(i)
        chosen = sorted(chosen)[:k]
    elif arrangement == "non_uniform":
        chosen = list(range(k))
    elif arrangement == "random":
        rng = np.random.default_rng(seed)
        chosen = sorted(rng.choice(n, size=k, replace=False).tolist())
    else:
        m = _match_matrix(names, pairs)
        high = arrangement == "high_overlap"
        totals = m.sum(axis=1)
        first = int(np.argmax(totals) if high else np.argmin(totals))
        chosen = [first]
        while len(chosen) < k:
            rest = [i for i in range(n) if i not in chosen]
            score = [m[i, chosen].sum() for i in rest]
            chosen.append(rest[int(np.argmax(score) if high else np.argmin(score))])
        chosen = sorted(chosen)
    return [names[i] for i in chosen]
