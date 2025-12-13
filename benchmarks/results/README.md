# Benchmark Results

This directory contains benchmark results for the NL2SQL system.

## Files

- `benchmark_YYYYMMDD_HHMMSS.json` - Detailed benchmark results with timestamp

## Viewing Results

Results are in JSON format with the following structure:

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "total_tests": 50,
  "passed_tests": 45,
  "failed_tests": 5,
  "overall_accuracy": 90.0,
  "valid_sql_rate": 95.0,
  "avg_latency_ms": 150,
  "p50_latency_ms": 120,
  "p95_latency_ms": 350,
  "p99_latency_ms": 500,
  "cache_hit_rate": 25.0,
  "categories": { ... },
  "detailed_results": [ ... ]
}
```

## Quick Analysis

Use Python to analyze results:

```python
import json

with open("benchmark_20240115_103000.json") as f:
    data = json.load(f)

print(f"Accuracy: {data['overall_accuracy']}%")
print(f"P95 Latency: {data['p95_latency_ms']}ms")
```
