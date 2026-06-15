# Cluster Benchmarking

This folder contains a minimal cluster layer around `run_benchmark.py`.

The core benchmark still lives in `benchmarks/registration/run_benchmark.py`.
The cluster code only splits the run into independent pair jobs and collects the
per-pair JSON files afterward.

## SLURM Array

Submit the script from the repository root. First decide how many pairs to run.
If you want to run `N` pairs, submit an array from `0` to `N - 1`:

```bash
export BENCHMARK_PAIRS=/path/to/pairs.csv
export BENCHMARK_CONFIG=/path/to/dipy/benchmarks/registration/configs/syn_cc_default.yaml
export BENCHMARK_OUT=/path/to/output/run_001
export DOWNSAMPLE_FACTOR=2
export USE_CUDA=1

sbatch --array=0-99 benchmarks/registration/cluster/slurm_pair_job.sh
```

Each array task runs one zero-based pair index from the selected pairs:

```bash
python benchmarks/registration/run_benchmark.py \
  --pairs "$BENCHMARK_PAIRS" \
  --config "$BENCHMARK_CONFIG" \
  --out-dir "$BENCHMARK_OUT" \
  --downsample-factor "$DOWNSAMPLE_FACTOR" \
  --pair-index "$SLURM_ARRAY_TASK_ID"
```

The SLURM array range controls how many pairs are run. For example,
`--array=0-99` runs the first 100 pair indices in the CSV.

Each task writes:

```text
BENCHMARK_OUT/<pair_id>/sample_result.json
```

## Collect Results

After all jobs finish:

```bash
python benchmarks/registration/cluster/collect_results.py \
  --out-dir /path/to/output/run_001
```

This writes:

```text
/path/to/output/run_001/benchmark_results.json
```

## Notes

- Adjust `#SBATCH` memory, time,
  partition, and environment setup for your cluster.
- If your cluster uses PBS/Torque instead of SLURM, keep the same `--pair-index`
  call and replace only the scheduler template.
