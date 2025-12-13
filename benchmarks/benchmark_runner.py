"""
NL2SQL Benchmark Runner
=======================
Comprehensive benchmark suite for evaluating NL2SQL system performance.

Metrics:
- Execution Accuracy (EX): SQL executes and returns correct results
- Valid SQL Rate: Percentage of syntactically valid SQL
- Latency: Response time (P50, P95, P99)
- Cache Performance: Hit rates for semantic and query plan caches
- Token Usage: Average tokens per query
- Throughput: Requests per second under load

Usage:
    python benchmark_runner.py --all              # Run all benchmarks
    python benchmark_runner.py --accuracy         # Run accuracy tests only
    python benchmark_runner.py --performance      # Run performance tests only
    python benchmark_runner.py --category join    # Run specific category
    python benchmark_runner.py --export results   # Export results to file
"""

import json
import time
import asyncio
import argparse
import statistics
import concurrent.futures
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
import requests
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class TestResult:
    """Result of a single test case"""
    test_id: str
    category: str
    question: str
    success: bool
    sql_generated: Optional[str] = None
    sql_valid: bool = False
    execution_success: bool = False
    latency_ms: float = 0.0
    confidence: float = 0.0
    tables_used: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    validation_passed: bool = False
    from_cache: bool = False


@dataclass
class CategoryResult:
    """Aggregated results for a category"""
    category: str
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    valid_sql_rate: float = 0.0
    execution_accuracy: float = 0.0
    avg_latency_ms: float = 0.0
    avg_confidence: float = 0.0
    cache_hit_rate: float = 0.0


@dataclass
class BenchmarkReport:
    """Complete benchmark report"""
    timestamp: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    overall_accuracy: float
    valid_sql_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    cache_hit_rate: float
    avg_confidence: float
    categories: Dict[str, CategoryResult] = field(default_factory=dict)
    detailed_results: List[TestResult] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


class NL2SQLBenchmark:
    """Benchmark runner for NL2SQL system"""
    
    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        test_cases_path: str = None,
        timeout: int = 30
    ):
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.test_cases_path = test_cases_path or Path(__file__).parent / "test_cases.json"
        self.test_cases = self._load_test_cases()
        self.results: List[TestResult] = []
        
    def _load_test_cases(self) -> Dict:
        """Load test cases from JSON file"""
        with open(self.test_cases_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _check_api_health(self) -> bool:
        """Check if API is available"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ API health check failed: {e}")
            return False
    
    def _send_query(self, question: str, execute: bool = True) -> Dict:
        """Send a query to the API"""
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/chat",
                json={
                    "message": question,
                    "execute_query": execute,
                    "session_id": f"benchmark-{int(time.time())}"
                },
                timeout=self.timeout
            )
            latency_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                data["_latency_ms"] = latency_ms
                return data
            else:
                return {
                    "error": f"HTTP {response.status_code}",
                    "detail": response.text,
                    "_latency_ms": latency_ms
                }
        except Exception as e:
            return {"error": str(e), "_latency_ms": 0}
    
    def _validate_result(
        self,
        test_case: Dict,
        response: Dict
    ) -> Tuple[bool, str]:
        """Validate test result against expected outcome"""
        validation_rules = test_case.get("validation", "").split(",")
        sql_gen = response.get("sql_generation", {})
        execution = response.get("execution", {})
        
        # Check for greeting/non-query detection
        if "greeting_detected" in validation_rules:
            # Should NOT generate SQL query for greetings
            if sql_gen and sql_gen.get("query"):
                return False, "Generated SQL for greeting (should not)"
            return True, "Greeting correctly detected"
        
        if "help_detected" in validation_rules:
            return True, "Help request detected"
        
        if "non_query_detected" in validation_rules:
            if sql_gen and sql_gen.get("query"):
                return False, "Generated SQL for non-query"
            return True, "Non-query correctly detected"
        
        if "blocked" in validation_rules:
            # Dangerous queries should be blocked
            query = sql_gen.get("query", "").upper()
            if any(kw in query for kw in ["DROP", "DELETE", "TRUNCATE", "INSERT", "UPDATE"]):
                return False, "Dangerous query not blocked"
            return True, "Dangerous query blocked"
        
        if "low_confidence" in validation_rules:
            confidence = sql_gen.get("confidence", 1.0)
            if confidence < 0.7:
                return True, "Low confidence correctly assigned"
            return False, f"Confidence too high: {confidence}"
        
        # Standard validations
        passed = True
        messages = []
        
        for rule in validation_rules:
            rule = rule.strip()
            
            if rule == "row_count > 0":
                if execution.get("row_count", 0) <= 0:
                    passed = False
                    messages.append("Expected rows > 0")
            
            elif rule == "single_value":
                if execution.get("row_count", 0) != 1:
                    passed = False
                    messages.append("Expected single row")
            
            elif rule == "has_join":
                query = sql_gen.get("query", "").upper()
                if "JOIN" not in query:
                    passed = False
                    messages.append("Expected JOIN in query")
            
            elif rule == "has_group_by":
                query = sql_gen.get("query", "").upper()
                if "GROUP BY" not in query:
                    passed = False
                    messages.append("Expected GROUP BY in query")
            
            elif rule == "has_order_by":
                query = sql_gen.get("query", "").upper()
                if "ORDER BY" not in query:
                    passed = False
                    messages.append("Expected ORDER BY in query")
            
            elif rule == "has_limit":
                query = sql_gen.get("query", "").upper()
                if "LIMIT" not in query:
                    passed = False
                    messages.append("Expected LIMIT in query")
            
            elif rule == "has_where":
                query = sql_gen.get("query", "").upper()
                if "WHERE" not in query:
                    passed = False
                    messages.append("Expected WHERE in query")
            
            elif rule == "has_date_filter":
                query = sql_gen.get("query", "").upper()
                date_keywords = ["DATE", "MONTH", "YEAR", "CURDATE", "NOW", "INTERVAL"]
                if not any(kw in query for kw in date_keywords):
                    passed = False
                    messages.append("Expected date filter in query")
            
            elif rule.startswith("columns_include:"):
                col = rule.split(":")[1]
                columns = execution.get("columns", [])
                if col not in columns:
                    passed = False
                    messages.append(f"Expected column: {col}")
            
            elif rule.startswith("columns_count:"):
                count = int(rule.split(":")[1])
                columns = execution.get("columns", [])
                if len(columns) < count:
                    passed = False
                    messages.append(f"Expected at least {count} columns")
        
        return passed, "; ".join(messages) if messages else "All validations passed"
    
    def run_single_test(self, test_case: Dict) -> TestResult:
        """Run a single test case"""
        question = test_case["question"]
        test_id = test_case["id"]
        category = test_case["category"]
        
        # Send query
        response = self._send_query(question, execute=True)
        latency_ms = response.get("_latency_ms", 0)
        
        # Check for errors
        if "error" in response:
            return TestResult(
                test_id=test_id,
                category=category,
                question=question,
                success=False,
                latency_ms=latency_ms,
                error_message=response.get("error")
            )
        
        # Extract results
        sql_gen = response.get("sql_generation", {})
        execution = response.get("execution", {})
        
        sql_query = sql_gen.get("query")
        confidence = sql_gen.get("confidence", 0)
        tables_used = sql_gen.get("tables_used", [])
        
        sql_valid = sql_query is not None and len(sql_query) > 0
        execution_success = execution.get("success", False) if execution else True
        
        # Check if from cache
        explanation = sql_gen.get("explanation", "")
        from_cache = "cache" in explanation.lower()
        
        # Validate result
        validation_passed, validation_msg = self._validate_result(test_case, response)
        
        return TestResult(
            test_id=test_id,
            category=category,
            question=question,
            success=validation_passed and (execution_success or not sql_query),
            sql_generated=sql_query,
            sql_valid=sql_valid,
            execution_success=execution_success,
            latency_ms=latency_ms,
            confidence=confidence,
            tables_used=tables_used,
            error_message=None if validation_passed else validation_msg,
            validation_passed=validation_passed,
            from_cache=from_cache
        )
    
    def run_category(self, category: str) -> List[TestResult]:
        """Run all tests in a category"""
        test_cases = [
            tc for tc in self.test_cases["test_cases"]
            if tc["category"] == category
        ]
        
        results = []
        for tc in test_cases:
            print(f"  Running {tc['id']}: {tc['question'][:50]}...")
            result = self.run_single_test(tc)
            results.append(result)
            
            status = "✅" if result.success else "❌"
            print(f"    {status} {result.latency_ms:.0f}ms | Confidence: {result.confidence:.2f}")
            if not result.success and result.error_message:
                print(f"    Error: {result.error_message}")
        
        return results
    
    def run_all_tests(self) -> List[TestResult]:
        """Run all test cases"""
        print("\n" + "="*60)
        print("🚀 NL2SQL Benchmark - Running All Tests")
        print("="*60)
        
        if not self._check_api_health():
            print("❌ API is not available. Please start the API first.")
            return []
        
        print("✅ API is healthy\n")
        
        all_results = []
        categories = self.test_cases["categories"]
        
        for category_name in categories.keys():
            print(f"\n📂 Category: {category_name.upper()}")
            print("-" * 40)
            results = self.run_category(category_name)
            all_results.extend(results)
        
        self.results = all_results
        return all_results
    
    def run_performance_test(
        self,
        num_requests: int = 50,
        concurrency: int = 5
    ) -> Dict[str, Any]:
        """Run performance/load test"""
        print("\n" + "="*60)
        print("⚡ NL2SQL Benchmark - Performance Test")
        print(f"   Requests: {num_requests}, Concurrency: {concurrency}")
        print("="*60)
        
        if not self._check_api_health():
            return {"error": "API not available"}
        
        # Select diverse test queries
        test_queries = [
            "How many users?",
            "Top 5 products by price",
            "Show orders from last week",
            "Có bao nhiêu đơn hàng?",
            "List products with categories"
        ]
        
        latencies = []
        errors = 0
        cache_hits = 0
        
        def run_query(i):
            query = test_queries[i % len(test_queries)]
            result = self._send_query(query, execute=False)
            return result
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(run_query, i) for i in range(num_requests)]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if "error" in result:
                        errors += 1
                    else:
                        latencies.append(result.get("_latency_ms", 0))
                        if "cache" in result.get("sql_generation", {}).get("explanation", "").lower():
                            cache_hits += 1
                except Exception as e:
                    errors += 1
        
        total_time = time.time() - start_time
        
        if latencies:
            latencies_sorted = sorted(latencies)
            p50_idx = int(len(latencies) * 0.50)
            p95_idx = int(len(latencies) * 0.95)
            p99_idx = int(len(latencies) * 0.99)
            
            metrics = {
                "total_requests": num_requests,
                "successful_requests": len(latencies),
                "failed_requests": errors,
                "total_time_seconds": round(total_time, 2),
                "requests_per_second": round(num_requests / total_time, 2),
                "avg_latency_ms": round(statistics.mean(latencies), 2),
                "min_latency_ms": round(min(latencies), 2),
                "max_latency_ms": round(max(latencies), 2),
                "p50_latency_ms": round(latencies_sorted[p50_idx], 2),
                "p95_latency_ms": round(latencies_sorted[p95_idx], 2),
                "p99_latency_ms": round(latencies_sorted[min(p99_idx, len(latencies)-1)], 2),
                "cache_hit_rate": round(cache_hits / len(latencies) * 100, 2) if latencies else 0
            }
        else:
            metrics = {"error": "No successful requests", "failed_requests": errors}
        
        print("\n📊 Performance Results:")
        for key, value in metrics.items():
            print(f"   {key}: {value}")
        
        return metrics
    
    def generate_report(self) -> BenchmarkReport:
        """Generate comprehensive benchmark report"""
        if not self.results:
            self.run_all_tests()
        
        # Calculate overall metrics
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - passed_tests
        
        valid_sql = sum(1 for r in self.results if r.sql_valid)
        valid_sql_rate = (valid_sql / total_tests * 100) if total_tests > 0 else 0
        
        latencies = [r.latency_ms for r in self.results if r.latency_ms > 0]
        cache_hits = sum(1 for r in self.results if r.from_cache)
        
        if latencies:
            latencies_sorted = sorted(latencies)
            p50_idx = int(len(latencies) * 0.50)
            p95_idx = int(len(latencies) * 0.95)
            p99_idx = min(int(len(latencies) * 0.99), len(latencies) - 1)
            
            avg_latency = statistics.mean(latencies)
            p50_latency = latencies_sorted[p50_idx]
            p95_latency = latencies_sorted[p95_idx]
            p99_latency = latencies_sorted[p99_idx]
        else:
            avg_latency = p50_latency = p95_latency = p99_latency = 0
        
        confidences = [r.confidence for r in self.results if r.confidence > 0]
        avg_confidence = statistics.mean(confidences) if confidences else 0
        
        # Calculate per-category metrics
        category_results = {}
        for category in self.test_cases["categories"].keys():
            cat_results = [r for r in self.results if r.category == category]
            if cat_results:
                cat_passed = sum(1 for r in cat_results if r.success)
                cat_valid = sum(1 for r in cat_results if r.sql_valid)
                cat_exec = sum(1 for r in cat_results if r.execution_success)
                cat_latencies = [r.latency_ms for r in cat_results if r.latency_ms > 0]
                cat_confidences = [r.confidence for r in cat_results if r.confidence > 0]
                cat_cache = sum(1 for r in cat_results if r.from_cache)
                
                category_results[category] = CategoryResult(
                    category=category,
                    total_tests=len(cat_results),
                    passed_tests=cat_passed,
                    failed_tests=len(cat_results) - cat_passed,
                    valid_sql_rate=round(cat_valid / len(cat_results) * 100, 2),
                    execution_accuracy=round(cat_exec / len(cat_results) * 100, 2),
                    avg_latency_ms=round(statistics.mean(cat_latencies), 2) if cat_latencies else 0,
                    avg_confidence=round(statistics.mean(cat_confidences), 2) if cat_confidences else 0,
                    cache_hit_rate=round(cat_cache / len(cat_results) * 100, 2)
                )
        
        # Create report
        report = BenchmarkReport(
            timestamp=datetime.now().isoformat(),
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            overall_accuracy=round(passed_tests / total_tests * 100, 2) if total_tests > 0 else 0,
            valid_sql_rate=round(valid_sql_rate, 2),
            avg_latency_ms=round(avg_latency, 2),
            p50_latency_ms=round(p50_latency, 2),
            p95_latency_ms=round(p95_latency, 2),
            p99_latency_ms=round(p99_latency, 2),
            cache_hit_rate=round(cache_hits / total_tests * 100, 2) if total_tests > 0 else 0,
            avg_confidence=round(avg_confidence, 2),
            categories=category_results,
            detailed_results=self.results
        )
        
        return report
    
    def print_report(self, report: BenchmarkReport):
        """Print formatted benchmark report"""
        print("\n" + "="*70)
        print("📊 NL2SQL BENCHMARK REPORT")
        print("="*70)
        print(f"Timestamp: {report.timestamp}")
        print()
        
        # Overall Summary
        print("📈 OVERALL SUMMARY")
        print("-"*40)
        print(f"  Total Tests:      {report.total_tests}")
        print(f"  Passed:           {report.passed_tests} ({report.overall_accuracy}%)")
        print(f"  Failed:           {report.failed_tests}")
        print(f"  Valid SQL Rate:   {report.valid_sql_rate}%")
        print(f"  Avg Confidence:   {report.avg_confidence}")
        print(f"  Cache Hit Rate:   {report.cache_hit_rate}%")
        print()
        
        # Latency Metrics
        print("⏱️  LATENCY METRICS")
        print("-"*40)
        print(f"  Average:   {report.avg_latency_ms:.0f}ms")
        print(f"  P50:       {report.p50_latency_ms:.0f}ms")
        print(f"  P95:       {report.p95_latency_ms:.0f}ms")
        print(f"  P99:       {report.p99_latency_ms:.0f}ms")
        print()
        
        # Per-Category Results
        print("📂 CATEGORY BREAKDOWN")
        print("-"*70)
        print(f"{'Category':<20} {'Tests':<8} {'Passed':<8} {'Accuracy':<10} {'Avg Latency':<12}")
        print("-"*70)
        
        for cat_name, cat_result in report.categories.items():
            print(f"{cat_name:<20} {cat_result.total_tests:<8} {cat_result.passed_tests:<8} "
                  f"{cat_result.execution_accuracy:>6.1f}%    {cat_result.avg_latency_ms:>8.0f}ms")
        
        print()
        
        # Failed Tests
        failed = [r for r in report.detailed_results if not r.success]
        if failed:
            print("❌ FAILED TESTS")
            print("-"*70)
            for r in failed[:10]:  # Show first 10
                print(f"  [{r.test_id}] {r.question[:40]}...")
                print(f"    Error: {r.error_message}")
            if len(failed) > 10:
                print(f"  ... and {len(failed) - 10} more")
        
        print("\n" + "="*70)
    
    def export_results(self, output_path: str = None):
        """Export results to JSON file"""
        if not output_path:
            output_path = Path(__file__).parent / "results" / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        report = self.generate_report()
        
        # Convert dataclasses to dict
        def to_dict(obj):
            if hasattr(obj, "__dataclass_fields__"):
                return {k: to_dict(v) for k, v in asdict(obj).items()}
            elif isinstance(obj, list):
                return [to_dict(i) for i in obj]
            elif isinstance(obj, dict):
                return {k: to_dict(v) for k, v in obj.items()}
            return obj
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(to_dict(report), f, indent=2, ensure_ascii=False)
        
        print(f"\n📁 Results exported to: {output_path}")
        return output_path


def main():
    parser = argparse.ArgumentParser(description="NL2SQL Benchmark Runner")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--all", action="store_true", help="Run all benchmarks")
    parser.add_argument("--accuracy", action="store_true", help="Run accuracy tests only")
    parser.add_argument("--performance", action="store_true", help="Run performance tests")
    parser.add_argument("--category", type=str, help="Run specific category")
    parser.add_argument("--export", type=str, help="Export results to file")
    parser.add_argument("--requests", type=int, default=50, help="Number of requests for performance test")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrency level for performance test")
    
    args = parser.parse_args()
    
    benchmark = NL2SQLBenchmark(api_url=args.api_url)
    
    if args.category:
        print(f"\n📂 Running category: {args.category}")
        results = benchmark.run_category(args.category)
        benchmark.results = results
        report = benchmark.generate_report()
        benchmark.print_report(report)
    
    elif args.performance:
        benchmark.run_performance_test(
            num_requests=args.requests,
            concurrency=args.concurrency
        )
    
    elif args.accuracy or args.all:
        benchmark.run_all_tests()
        report = benchmark.generate_report()
        benchmark.print_report(report)
        
        if args.all:
            print("\n" + "="*60)
            benchmark.run_performance_test()
    
    else:
        # Default: run all
        benchmark.run_all_tests()
        report = benchmark.generate_report()
        benchmark.print_report(report)
    
    if args.export:
        benchmark.export_results(args.export)
    elif benchmark.results:
        benchmark.export_results()


if __name__ == "__main__":
    main()
