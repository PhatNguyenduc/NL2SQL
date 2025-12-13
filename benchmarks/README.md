# NL2SQL Benchmarks

Comprehensive benchmark suite for evaluating NL2SQL system performance.

## Quick Start

```bash
# Run all benchmarks
python benchmark_runner.py --all

# Run accuracy tests only
python benchmark_runner.py --accuracy

# Run performance/load test
python benchmark_runner.py --performance --requests 100 --concurrency 10

# Run specific category
python benchmark_runner.py --category join

# Export results
python benchmark_runner.py --all --export results/my_benchmark.json
```

## Metrics Measured

### Accuracy Metrics

| Metric                      | Description                              |
| --------------------------- | ---------------------------------------- |
| **Execution Accuracy (EX)** | SQL executes and returns correct results |
| **Valid SQL Rate**          | Percentage of syntactically valid SQL    |
| **Table Detection**         | Correctly identified tables              |
| **Validation Pass Rate**    | Passed custom validation rules           |

### Performance Metrics

| Metric          | Description                    |
| --------------- | ------------------------------ |
| **Avg Latency** | Average response time          |
| **P50 Latency** | 50th percentile response time  |
| **P95 Latency** | 95th percentile response time  |
| **P99 Latency** | 99th percentile response time  |
| **Throughput**  | Requests per second under load |

### Cache Metrics

| Metric                  | Description                             |
| ----------------------- | --------------------------------------- |
| **Cache Hit Rate**      | Percentage of queries served from cache |
| **Semantic Cache Hits** | Similar queries matched via embeddings  |

## Test Categories

| Category         | Weight | Description                 |
| ---------------- | ------ | --------------------------- |
| `simple_lookup`  | 1.0x   | Basic SELECT queries        |
| `aggregation`    | 1.2x   | COUNT, SUM, AVG, MAX, MIN   |
| `join`           | 1.5x   | Multi-table joins           |
| `complex_filter` | 1.3x   | Multiple WHERE conditions   |
| `ranking`        | 1.2x   | ORDER BY + LIMIT            |
| `time_range`     | 1.4x   | Date/time filters           |
| `vietnamese`     | 1.5x   | Vietnamese language queries |
| `edge_case`      | 2.0x   | Edge cases, SQL injection   |
| `non_query`      | 1.0x   | Greetings, help requests    |

## Test Cases Structure

```json
{
  "id": "AG001",
  "category": "aggregation",
  "question": "How many users are there?",
  "expected_tables": ["users"],
  "expected_type": "SELECT",
  "gold_sql": "SELECT COUNT(*) FROM users",
  "validation": "single_value"
}
```

### Validation Rules

| Rule                | Description                 |
| ------------------- | --------------------------- |
| `row_count > 0`     | Result has at least 1 row   |
| `single_value`      | Exactly 1 row returned      |
| `has_join`          | SQL contains JOIN clause    |
| `has_group_by`      | SQL contains GROUP BY       |
| `has_order_by`      | SQL contains ORDER BY       |
| `has_limit`         | SQL contains LIMIT          |
| `has_where`         | SQL contains WHERE clause   |
| `has_date_filter`   | SQL contains date functions |
| `greeting_detected` | Should NOT generate SQL     |
| `blocked`           | Dangerous query blocked     |

## Output Example

```
======================================================================
📊 NL2SQL BENCHMARK REPORT
======================================================================
Timestamp: 2024-01-15T10:30:00

📈 OVERALL SUMMARY
----------------------------------------
  Total Tests:      50
  Passed:           45 (90.0%)
  Failed:           5
  Valid SQL Rate:   95.0%
  Avg Confidence:   0.87
  Cache Hit Rate:   25.0%

⏱️  LATENCY METRICS
----------------------------------------
  Average:   150ms
  P50:       120ms
  P95:       350ms
  P99:       500ms

📂 CATEGORY BREAKDOWN
----------------------------------------------------------------------
Category             Tests    Passed   Accuracy   Avg Latency
----------------------------------------------------------------------
simple_lookup        5        5        100.0%         80ms
aggregation          6        6        100.0%        120ms
join                 5        4         80.0%        250ms
...
```

## CI/CD Integration

```yaml
# GitHub Actions example
- name: Run Benchmarks
  run: |
    python benchmarks/benchmark_runner.py --all --export results.json

- name: Check Accuracy Threshold
  run: |
    accuracy=$(cat results.json | jq '.overall_accuracy')
    if (( $(echo "$accuracy < 85" | bc -l) )); then
      echo "Accuracy below threshold!"
      exit 1
    fi
```

## Adding New Test Cases

Edit `test_cases.json`:

```json
{
  "id": "NEW001",
  "category": "simple_lookup",
  "question": "Your new test question",
  "expected_tables": ["table_name"],
  "expected_type": "SELECT",
  "gold_sql": "SELECT * FROM table_name",
  "validation": "row_count > 0"
}
```

## Comparing Results

```python
import json

# Load two benchmark results
with open("benchmark_v1.json") as f:
    v1 = json.load(f)
with open("benchmark_v2.json") as f:
    v2 = json.load(f)

# Compare
print(f"Accuracy: {v1['overall_accuracy']}% → {v2['overall_accuracy']}%")
print(f"P95 Latency: {v1['p95_latency_ms']}ms → {v2['p95_latency_ms']}ms")
```
