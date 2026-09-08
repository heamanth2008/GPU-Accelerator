# Working CPU LP Solver

This project loads continuous linear programs from free-format MPS files and solves them with the production HiGHS solver through SciPy.

## Setup and run (Windows)

```powershell
py -3 -m pip install -r requirements.txt
py -3 run.py
```

Expected result for the included sample: an optimal objective of `3.0` with a feasible solution equivalent to `[0, 0, 3]`.

To solve another MPS file:

```powershell
py -3 -m src.solver path\\to\\model.mps
```

For a small timing run on randomly generated feasible models:

```powershell
py -3 benchmark.py
```

## GPU backend

The optional GPU backend uses CuPy and the iterative PDHG algorithm. It is
intended for large, sparse continuous LPs; the default HiGHS backend is faster
and more accurate for small models.

```powershell
py -3 -m pip install -r requirements-gpu.txt
py -3 run.py --backend gpu
```

The GPU result is labelled `approximate` and includes its maximum constraint
violation. Check it against the CPU result when accuracy is important.

## Browser interface

Start the local interface:

```powershell
py -3 app.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). Choose an `.mps`
file, select the CPU or GPU backend, and click **Solve model**. The server
does not retain uploaded files.

## Deploy on Render

Create a Render **Web Service** from this repository and set:

```text
Root Directory: lpsolver
Build Command: pip install -r requirements.txt
Start Command: python app.py
```

Render supplies the required `PORT` environment variable automatically. Its
standard service has no NVIDIA GPU, so choose **CPU HiGHS** in the deployed app.

The reader supports continuous LP ROWS, COLUMNS, RHS, and BOUNDS records. Integer MPS markers and RANGES are intentionally not supported.
