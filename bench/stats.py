"""Medians and the success band. No model is the judge."""

from __future__ import annotations


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (float(ordered[mid - 1]) + float(ordered[mid])) / 2.0


def success_rate(records: list[dict], *, holdout: bool) -> float:
    chosen = [record for record in records if bool(record["holdout"]) is holdout]
    if not chosen:
        return 0.0
    return sum(1 for record in records if bool(record["holdout"]) is holdout and record["success"]) / len(chosen)


def within_success_band(baseline: float, candidate: float) -> bool:
    return abs(candidate - baseline) <= 0.01 + 1e-9
