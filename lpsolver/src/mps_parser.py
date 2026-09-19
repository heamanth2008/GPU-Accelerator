"""Small, dependency-light free-format MPS reader for continuous LPs."""
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix


@dataclass
class LPModel:
    name: str
    A: csr_matrix
    row_types: list[str]
    rhs: np.ndarray
    c: np.ndarray
    col_names: list[str]
    row_names: list[str]
    lower: np.ndarray
    upper: np.ndarray

    @property
    def num_rows(self): return self.A.shape[0]
    @property
    def num_cols(self): return self.A.shape[1]
    @property
    def nnz(self): return self.A.nnz


def parse_mps(filepath: str | Path) -> LPModel:
    """Parse ROWS, COLUMNS, RHS and BOUNDS from a free-format MPS file."""
    section, name, objective = None, "UNNAMED", None
    rows, types, cols, col_index = [], {}, [], {}
    entries, costs, rhs_values, lower_values, upper_values = [], {}, {}, {}, {}
    for raw in Path(filepath).read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("*"): continue
        tokens, leading = raw.split(), raw[:1].isspace()
        if not tokens: continue
        key = tokens[0].upper()
        if not leading and key == "NAME":
            name = tokens[1] if len(tokens) > 1 else name; continue
        if not leading and key in {"ROWS", "COLUMNS", "RHS", "BOUNDS", "RANGES"}:
            section = key; continue
        if not leading and key == "ENDATA": break
        if section == "ROWS":
            typ, row = tokens[0].upper(), tokens[1]
            if typ == "N" and objective is None: objective = row
            elif typ in {"L", "G", "E"}: rows.append(row); types[row] = typ
        elif section == "COLUMNS":
            if "MARKER" in raw.upper(): continue
            col = tokens[0]
            if col not in col_index: col_index[col] = len(cols); cols.append(col)
            for row, value in zip(tokens[1::2], tokens[2::2]):
                value = float(value)
                if row == objective: costs[col] = costs.get(col, 0.0) + value
                else: entries.append((row, col, value))
        elif section == "RHS":
            for row, value in zip(tokens[1::2], tokens[2::2]): rhs_values[row] = float(value)
        elif section == "BOUNDS":
            if len(tokens) < 3: continue
            kind, col = tokens[0].upper(), tokens[2]
            value = float(tokens[3]) if len(tokens) > 3 else None
            if kind == "LO": lower_values[col] = value
            elif kind == "UP": upper_values[col] = value
            elif kind == "FX": lower_values[col] = upper_values[col] = value
            elif kind == "FR": lower_values[col], upper_values[col] = -np.inf, np.inf
            elif kind == "MI": lower_values[col] = -np.inf
            elif kind == "PL": upper_values[col] = np.inf
    row_index = {r: i for i, r in enumerate(rows)}
    ri, ci, values = [], [], []
    for row, col, value in entries:
        if row in row_index:
            ri.append(row_index[row]); ci.append(col_index[col]); values.append(value)
    A = csr_matrix((values, (ri, ci)), shape=(len(rows), len(cols)))
    c = np.array([costs.get(col, 0.0) for col in cols])
    rhs = np.array([rhs_values.get(row, 0.0) for row in rows])
    lower = np.array([lower_values.get(col, 0.0) for col in cols])
    upper = np.array([upper_values.get(col, np.inf) for col in cols])
    return LPModel(name, A, [types[r] for r in rows], rhs, c, cols, rows, lower, upper)


if __name__ == "__main__":
    import sys
    m = parse_mps(sys.argv[1])
    print(f"Parsed {m.name}: {m.num_rows} rows, {m.num_cols} columns, {m.nnz} nonzeros")
