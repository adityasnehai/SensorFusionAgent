# Benchmark Dataset Format

Place scenarios under `benchmarks/datasets/<scenario_name>/`.

Required files per scenario:
- `dataset1.csv`
- `dataset2.csv`

Optional files:
- `dataset3.csv`, `dataset4.csv`
- `metadata.json`

Example `metadata.json`:

```json
{
  "ground_truth_offset_seconds": 0.12,
  "best_alignment_strategy": "classical"
}
```

For multi-dataset offsets, use:

```json
{
  "ground_truth_offsets_seconds": {
    "dataset2": 0.12,
    "dataset3": -0.08
  }
}
```
