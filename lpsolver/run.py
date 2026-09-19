import argparse
from src.mps_parser import parse_mps
from src.solver import solve

parser = argparse.ArgumentParser(description="Solve a continuous MPS linear program.")
parser.add_argument("model", nargs="?", default="data/sample_small.mps")
parser.add_argument("--backend", choices=("highs", "gpu"), default="highs")
parser.add_argument("--max-iterations", type=int, default=50_000)
args = parser.parse_args()

model = parse_mps(args.model)
if args.backend == "gpu":
    from src.gpu_solver import solve_gpu_pdhg
    result = solve_gpu_pdhg(model, max_iterations=args.max_iterations)
else:
    result = solve(model)

print(f"Model: {model.name} ({model.num_rows} constraints, {model.num_cols} variables)")
print(f"Solver: {result['solver']}")
print(f"Status: {result['status']}")
print(f"Objective: {result['objective']}")
print(f"Solution: {result['x']}")
if "device" in result:
    print(f"Device: {result['device']}")
    print(f"Iterations: {result['iterations']}")
    print(f"Max constraint violation: {result['max_constraint_violation']:.3g}")
