# agent.py

import os
import sys
import time
import logging
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Configs.settings import (
    BASELINE_SAMPLES,
    COLLECTION_INTERVAL,
    MONITORING_INTERVAL,
    MODEL_PATH,
    SCALER_PATH,
)
from Tools.metrics_fetcher  import get_metrics, get_feature_vector
from Models.anomaly_detector import AnomalyDetector
from Tools.trace_analyzer   import get_trace_analysis
from RCA.rule_engine        import run_rca
from Tools.suggestion_engine import get_suggestions
from LLM.explainer          import generate_explanation

# ──────────────────────────────────────────
# Logging
# ──────────────────────────────────────────
logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt= "%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("agent")


# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────
def print_banner() -> None:
    print("""
╔══════════════════════════════════════════════════════════╗
║           AIOps Observability Agent  v0.1.0              ║
║   Anomaly Detection · RCA · LLM Explanation              ║
╚══════════════════════════════════════════════════════════╝
    """)


def print_incident_report(
    metrics:     dict,
    rca_result:  dict,
    explanation: str,
) -> None:
    sep = "═" * 60
    print(f"\n{sep}")
    print("  🚨  ANOMALY DETECTED — INCIDENT REPORT")
    print(sep)
    print(f"  Root Cause  : {rca_result.get('root_cause')}")
    print(f"  Culprit     : {rca_result.get('culprit')}")
    print(f"  Priority    : {rca_result.get('priority')}")
    print(f"  Confidence  : {rca_result.get('confidence')}")
    print(f"  Action      : {rca_result.get('action')}")
    print(f"\n  Metrics at detection:")
    print(f"    P95 Latency : {metrics.get('p95_latency_ms')} ms")
    print(f"    CPU Usage   : {metrics.get('cpu_usage')}")
    print(f"    RPS         : {metrics.get('rps')} req/s")
    print(f"\n  Suggestions:")
    for i, s in enumerate(rca_result.get("suggestions", [])[:5], 1):
        print(f"    {i}. {s}")
    print(f"\n  LLM Explanation:")
    print(f"  {explanation}")
    print(f"{sep}\n")


# ──────────────────────────────────────────
# Phase 1 — Baseline Collection
# ──────────────────────────────────────────
def collect_baseline(detector: AnomalyDetector) -> float:
    """
    Collect baseline samples and train the Isolation Forest.
    Returns the average RPS observed during baseline (used for
    traffic spike detection in RCA).
    """
    logger.info(
        "Starting baseline collection — %d samples × %ds intervals",
        BASELINE_SAMPLES, COLLECTION_INTERVAL
    )
    print(f"\n[BASELINE] Collecting {BASELINE_SAMPLES} samples "
          f"({BASELINE_SAMPLES * COLLECTION_INTERVAL}s)...\n")

    baseline_data = []
    rps_values    = []
    failures      = 0

    for i in range(1, BASELINE_SAMPLES + 1):
        metrics = get_metrics()

        if metrics is None:
            failures += 1
            logger.warning("Sample %d/%d failed — skipping", i, BASELINE_SAMPLES)
            if failures >= 5:
                logger.error("Too many consecutive failures during baseline")
                sys.exit(1)
            time.sleep(COLLECTION_INTERVAL)
            continue

        failures = 0
        vector   = get_feature_vector(metrics)
        baseline_data.append(vector)
        rps_values.append(metrics["rps"])

        print(
            f"  [{i:02d}/{BASELINE_SAMPLES}] "
            f"p95={metrics['p95_latency_ms']:.4f}ms  "
            f"cpu={metrics['cpu_usage']:.6f}  "
            f"rps={metrics['rps']:.4f}"
        )
        time.sleep(COLLECTION_INTERVAL)

    if len(baseline_data) < 5:
        logger.error("Insufficient baseline samples collected (%d). Exiting.", len(baseline_data))
        sys.exit(1)

    logger.info("Training model on %d samples...", len(baseline_data))
    detector.train(baseline_data)

    baseline_rps = float(np.mean(rps_values)) if rps_values else 0.0
    logger.info("Baseline RPS: %.4f", baseline_rps)
    print(f"\n[BASELINE] Model trained. Baseline RPS = {baseline_rps:.4f}\n")

    return baseline_rps


# ──────────────────────────────────────────
# Phase 2 — Monitoring Loop
# ──────────────────────────────────────────
def monitoring_loop(
    detector:     AnomalyDetector,
    baseline_rps: float,
) -> None:
    """
    Continuous monitoring loop.
    On anomaly: fetch traces → RCA → suggestions → LLM → print report.
    """
    logger.info("Entering monitoring loop — interval: %ds", MONITORING_INTERVAL)
    print("[MONITOR] Watching for anomalies...\n")

    cycle = 0

    while True:
        cycle += 1
        metrics = get_metrics()

        if metrics is None:
            logger.warning("Cycle %d — failed to fetch metrics, skipping", cycle)
            time.sleep(MONITORING_INTERVAL)
            continue

        vector = get_feature_vector(metrics)
        result = detector.predict(vector)

        print(
            f"  [cycle {cycle:04d}] "
            f"p95={metrics['p95_latency_ms']:.4f}ms  "
            f"cpu={metrics['cpu_usage']:.6f}  "
            f"rps={metrics['rps']:.4f}  "
            f"score={result['anomaly_score']:.4f}  "
            f"{'🚨 ANOMALY' if result['is_anomaly'] else '✓ normal'}"
        )

        if result["is_anomaly"]:
            logger.warning(
                "Anomaly detected — score: %.6f — triggering RCA pipeline",
                result["anomaly_score"]
            )

            # Fetch traces
            analysis = get_trace_analysis()
            if analysis is None:
                logger.error("No trace data available — skipping RCA")
                time.sleep(MONITORING_INTERVAL)
                continue

            # RCA
            rca = run_rca(metrics, analysis, baseline_rps=baseline_rps)

            # Suggestions
            rca_with_suggestions = get_suggestions(rca)

            # LLM explanation
            explanation = generate_explanation(
                metrics, rca_with_suggestions, analysis
            )

            # Print incident report
            print_incident_report(metrics, rca_with_suggestions, explanation)

        time.sleep(MONITORING_INTERVAL)


# ──────────────────────────────────────────
# Main
# ──────────────────────────────────────────
def main() -> None:
    print_banner()
    detector = AnomalyDetector()

    # Try loading saved model first
    if detector.load():
        logger.info("Loaded saved model — skipping baseline collection")
        print("[AGENT] Saved model found — skipping baseline collection")
        print("[AGENT] Using default baseline RPS = 0.05\n")
        baseline_rps = 0.05
    else:
        baseline_rps = collect_baseline(detector)

    monitoring_loop(detector, baseline_rps)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[AGENT] Stopped by user.")
        logger.info("Agent stopped by user")