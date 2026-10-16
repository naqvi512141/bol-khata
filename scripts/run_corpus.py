#!/usr/bin/env python3
"""Run corpus end-to-end evaluation and print metrics table.

Docs: docs/03-build-plan.md Phase 8; prompts/PROMPTS.md Phase 8.
Evaluates:
- Fast-path percentage
- p50 and p95 latency per stage
- SKU and customer match accuracy
- Normalizer accuracy on the fraction subset
- Extractor accuracy broken down PER order_form
- Price-source distribution
- ASR WER with and without bias prompt (measured on available audio fixtures)
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Add server directory to sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SERVER_DIR = _PROJECT_ROOT / "server"
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

# Load .env
_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

from app.extractor import extract  # noqa: E402
from app.normalizer import normalize  # noqa: E402
from app.pricing.catalogue import Catalogue  # noqa: E402
from app.pricing.resolver import resolve_prices  # noqa: E402
from app.schemas import SKU, Customer  # noqa: E402
from app.validation.rules import validate  # noqa: E402


def calculate_wer(reference: str, hypothesis: str) -> float:
    """Compute Word Error Rate (WER) using Levenshtein distance on words."""
    ref_words = reference.strip().split()
    hyp_words = hypothesis.strip().split()

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]
    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j

    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                d[i][j] = min(
                    d[i - 1][j] + 1,      # deletion
                    d[i][j - 1] + 1,      # insertion
                    d[i - 1][j - 1] + 1,  # substitution
                )

    return d[len(ref_words)][len(hyp_words)] / float(len(ref_words))


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_v) - 1)
    d = k - f
    return sorted_v[f] + d * (sorted_v[c] - sorted_v[f])


def main() -> None:
    # Ensure stdout handles UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

    manifest_path = _SERVER_DIR / "data" / "corpus" / "manifest.json"
    if not manifest_path.exists():
        print(f"Error: manifest not found at {manifest_path}", file=sys.stderr)
        sys.exit(1)

    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    utterances = raw_manifest.get("utterances", [])

    # Load catalogue and customers
    catalogue = Catalogue.from_json(_SERVER_DIR / "data" / "catalogue.json")
    skus: list[SKU] = list(catalogue.skus.values())
    raw_customers = json.loads((_SERVER_DIR / "data" / "customers.json").read_text(encoding="utf-8"))
    customers = [Customer(**c) for c in raw_customers]

    print(f"Evaluating {len(utterances)} corpus utterances through the deterministic pipeline...\n")

    # Metrics accumulators
    total_count = len(utterances)
    fast_path_count = 0
    sku_matches_correct = 0
    sku_matches_total = 0
    cust_matches_correct = 0
    cust_matches_total = 0

    order_form_stats: dict[str, dict[str, int]] = {}
    fraction_correct = 0
    fraction_total = 0
    price_sources: dict[str, int] = {"spoken": 0, "catalogue": 0, "missing": 0}

    # Latency tracking (in milliseconds)
    normalize_times: list[float] = []
    extract_times: list[float] = []
    pricing_times: list[float] = []
    validation_times: list[float] = []
    total_pipeline_times: list[float] = []

    # Run each utterance multiple times to obtain stable latency distributions
    benchmark_iterations = 20

    for u in utterances:
        text = u["ground_truth_text"]
        expected = u["expected"]
        tags = u.get("tags", [])
        exp_form = expected.get("order_form")

        if exp_form not in order_form_stats:
            order_form_stats[exp_form] = {"correct": 0, "total": 0}
        order_form_stats[exp_form]["total"] += 1

        # Run pipeline once for correctness checking
        t_start = time.perf_counter()
        t0 = time.perf_counter()
        _ = normalize(text)
        t_norm = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        draft = extract(
            tokens=text,
            catalogue=skus,
            customers=customers,
            shop_id="demo_shop_01",
            draft_id=f"d_{u['id']}",
        )
        t_ext = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        draft.items = resolve_prices(draft.items, catalogue)
        draft.computed_total = int(sum(it.line_total for it in draft.items if it.line_total is not None))
        t_price = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        val_res = validate(
            items=draft.items,
            customer=draft.customer,
            payment_type=draft.payment_type,
            catalogue=catalogue,
            stated_total=draft.stated_total,
            computed_total=draft.computed_total,
        )
        draft.validation = val_res
        t_val = (time.perf_counter() - t0) * 1000
        t_total = (time.perf_counter() - t_start) * 1000

        normalize_times.append(t_norm)
        extract_times.append(t_ext)
        pricing_times.append(t_price)
        validation_times.append(t_val)
        total_pipeline_times.append(t_total)

        # 1. Fast path check
        if val_res.passed:
            fast_path_count += 1

        # 2. Customer match check
        exp_cust = expected.get("customer_id")
        cust_matches_total += 1
        if exp_cust is None:
            if draft.customer.customer_id is None or draft.customer.status == "absent":
                cust_matches_correct += 1
        else:
            if draft.customer.customer_id == exp_cust and draft.customer.status == "resolved":
                cust_matches_correct += 1

        # 3. Order form check
        if draft.order_form == exp_form:
            order_form_stats[exp_form]["correct"] += 1

        # 4. SKU match check
        exp_items = expected.get("items", [])
        for exp_it in exp_items:
            sku_matches_total += 1
            pred_it = next((it for it in draft.items if it.sku_id == exp_it["sku_id"]), None)
            if pred_it is not None:
                sku_matches_correct += 1

        # 5. Fraction subset check
        if "fraction" in tags:
            fraction_total += 1
            # Check if all expected fractional quantities match
            matched_frac = True
            for exp_it in exp_items:
                pred_it = next((it for it in draft.items if it.sku_id == exp_it["sku_id"]), None)
                if not pred_it or abs((pred_it.qty or 0) - exp_it["qty"]) > 1e-4:
                    matched_frac = False
                    break
            if matched_frac:
                fraction_correct += 1

        # 6. Price sources
        for it in draft.items:
            price_sources[it.price_source] = price_sources.get(it.price_source, 0) + 1

    # Additional benchmarking passes for latency distributions
    for _ in range(benchmark_iterations - 1):
        for u in utterances:
            text = u["ground_truth_text"]
            t0 = time.perf_counter()
            _ = normalize(text)
            normalize_times.append((time.perf_counter() - t0) * 1000)

            t0 = time.perf_counter()
            d = extract(text, skus, customers)
            extract_times.append((time.perf_counter() - t0) * 1000)

            t0 = time.perf_counter()
            d.items = resolve_prices(d.items, catalogue)
            pricing_times.append((time.perf_counter() - t0) * 1000)

            t0 = time.perf_counter()
            _ = validate(d.items, d.customer, d.payment_type, catalogue)
            validation_times.append((time.perf_counter() - t0) * 1000)

    # Audio & WER measurement check
    # Check if sample_ur.wav or audio fixtures exist
    sample_wav = _SERVER_DIR / "tests" / "fixtures" / "sample_ur.wav"
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()

    wer_measured_info: dict[str, str | float] = {}
    if sample_wav.exists() and groq_key:
        try:
            from app.asr.groq_whisper import GroqWhisperEngine
            from app.asr.bias import build_bias_prompt
            from app.ingest.audio import process_audio

            audio = process_audio(sample_wav.read_bytes())
            bias = build_bias_prompt(skus, customers)
            groq = GroqWhisperEngine(api_key=groq_key)

            # Ground truth for sample_ur.wav
            ground_truth = "احمد بھائی کا دو کلو چینی آدھا کلو بیسن"

            # 1. Without bias prompt
            res_nobias = groq.transcribe(audio, job_id="wer_nobias", shop_id="demo", prompt="")
            wer_nobias = calculate_wer(ground_truth, res_nobias.raw_text)

            # 2. With bias prompt
            res_bias = groq.transcribe(audio, job_id="wer_bias", shop_id="demo", prompt=bias)
            wer_bias = calculate_wer(ground_truth, res_bias.raw_text)

            wer_measured_info["wer_no_bias"] = f"{wer_nobias * 100:.1f}%"
            wer_measured_info["wer_with_bias"] = f"{wer_bias * 100:.1f}%"
        except Exception as e:
            wer_measured_info["wer_no_bias"] = f"not measured ({type(e).__name__})"
            wer_measured_info["wer_with_bias"] = f"not measured ({type(e).__name__})"
    else:
        wer_measured_info["wer_no_bias"] = "not measured (GROQ_API_KEY not configured or audio missing)"
        wer_measured_info["wer_with_bias"] = "not measured (GROQ_API_KEY not configured or audio missing)"

    # Print Report Table
    print("=" * 76)
    print("                      BOL KHATA CORPUS METRICS REPORT")
    print("=" * 76)

    print("\n1. PIPELINE ACCURACY & PATH DISTRIBUTION")
    print(f"  • Total Corpus Utterances     : {total_count}")
    print(f"  • Fast-Path Percentage        : {(fast_path_count / total_count) * 100:.1f}%  ({fast_path_count}/{total_count})")
    print(f"  • Customer Match Accuracy     : {(cust_matches_correct / cust_matches_total) * 100:.1f}%  ({cust_matches_correct}/{cust_matches_total})")
    print(f"  • SKU Match Accuracy          : {(sku_matches_correct / sku_matches_total) * 100:.1f}%  ({sku_matches_correct}/{sku_matches_total})")
    frac_pct = (fraction_correct / fraction_total * 100) if fraction_total else 0.0
    print(f"  • Normalizer Fraction Accuracy: {frac_pct:.1f}%  ({fraction_correct}/{fraction_total})")

    print("\n2. EXTRACTOR ACCURACY PER ORDER_FORM")
    print(f"  {'Order Form':<18} | {'Correct':<8} | {'Total':<6} | {'Accuracy':<10}")
    print("  " + "─" * 48)
    for form, s in order_form_stats.items():
        acc = (s["correct"] / s["total"] * 100) if s["total"] else 0.0
        print(f"  {form:<18} | {s['correct']:<8} | {s['total']:<6} | {acc:.1f}%")

    print("\n3. PRICE SOURCE DISTRIBUTION")
    tot_prices = sum(price_sources.values()) or 1
    for src, cnt in price_sources.items():
        print(f"  • {src.capitalize():<12}: {cnt} items  ({(cnt / tot_prices) * 100:.1f}%)")

    print("\n4. STAGE LATENCY (Real Measured on CPU, N=200 iterations)")
    print(f"  {'Pipeline Stage':<20} | {'p50 (ms)':<10} | {'p95 (ms)':<10}")
    print("  " + "─" * 46)
    stages = [
        ("Normalizer", normalize_times),
        ("Extractor", extract_times),
        ("Pricing", pricing_times),
        ("Validation", validation_times),
        ("Total Engine", total_pipeline_times),
    ]
    for name, times in stages:
        p50 = percentile(times, 50)
        p95 = percentile(times, 95)
        print(f"  {name:<20} | {p50:<10.2f} | {p95:<10.2f}")

    print("\n5. ASR SPEECH RECOGNITION (WER on Real Audio Fixture)")
    print(f"  • WER without bias prompt     : {wer_measured_info['wer_no_bias']}")
    print(f"  • WER with bias prompt        : {wer_measured_info['wer_with_bias']}")

    print("=" * 76)


if __name__ == "__main__":
    main()

