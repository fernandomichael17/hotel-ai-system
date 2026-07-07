import os
import sys
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

# Menambahkan root project ke sys.path agar modul backend dapat diimpor secara langsung
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.integrations.llm.client import LLMClient
from backend.core.classifier.intent_classifier import IntentClassifier, ParameterExtractor
from backend.core.classifier.schemas import IntentType

def normalize_val(val: Any) -> str:
    """
    Menormalisasi nilai untuk perbandingan string yang aman (lowercase, strip, menyamakan null/none/empty).
    """
    if val is None:
        return ""
    val_str = str(val).strip().lower()
    if val_str in ("null", "none", ""):
        return ""
    return val_str

def run_evaluation() -> None:
    """
    Menjalankan evaluasi lengkap (Test Utama, Test A, Test B, Test C) secara paralel
    dan menyimpan laporannya ke berkas JSON serta menampilkan tabel ringkasan ke terminal.
    """
    # 1. Definisikan path file fixtures
    fixtures = {
        "utama": os.path.join(ROOT_DIR, "tests", "fixtures", "sample_messages.json"),
        "test_a": os.path.join(ROOT_DIR, "tests", "fixtures", "multiturn_messages.json"),
        "test_b": os.path.join(ROOT_DIR, "tests", "fixtures", "extraction_messages.json"),
        "test_c": os.path.join(ROOT_DIR, "tests", "fixtures", "dual_intent_messages.json")
    }

    results_dir = os.path.join(ROOT_DIR, "ml", "eval", "results")
    output_path = os.path.join(results_dir, "latest.json")
    os.makedirs(results_dir, exist_ok=True)

    # Membaca semua data uji
    datasets = {}
    for name, path in fixtures.items():
        if not os.path.exists(path):
            print(f"Error: Berkas fixture {name} tidak ditemukan di {path}")
            return
        with open(path, "r", encoding="utf-8") as f:
            datasets[name] = json.load(f)

    llm_client = LLMClient()
    classifier = IntentClassifier(llm_client)
    extractor = ParameterExtractor(llm_client)

    # 2. Definisikan tugas-tugas evaluasi untuk dimasukkan ke thread pool
    tasks = []

    # Tugas Test Utama (Single-turn)
    for i, s in enumerate(datasets["utama"]):
        tasks.append({
            "suite": "utama",
            "index": i + 1,
            "fn": lambda sample=s: classifier.classify(sample["message"]),
            "sample": s
        })

    # Tugas Test A (Multi-turn)
    for i, s in enumerate(datasets["test_a"]):
        tasks.append({
            "suite": "test_a",
            "index": i + 1,
            "fn": lambda sample=s: classifier.classify_multiturn(sample["history"], sample["message"]),
            "sample": s
        })

    # Tugas Test B (Parameter Extraction)
    for i, s in enumerate(datasets["test_b"]):
        tasks.append({
            "suite": "test_b",
            "index": i + 1,
            "fn": lambda sample=s: extractor.extract(sample["message"]),
            "sample": s
        })

    # Tugas Test C (Dual Intent)
    for i, s in enumerate(datasets["test_c"]):
        tasks.append({
            "suite": "test_c",
            "index": i + 1,
            "fn": lambda sample=s: classifier.classify_dual(sample["message"]),
            "sample": s
        })

    print(f"Memulai evaluasi total {len(tasks)} tugas dari 4 test suite secara paralel...")

    # Jalankan semua tugas secara paralel
    evaluated_results = []
    completed_count = 0

    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit semua fungsi lambda
        future_to_task = {executor.submit(task["fn"]): task for task in tasks}

        for future in as_completed(future_to_task):
            task = future_to_task[future]
            suite = task["suite"]
            sample = task["sample"]
            index = task["index"]
            
            completed_count += 1
            
            try:
                res_obj = future.result()
                raw_response = res_obj.raw_response
                error_msg = None
            except Exception as exc:
                res_obj = None
                raw_response = ""
                error_msg = str(exc)

            eval_entry = {
                "suite": suite,
                "message": sample.get("message", ""),
                "raw_response": raw_response,
                "correct": False,
                "error": error_msg
            }

            # Lakukan pencocokan spesifik per suite
            if error_msg is None and res_obj is not None:
                if suite == "utama":
                    predicted = res_obj.intent.value
                    expected = sample["expected_intent"]
                    is_correct = (predicted == expected)
                    eval_entry.update({
                        "expected": expected,
                        "predicted": predicted,
                        "difficulty": sample["difficulty"],
                        "correct": is_correct
                    })
                elif suite == "test_a":
                    predicted = res_obj.intent.value
                    expected = sample["expected_intent"]
                    is_correct = (predicted == expected)
                    eval_entry.update({
                        "history": sample["history"],
                        "expected": expected,
                        "predicted": predicted,
                        "correct": is_correct
                    })
                elif suite == "test_b":
                    # Evaluasi pencocokan parameter
                    expected = sample["expected"]
                    actual = {
                        "name": res_obj.name,
                        "check_in_date": res_obj.check_in_date,
                        "check_out_date": res_obj.check_out_date,
                        "room_type": res_obj.room_type
                    }
                    
                    # Bandingkan tiap key secara aman
                    param_matches = {}
                    is_correct = True
                    for k in expected.keys():
                        is_match = (normalize_val(expected[k]) == normalize_val(actual[k]))
                        param_matches[k] = is_match
                        if not is_match:
                            is_correct = False

                    eval_entry.update({
                        "expected": expected,
                        "predicted": actual,
                        "param_matches": param_matches,
                        "correct": is_correct
                    })
                elif suite == "test_c":
                    predicted = [intent.value for intent in res_obj.intents]
                    expected = sample["expected_intents"]
                    is_correct = (set(predicted) == set(expected))
                    eval_entry.update({
                        "expected": expected,
                        "predicted": predicted,
                        "correct": is_correct
                    })
            else:
                eval_entry["correct"] = False

            evaluated_results.append(eval_entry)

            # Cetak log progress ke terminal
            indicator = "✓" if eval_entry["correct"] else "✗"
            suite_label = {
                "utama": "UTAMA",
                "test_a": "TEST A (MULTI-TURN)",
                "test_b": "TEST B (EXTRACTION)",
                "test_c": "TEST C (DUAL INTENT)"
            }[suite]
            print(f"[{completed_count}/{len(tasks)}] {indicator} [{suite_label}] Msg: \"{eval_entry['message'][:35]}...\"")

    # 3. Pengelompokan metrik hasil evaluasi
    suite_metrics = {
        "utama": {"correct": 0, "total": 0},
        "test_a": {"correct": 0, "total": 0},
        "test_b": {"correct": 0, "total": 0},
        "test_c": {"correct": 0, "total": 0}
    }

    # Metrik detail untuk Test Utama
    stats_intent = {}
    stats_diff = {}

    for item in evaluated_results:
        suite = item["suite"]
        suite_metrics[suite]["total"] += 1
        if item["correct"]:
            suite_metrics[suite]["correct"] += 1

        if suite == "utama":
            exp = item["expected"]
            diff = item["difficulty"]
            if exp not in stats_intent:
                stats_intent[exp] = {"correct": 0, "total": 0}
            if diff not in stats_diff:
                stats_diff[diff] = {"correct": 0, "total": 0}

            stats_intent[exp]["total"] += 1
            stats_diff[diff]["total"] += 1
            if item["correct"]:
                stats_intent[exp]["correct"] += 1
                stats_diff[diff]["correct"] += 1

    # 4. Tampilkan Tabel Ringkasan Hasil ke Terminal
    print("\n" + "=" * 65)
    print(" HASIL RINGKASAN EVALUASI POC ".center(65, "="))
    print("=" * 65)
    print(f"Waktu Evaluasi : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 65)
    print(f"{'Test Suite':<28} | {'Correct':<8} | {'Total':<6} | {'Accuracy':<10}")
    print("-" * 65)
    for suite_name, counts in suite_metrics.items():
        label = {
            "utama": "Test Utama (Single-turn)",
            "test_a": "Test A (Multi-turn)",
            "test_b": "Test B (Parameter Extract)",
            "test_c": "Test C (Dual Intent)"
        }[suite_name]
        acc = counts["correct"] / counts["total"] * 100 if counts["total"] > 0 else 0.0
        print(f"{label:<28} | {counts['correct']:<8} | {counts['total']:<6} | {acc:.2f}%")
    print("=" * 65)

    # Tampilkan detail Test Utama jika dijalankan
    if suite_metrics["utama"]["total"] > 0:
        print("\nAKURASI DETIL TEST UTAMA (BY INTENT):")
        print("-" * 55)
        print(f"{'Intent':<20} | {'Correct':<8} | {'Total':<6} | {'Accuracy':<10}")
        print("-" * 55)
        for intent, metrics in sorted(stats_intent.items()):
            acc = metrics["correct"] / metrics["total"] * 100 if metrics["total"] > 0 else 0.0
            print(f"{intent:<20} | {metrics['correct']:<8} | {metrics['total']:<6} | {acc:.2f}%")
        print("-" * 55)

        print("\nAKURASI DETIL TEST UTAMA (BY DIFFICULTY):")
        print("-" * 55)
        print(f"{'Difficulty':<20} | {'Correct':<8} | {'Total':<6} | {'Accuracy':<10}")
        print("-" * 55)
        for diff, metrics in sorted(stats_diff.items()):
            acc = metrics["correct"] / metrics["total"] * 100 if metrics["total"] > 0 else 0.0
            print(f"{diff:<20} | {metrics['correct']:<8} | {metrics['total']:<6} | {acc:.2f}%")
        print("-" * 55)

    # 5. Simpan Hasil ke file JSON
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            s_name: {
                "correct": s_counts["correct"],
                "total": s_counts["total"],
                "accuracy": s_counts["correct"] / s_counts["total"] if s_counts["total"] > 0 else 0.0
            } for s_name, s_counts in suite_metrics.items()
        },
        "details": evaluated_results
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
    print(f"\nHasil evaluasi lengkap disimpan ke: {output_path}\n")

if __name__ == "__main__":
    run_evaluation()
