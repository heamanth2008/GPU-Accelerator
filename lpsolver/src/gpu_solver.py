"""GPU LP solver using the primal-dual hybrid-gradient (PDHG) method.

This backend is designed for large sparse continuous LPs.
When CuPy and NVIDIA CUDA are available, all sparse matrix-vector products and
proximal steps execute directly on the GPU VRAM.
If CuPy is blocked by Windows Smart App Control or unavailable, it seamlessly
executes the exact same PDHG algorithm via NumPy/SciPy sparse routines, streaming
live iteration counts, convergence progress, and feasibility metrics without crashing.
"""
from __future__ import annotations

import time
import numpy as np
from scipy import sparse as sp_sparse
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


def _spectral_norm(A, xp, iterations: int = 30) -> float:
    """Estimate ||A||_2 with power iteration."""
    if A.shape[1] == 0:
        return 0.0
    v = xp.ones(A.shape[1], dtype=np.float64 if xp is np else xp.float64)
    v /= float(xp.linalg.norm(v))
    for _ in range(iterations):
        av = A @ v
        atav = A.T @ av
        norm = float(xp.linalg.norm(atav))
        if norm == 0.0:
            return 0.0
        v = atav / norm
    return float(xp.linalg.norm(A @ v))


def solve_gpu_pdhg(
    model: LPModel,
    max_iterations: int = 50_000,
    tolerance: float = 1e-5,
    check_every: int = 100,
    progress_callback=None,
) -> dict:
    """Solve linear program using Primal-Dual Hybrid Gradient (PDHG)."""
    has_cupy = False
    device_name = "CPU (PDHG Algorithm)"
    try:
        import cupy as cp
        import cupyx.scipy.sparse as cpx_sparse
        if cp.cuda.runtime.getDeviceCount() > 0:
            has_cupy = True
            raw_name = cp.cuda.runtime.getDeviceProperties(0)["name"]
            device_name = raw_name.decode() if isinstance(raw_name, bytes) else str(raw_name)
    except Exception:
        has_cupy = False

    started = time.perf_counter()

    row_lower_cpu, row_upper_cpu = _constraint_bounds(model)

    if has_cupy:
        A = cpx_sparse.csr_matrix(model.A, dtype=cp.float64)
        c = cp.asarray(model.c, dtype=cp.float64)
        x_lower = cp.asarray(model.lower, dtype=cp.float64)
        x_upper = cp.asarray(model.upper, dtype=cp.float64)
        row_lower = cp.asarray(row_lower_cpu)
        row_upper = cp.asarray(row_upper_cpu)
        xp = cp
    else:
        A = model.A.tocsr().astype(np.float64)
        c = np.asarray(model.c, dtype=np.float64)
        x_lower = np.asarray(model.lower, dtype=np.float64)
        x_upper = np.asarray(model.upper, dtype=np.float64)
        row_lower = row_lower_cpu
        row_upper = row_upper_cpu
        xp = np

    norm_a = _spectral_norm(A, xp)
    if norm_a == 0.0:
        raise ValueError("The constraint matrix is empty; please check the model.")

    tau = sigma = 0.95 / norm_a
    x = xp.clip(xp.zeros(model.num_cols, dtype=np.float64), x_lower, x_upper)
    y = xp.zeros(model.num_rows, dtype=np.float64)
    x_bar = x.copy()
    feasibility = float("inf")
    movement = float("inf")

    for iteration in range(1, max_iterations + 1):
        # Prox of conjugate via Moreau's rule
        y = y + sigma * (A @ x_bar)
        y = y - sigma * xp.clip(y / sigma, row_lower, row_upper)

        x_next = xp.clip(x - tau * (A.T @ y + c), x_lower, x_upper)
        x_bar = 2.0 * x_next - x

        if iteration % check_every == 0 or iteration == max_iterations:
            activity = A @ x_next
            lower_error = xp.maximum(row_lower - activity, 0.0)
            upper_error = xp.maximum(activity - row_upper, 0.0)
            feasibility = float(xp.max(xp.maximum(lower_error, upper_error)))
            norm_x = float(xp.linalg.norm(x))
            movement = float(xp.linalg.norm(x_next - x) / max(norm_x, 1.0))
            objective_now = float(xp.dot(c, x_next))

            if progress_callback is not None:
                try:
                    progress_callback(iteration, objective_now, feasibility)
                except Exception:
                    pass

            if feasibility <= tolerance and movement <= tolerance:
                x = x_next
                break
        x = x_next

    if has_cupy:
        cp.cuda.Stream.null.synchronize()

    elapsed = time.perf_counter() - started

    # Final metrics
    activity = A @ x
    lower_error = xp.maximum(row_lower - activity, 0.0)
    upper_error = xp.maximum(activity - row_upper, 0.0)
    feasibility = float(xp.max(xp.maximum(lower_error, upper_error)))
    objective = float(xp.dot(c, x))

    # Calculate dual / reduced costs: r = c - A.T @ y
    reduced_costs_arr = c - (A.T @ y)
    slack_arr = row_upper - activity

    if has_cupy:
        x_final = cp.asnumpy(x).tolist()
        rc_final = cp.asnumpy(reduced_costs_arr).tolist()
        slack_final = cp.asnumpy(slack_arr).tolist()
    else:
        x_final = x.tolist()
        rc_final = reduced_costs_arr.tolist()
        slack_final = slack_arr.tolist()

    solver_label = f"CuPy PDHG ({device_name})" if has_cupy else "PDHG (First-Order Hybrid)"

    return {
        "status": "approximate" if feasibility <= tolerance else "iteration limit reached",
        "objective": objective,
        "x": x_final,
        "slack": slack_final,
        "reduced_costs": rc_final,
        "elapsed_sec": elapsed,
        "solver": solver_label,
        "iterations": iteration,
        "max_constraint_violation": feasibility,
        "relative_step": movement,
        "device": device_name,
        "gpu_accelerated": has_cupy,
    }
