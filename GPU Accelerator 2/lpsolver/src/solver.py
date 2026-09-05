"""Reliable LP solution path powered by SciPy's HiGHS backend."""
import time
import numpy as np
from scipy.optimize import linprog
from .mps_parser import LPModel


def solve(model: LPModel) -> dict:
    """Minimize c @ x subject to model constraints and variable bounds."""
    A_ub, b_ub, A_eq, b_eq = [], [], [], []
    dense = model.A.toarray()
    for i, kind in enumerate(model.row_types):
        if kind == "L": A_ub.append(dense[i]); b_ub.append(model.rhs[i])
        elif kind == "G": A_ub.append(-dense[i]); b_ub.append(-model.rhs[i])
        elif kind == "E": A_eq.append(dense[i]); b_eq.append(model.rhs[i])
    bounds = list(zip(np.where(np.isfinite(model.lower), model.lower, None),
                     np.where(np.isfinite(model.upper), model.upper, None)))
    started = time.perf_counter()
    result = linprog(model.c, A_ub=A_ub or None, b_ub=b_ub or None,
                     A_eq=A_eq or None, b_eq=b_eq or None, bounds=bounds, method="highs")
    return {"status": "optimal" if result.success else result.message,
            "objective": float(result.fun) if result.success else None,
            "x": result.x if result.success else None,
            "elapsed_sec": time.perf_counter() - started, "solver": "HiGHS"}


if __name__ == "__main__":
    import sys
    from .mps_parser import parse_mps
    result = solve(parse_mps(sys.argv[1]))
    print(f"{result['solver']}: {result['status']}; objective={result['objective']}; x={result['x']}")
