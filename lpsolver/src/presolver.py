"""Ruiz row/column equilibration for conditioning an LP matrix."""
import numpy as np
from scipy.sparse import diags


def ruiz_scaling(A, b, c, iterations=5):
    A = A.tocsr().astype(float); rs = np.ones(A.shape[0]); cs = np.ones(A.shape[1])
    for _ in range(iterations):
        row_max = np.maximum(np.asarray(abs(A).max(axis=1).toarray()).ravel(), 1.0)
        step = 1 / np.sqrt(row_max); rs *= step; A = diags(step) @ A
        col_max = np.maximum(np.asarray(abs(A).max(axis=0).toarray()).ravel(), 1.0)
        step = 1 / np.sqrt(col_max); cs *= step; A = (A @ diags(step)).tocsr()
    return A, rs * b, cs * c, rs, cs
