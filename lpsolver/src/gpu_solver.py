"""GPU LP solver using the primal-dual hybrid-gradient (PDHG) method.

This backend is intended for large sparse continuous LPs.  Unlike the CPU
HiGHS path, it is an iterative method, so it reports ``approximate`` rather
than claiming exact optimality.  Matrix-vector products and all iterations
remain on the CUDA device.
"""
from __future__ import annotations

import time
import numpy as np

from .mps_parser import LPModel


def _constraint_bounds(model: LPModel) -> tuple[np.ndarray, np.ndarray]:
    """Convert MPS L/G/E rows to lower <= A x <= upper form."""
    lower = np.full(model.num_rows, -np.inf)
    upper = np.full(model.num_rows, np.inf)
    for i, kind in enumerate(model.row_types):
        if kind == "L":
            upper[i] = model.rhs[i]
        elif kind == "G":
            lower[i] = model.rhs[i]
        elif kind == "E":
            lower[i] = upper[i] = model.rhs[i]
        else:
            raise ValueError(f"Unsupported row type: {kind}")
    return lower, upper


def _spectral_norm(A, cp, iterations: int = 30) -> float:
    """Estimate ||A||_2 with power iteration without transferring A to CPU."""
    if A.shape[1] == 0:
        return 0.0
    v = cp.ones(A.shape[1], dtype=cp.float64)
    v /= cp.linalg.norm(v)
    for _ in range(iterations):
        av = A @ v
        atav = A.T @ av
        norm = cp.linalg.norm(atav)
        if float(norm.get()) == 0.0:
            return 0.0
        v = atav / norm
    return float(cp.linalg.norm(A @ v).get())


def solve_gpu_pdhg(
    model: LPModel,
    max_iterations: int = 50_000,
    tolerance: float = 1e-5,
    check_every: int = 100,
) -> dict:
    """Approximately solve ``min c @ x`` subject to model constraints.

    PDHG alternates sparse ``A @ x`` and ``A.T @ y`` products.  The two
    proximal projections enforce variable bounds and L/G/E constraint bounds.
    It is useful when the sparse model is large enough to amortize GPU setup.
    """
    try:
        import cupy as cp
        import cupyx.scipy.sparse as cpx_sparse
    except ImportError as exc:
        raise RuntimeError(
            "GPU backend requires CuPy. Install with: pip install 'cupy-cuda13x[ctk]'"
        ) from exc

    started = time.perf_counter()
    A = cpx_sparse.csr_matrix(model.A, dtype=cp.float64)
    c = cp.asarray(model.c, dtype=cp.float64)
    x_lower = cp.asarray(model.lower, dtype=cp.float64)
    x_upper = cp.asarray(model.upper, dtype=cp.float64)
    row_lower_cpu, row_upper_cpu = _constraint_bounds(model)
    row_lower = cp.asarray(row_lower_cpu)
    row_upper = cp.asarray(row_upper_cpu)

    norm_a = _spectral_norm(A, cp)
    if norm_a == 0.0:
        raise ValueError("The constraint matrix is empty; use the CPU solver for this model.")
    # tau * sigma * ||A||^2 < 1 is the PDHG stability condition.
    tau = sigma = 0.95 / norm_a
    x = cp.clip(cp.zeros(model.num_cols, dtype=cp.float64), x_lower, x_upper)
    y = cp.zeros(model.num_rows, dtype=cp.float64)
    x_bar = x.copy()
    feasibility = float("inf")
    movement = float("inf")

    for iteration in range(1, max_iterations + 1):
        # prox of the conjugate of the interval indicator, via Moreau's rule.
        y = y + sigma * (A @ x_bar)
        y = y - sigma * cp.clip(y / sigma, row_lower, row_upper)

        x_next = cp.clip(x - tau * (A.T @ y + c), x_lower, x_upper)
        x_bar = 2.0 * x_next - x

        if iteration % check_every == 0 or iteration == max_iterations:
            activity = A @ x_next
            lower_error = cp.maximum(row_lower - activity, 0.0)
            upper_error = cp.maximum(activity - row_upper, 0.0)
            feasibility = float(cp.max(cp.maximum(lower_error, upper_error)).get())
            movement = float((cp.linalg.norm(x_next - x) /
                              max(float(cp.linalg.norm(x).get()), 1.0)).get())
            if feasibility <= tolerance and movement <= tolerance:
                x = x_next
                break
        x = x_next

    cp.cuda.Stream.null.synchronize()
    elapsed = time.perf_counter() - started
    activity = A @ x
    lower_error = cp.maximum(row_lower - activity, 0.0)
    upper_error = cp.maximum(activity - row_upper, 0.0)
    feasibility = float(cp.max(cp.maximum(lower_error, upper_error)).get())
    objective = float(cp.dot(c, x).get())
    return {
        "status": "approximate" if feasibility <= tolerance else "iteration limit reached",
        "objective": objective,
        "x": cp.asnumpy(x),
        "elapsed_sec": elapsed,
        "solver": "CuPy PDHG (GPU)",
        "iterations": iteration,
        "max_constraint_violation": feasibility,
        "relative_step": movement,
        "device": cp.cuda.runtime.getDeviceProperties(0)["name"].decode(),
    }
