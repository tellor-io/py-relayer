from typing import List


def _clean(values: List[float]) -> List[float]:
    cleaned: List[float] = []
    for v in values:
        try:
            f = float(v)
            if f > 0 and f == f:  # positive and not NaN
                cleaned.append(f)
        except Exception:
            continue
    return cleaned


def median(values: List[float]) -> float:
    xs = sorted(_clean(values))
    if not xs:
        raise ValueError("no values")
    n = len(xs)
    mid = n // 2
    if n % 2 == 1:
        return xs[mid]
    return (xs[mid - 1] + xs[mid]) / 2.0


def trimmed_mean(values: List[float], trim: float = 0.1) -> float:
    xs = sorted(_clean(values))
    if not xs:
        raise ValueError("no values")
    if trim <= 0:
        return sum(xs) / float(len(xs))
    trim = min(0.45, max(0.0, trim))
    n = len(xs)
    k = int(n * trim)
    kept = xs[k: n - k] if n - k > k else xs
    if not kept:
        kept = xs
    return sum(kept) / float(len(kept))


