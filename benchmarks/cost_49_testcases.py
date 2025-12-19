"""
Cost Calculator for 49 Test Cases
Tính chi phí chạy 49 test cases trên các mô hình LLM khác nhau
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import random


@dataclass
class QueryCostEstimate:
    """Estimate chi phí cho một query"""
    test_id: str
    category: str
    question: str
    input_tokens: int
    output_tokens: int
    difficulty_multiplier: float  # Câu hỏi khó tốn token hơn


# Chi phí các mô hình (từ analysis trước)
MODEL_COSTS = {
    "GPT-4o": {
        "input_cost_per_1k": 0.005,
        "output_cost_per_1k": 0.015,
    },
    "Claude 3.5 Sonnet": {
        "input_cost_per_1k": 0.003,
        "output_cost_per_1k": 0.015,
    },
    "Gemini 2.0 Pro": {
        "input_cost_per_1k": 0.00075,
        "output_cost_per_1k": 0.003,
    },
    "DeepSeek v3": {
        "input_cost_per_1k": 0.00014,
        "output_cost_per_1k": 0.00042,
    },
    "Qwen Max": {
        "input_cost_per_1k": 0.00057,
        "output_cost_per_1k": 0.0023,
    },
    "Llama 3.1 405B": {
        "input_cost_per_1k": 0.0009,
        "output_cost_per_1k": 0.009,
    },
}

# Nhân tố khó độ và token estimate dựa vào loại câu hỏi
CATEGORY_MULTIPLIERS = {
    "simple_lookup": {"multiplier": 0.8, "avg_input": 380, "avg_output": 300},
    "aggregation": {"multiplier": 1.1, "avg_input": 420, "avg_output": 350},
    "join": {"multiplier": 1.3, "avg_input": 480, "avg_output": 420},
    "complex_filter": {"multiplier": 1.2, "avg_input": 450, "avg_output": 400},
    "ranking": {"multiplier": 1.0, "avg_input": 410, "avg_output": 350},
    "time_range": {"multiplier": 1.15, "avg_input": 440, "avg_output": 380},
    "vietnamese": {"multiplier": 1.4, "avg_input": 520, "avg_output": 450},
    "edge_case": {"multiplier": 1.5, "avg_input": 550, "avg_output": 500},
    "non_query": {"multiplier": 0.7, "avg_input": 300, "avg_output": 250},
}


def load_test_cases(filepath: str) -> List[Dict]:
    """Load test cases từ JSON"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('test_cases', [])


def estimate_tokens_for_query(test_case: Dict) -> Tuple[int, int]:
    """Estimate input/output tokens cho một query"""
    category = test_case.get('category', 'simple_lookup')
    multiplier_data = CATEGORY_MULTIPLIERS.get(category, CATEGORY_MULTIPLIERS['simple_lookup'])
    
    # Thêm variation ngẫu nhiên (+/- 10%)
    variation = 0.9 + (random.random() * 0.2)
    
    input_tokens = int(multiplier_data['avg_input'] * multiplier_data['multiplier'] * variation)
    output_tokens = int(multiplier_data['avg_output'] * multiplier_data['multiplier'] * variation)
    
    return input_tokens, output_tokens


def calculate_query_cost(input_tokens: int, output_tokens: int, model_config: Dict) -> float:
    """Tính chi phí cho một query"""
    input_cost = (input_tokens / 1000) * model_config['input_cost_per_1k']
    output_cost = (output_tokens / 1000) * model_config['output_cost_per_1k']
    return input_cost + output_cost


def analyze_49_test_cases():
    """Phân tích chi phí cho 49 test cases"""
    test_cases_path = Path(__file__).parent / "test_cases.json"
    all_test_cases = load_test_cases(str(test_cases_path))
    
    # Lấy 49 test cases (hoặc tất cả nếu có ít hơn)
    test_cases_49 = all_test_cases[:49]
    actual_count = len(test_cases_49)
    
    print(f"📋 Tổng test cases có sẵn: {len(all_test_cases)}")
    print(f"📋 Sử dụng: {actual_count} test cases\n")
    
    # Tính chi phí cho mỗi test case trên mỗi mô hình
    results = {}
    total_costs = {model: 0.0 for model in MODEL_COSTS.keys()}
    
    for idx, test_case in enumerate(test_cases_49, 1):
        test_id = test_case.get('id', f'TC{idx}')
        category = test_case.get('category', 'unknown')
        question = test_case.get('question', '')
        
        input_tokens, output_tokens = estimate_tokens_for_query(test_case)
        
        results[test_id] = {
            "category": category,
            "question": question[:60],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "costs": {}
        }
        
        # Tính chi phí cho mỗi mô hình
        for model_name, config in MODEL_COSTS.items():
            cost = calculate_query_cost(input_tokens, output_tokens, config)
            results[test_id]["costs"][model_name] = cost
            total_costs[model_name] += cost
    
    return results, total_costs, actual_count


def print_cost_table(results: Dict, total_costs: Dict, actual_count: int):
    """In bảng chi phí"""
    print("="*150)
    print(f"CHI PHÍ CHẠY {actual_count} TEST CASES TRÊN CÁC MÔ HÌNH LLM")
    print("="*150 + "\n")
    
    # Bảng chi tiết (một số samples)
    print("📊 CHI PHÍ CHI TIẾT (Top 10 test cases + Bottom 5):\n")
    print(f"{'#':<3} {'Test ID':<8} {'Category':<18} {'Input':<8} {'Output':<8} {'GPT-4o':<10} {'Claude':<10} {'Gemini':<10} {'DeepSeek':<10}")
    print("-"*150)
    
    sorted_results = sorted(results.items(), key=lambda x: x[1]['costs']['GPT-4o'], reverse=True)
    
    # Top 10
    for idx, (test_id, data) in enumerate(sorted_results[:10], 1):
        print(f"{idx:<3} {test_id:<8} {data['category']:<18} {data['input_tokens']:<8} {data['output_tokens']:<8} ${data['costs']['GPT-4o']:<9.6f} ${data['costs']['Claude 3.5 Sonnet']:<9.6f} ${data['costs']['Gemini 2.0 Pro']:<9.6f} ${data['costs']['DeepSeek v3']:<9.6f}")
    
    print("...")
    
    # Bottom 5
    for idx, (test_id, data) in enumerate(sorted_results[-5:], len(sorted_results)-4):
        print(f"{idx:<3} {test_id:<8} {data['category']:<18} {data['input_tokens']:<8} {data['output_tokens']:<8} ${data['costs']['GPT-4o']:<9.6f} ${data['costs']['Claude 3.5 Sonnet']:<9.6f} ${data['costs']['Gemini 2.0 Pro']:<9.6f} ${data['costs']['DeepSeek v3']:<9.6f}")
    
    # Tổng chi phí
    print("\n" + "="*150)
    print("💰 TỔNG CHI PHÍ CHO 49 TEST CASES\n")
    print(f"{'Mô hình':<25} {'Chi phí ($)':<15} {'Trung bình/query':<20} {'Xếp hạng':<10}")
    print("-"*70)
    
    sorted_totals = sorted(total_costs.items(), key=lambda x: x[1])
    for rank, (model, cost) in enumerate(sorted_totals, 1):
        avg_cost = cost / actual_count
        print(f"{model:<25} ${cost:<14.6f} ${avg_cost:<19.6f} {rank}. {'🥇' if rank == 1 else '🥈' if rank == 2 else '🥉' if rank == 3 else ''}")
    
    print("\n" + "="*150)
    print("\n📈 THỐNG KÊ\n")
    
    total_input = sum(d['input_tokens'] for d in results.values())
    total_output = sum(d['output_tokens'] for d in results.values())
    avg_input = total_input / actual_count
    avg_output = total_output / actual_count
    
    print(f"Tổng input tokens:     {total_input:,} (trung bình: {avg_input:.0f}/query)")
    print(f"Tổng output tokens:    {total_output:,} (trung bình: {avg_output:.0f}/query)")
    print(f"Tổng tokens:           {total_input + total_output:,} (trung bình: {(total_input + total_output)/actual_count:.0f}/query)")
    
    # So sánh chi phí
    print(f"\n💵 SO SÁNH CHI PHÍ\n")
    cheapest = min(total_costs.items(), key=lambda x: x[1])
    most_expensive = max(total_costs.items(), key=lambda x: x[1])
    ratio = most_expensive[1] / cheapest[1]
    
    print(f"Rẻ nhất:  {cheapest[0]:<25} ${cheapest[1]:.6f}")
    print(f"Đắt nhất: {most_expensive[0]:<25} ${most_expensive[1]:.6f}")
    print(f"Tỉ lệ:    {most_expensive[0]} đắt {ratio:.1f}x so với {cheapest[0]}")


def save_detailed_results(results: Dict, total_costs: Dict, actual_count: int):
    """Lưu kết quả chi tiết"""
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Markdown
    md_content = f"""# Chi Phí Chạy {actual_count} Test Cases

## Tóm Tắt

| Mô hình | Chi phí ($) | Trung bình/query | Xếp hạng |
|---------|-------------|------------------|----------|
"""
    
    sorted_totals = sorted(total_costs.items(), key=lambda x: x[1])
    for rank, (model, cost) in enumerate(sorted_totals, 1):
        avg_cost = cost / actual_count
        md_content += f"| {model} | ${cost:.6f} | ${avg_cost:.6f} | {rank} |\n"
    
    md_content += f"""
## Thống Kê

- **Tổng test cases**: {actual_count}
- **Tổng input tokens**: {sum(d['input_tokens'] for d in results.values()):,}
- **Tổng output tokens**: {sum(d['output_tokens'] for d in results.values()):,}
- **Tổng tokens**: {sum(d['total_tokens'] for d in results.values()):,}
- **Trung bình input/query**: {sum(d['input_tokens'] for d in results.values()) / actual_count:.0f}
- **Trung bình output/query**: {sum(d['output_tokens'] for d in results.values()) / actual_count:.0f}

## Chi Tiết Từng Test Case

| Test ID | Category | Input | Output | GPT-4o | Claude | Gemini | DeepSeek | Qwen | Llama |
|---------|----------|-------|--------|--------|--------|--------|----------|------|-------|
"""
    
    for test_id, data in sorted(results.items()):
        md_content += f"| {test_id} | {data['category']} | {data['input_tokens']} | {data['output_tokens']} | ${data['costs']['GPT-4o']:.6f} | ${data['costs']['Claude 3.5 Sonnet']:.6f} | ${data['costs']['Gemini 2.0 Pro']:.6f} | ${data['costs']['DeepSeek v3']:.6f} | ${data['costs']['Qwen Max']:.6f} | ${data['costs']['Llama 3.1 405B']:.6f} |\n"
    
    md_path = output_dir / f"cost_49_testcases_{timestamp}.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    return md_path


if __name__ == "__main__":
    results, total_costs, actual_count = analyze_49_test_cases()
    print_cost_table(results, total_costs, actual_count)
    
    md_path = save_detailed_results(results, total_costs, actual_count)
    print(f"\n📁 Chi tiết được lưu tại: {md_path}\n")
