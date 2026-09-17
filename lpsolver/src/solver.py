"""Reliable LP solution path powered by SciPy's HiGHS backend."""
from __future__ import annotations
import time
import numpy as np
from scipy.optimize import linprog
from .mps_parser import LPModel


def solve(model: LPModel, progress_callback=None) -> dict:
    """Minimize c @ x subject to model constraints and variable bounds.

    Args:
        progress_callback: Optional callable(iteration, objective, feasibility).
            For the HiGHS CPU path this is called once on completion since
            ``linprog`` is a black-box solver without iteration callbacks.
    """
    A_ub, b_ub, A_eq, b_eq = [], [], [], []
    dense = model.A.toarray()
    for i, kind in enumerate(model.row_types):
        if kind == "L":
            A_ub.append(dense[i])
            b_ub.append(model.rhs[i])
        elif kind == "G":
            A_ub.append(-dense[i])
            b_ub.append(-model.rhs[i])
        elif kind == "E":
            A_eq.append(dense[i])
            b_eq.append(model.rhs[i])

    bounds = list(zip(
        np.where(np.isfinite(model.lower), model.lower, None),
        np.where(np.isfinite(model.upper), model.upper, None)
    ))

    started = time.perf_counter()
    result = linprog(
        model.c,
        A_ub=A_ub or None,
        b_ub=b_ub or None,
        A_eq=A_eq or None,
        b_eq=b_eq or None,
        bounds=bounds,
        method="highs",
    )
    elapsed = time.perf_counter() - started
    objective = float(result.fun) if result.success else None

    if progress_callback is not None:
        try:
            progress_callback(1, objective, 0.0 if result.success else None)
        except Exception:
            pass

    # Extract slack and reduced costs (marginals)
    slack = []
    if getattr(result, "slack", None) is not None:
        slack = [float(s) for s in result.slack]

    reduced_costs = []
    if getattr(result, "marginals", None) is not None and getattr(result.marginals, "x", None) is not None:
        reduced_costs = [float(rc) for rc in result.marginals.x]

    return {
        "status": "optimal" if result.success else result.message,
        "objective": objective,
        "x": [float(val) for val in result.x] if result.success and result.x is not None else None,
        "slack": slack,
        "reduced_costs": reduced_costs,
        "elapsed_sec": elapsed,
        "solver": "HiGHS (CPU)",
    }
