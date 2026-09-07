"""Generate feasible random LPs and time the real solver."""
import time
import numpy as np
from scipy.sparse import random as sparse_random
from src.mps_parser import LPModel
from src.solver import solve


def make_random_lp(rows: int, cols: int, seed: int) -> LPModel:
    rng = np.random.default_rng(seed)
    A = sparse_random(rows, cols, density=0.2, format="csr", random_state=seed)
    A.data = rng.uniform(0.5, 5.0, A.nnz)
    upper = rng.uniform(5, 20, cols)
    x0 = rng.uniform(0, upper / 2)
    kinds = ["L"] * rows
    rhs = np.asarray(A @ x0).ravel() + rng.uniform(1, 4, rows)
    return LPModel(f"random_{rows}x{cols}", A, kinds, rhs, rng.uniform(1, 10, cols),
                   [f"x{i}" for i in range(cols)], [f"r{i}" for i in range(rows)],
                   np.zeros(cols), upper)


if __name__ == "__main__":
    for size in (5, 20, 100, 200):
        model = make_random_lp(size, size, size)
        result = solve(model)
        print(f"{size}x{size}: {result['status']}, {result['elapsed_sec'] * 1000:.2f} ms")
