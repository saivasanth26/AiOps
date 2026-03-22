# RCA/rule_engine.py

import logging
from Tools.metrics_fetcher import query_prometheus
from Configs.settings import (
    TARGET_SERVICE,
    CPU_QUERY,
    RPS_QUERY,
)

logger = logging.getLogger(__name__)

# CPU threshold for resource pressure rule
CPU_PRESSURE_THRESHOLD = 0.80

# Multiplier for traffic spike detection
RPS_SPIKE_MULTIPLIER = 2.0

# Known downstream dependency
DOWNSTREAM_SERVICE = "product-catalog"
DOWNSTREAM_OPERATION = "/oteldemo.ProductCatalogService/ListProducts"

# Known upstream callers to exclude from downstream analysis
UPSTREAM_SERVICES = {"load-generator", "frontend", "frontend-proxy", "frontend-web"}


def _get_downstream_service_spans(analysis: dict) -> list[dict]:
    """
    Filter spans to only actual downstream dependency calls.
    Excludes upstream callers (load-generator, frontend, etc.)
    and the target service itself.
    """
    return [
        s for s in analysis["all_spans"]
        if s["service_name"] not in UPSTREAM_SERVICES
        and s["service_name"] != TARGET_SERVICE
    ]


def _get_target_server_span(analysis: dict) -> dict | None:
    """
    Get the main server span for the target service.
    This is the span where recommendation receives the request.
    """
    target_spans = analysis.get("target_spans", [])
    server_spans = [
        s for s in target_spans
        if "ListRecommendations" in s["operation"]
        or "RecommendationService" in s["operation"]
    ]
    if server_spans:
        return max(server_spans, key=lambda s: s["duration_us"])
    return max(target_spans, key=lambda s: s["duration_us"]) if target_spans else None


def _check_cascade_failure(analysis: dict) -> dict | None:
    """
    Rule 1 — Cascade failure.
    Multiple services with errors in the trace.
    """
    error_services = set()
    for span in analysis["all_spans"]:
        if span["service_name"] in UPSTREAM_SERVICES:
            continue
        tags = {}
        if "error" in str(span).lower():
            error_services.add(span["service_name"])

    if len(error_services) >= 2:
        first_error = list(error_services)[0]
        return {
            "root_cause":   "cascade_failure",
            "culprit":      first_error,
            "confidence":   "high",
            "description":  (
                f"Multiple services showing errors: {error_services}. "
                f"First detected in: {first_error}."
            ),
        }
    return None


def _check_resource_pressure(metrics: dict) -> dict | None:
    """
    Rule 2 — CPU resource pressure.
    High CPU with elevated latency.
    """
    cpu = metrics.get("cpu_usage", 0.0)
    if cpu >= CPU_PRESSURE_THRESHOLD:
        return {
            "root_cause":  "resource_pressure",
            "culprit":     TARGET_SERVICE,
            "confidence":  "high",
            "description": (
                f"CPU usage at {cpu:.1%} exceeds threshold of "
                f"{CPU_PRESSURE_THRESHOLD:.0%}. "
                f"Service is under resource pressure."
            ),
        }
    return None


def _check_traffic_spike(metrics: dict, baseline_rps: float) -> dict | None:
    """
    Rule 3 — Traffic spike.
    RPS significantly above baseline.
    """
    current_rps = metrics.get("rps", 0.0)
    if baseline_rps > 0 and current_rps >= baseline_rps * RPS_SPIKE_MULTIPLIER:
        return {
            "root_cause":  "traffic_spike",
            "culprit":     "load_pattern",
            "confidence":  "medium",
            "description": (
                f"Request rate spiked to {current_rps:.3f} RPS — "
                f"{current_rps / baseline_rps:.1f}x above baseline "
                f"of {baseline_rps:.3f} RPS."
            ),
        }
    return None


def _check_downstream_dependency(analysis: dict) -> dict | None:
    """
    Rule 4 — Downstream dependency slowness.
    A downstream service span is slower than the target's internal processing.
    """
    downstream_spans = _get_downstream_service_spans(analysis)
    target_span      = _get_target_server_span(analysis)

    if not downstream_spans or not target_span:
        return None

    slowest_downstream = max(downstream_spans, key=lambda s: s["duration_us"])
    target_duration_ms = target_span["duration_ms"]

    if slowest_downstream["duration_ms"] > target_duration_ms * 0.5:
        return {
            "root_cause":  "downstream_dependency",
            "culprit":     slowest_downstream["service_name"],
            "confidence":  "high",
            "description": (
                f"Downstream service '{slowest_downstream['service_name']}' "
                f"took {slowest_downstream['duration_ms']:.3f}ms "
                f"(operation: {slowest_downstream['operation']}) vs "
                f"'{TARGET_SERVICE}' internal duration of "
                f"{target_duration_ms:.3f}ms. "
                f"Downstream call is the bottleneck."
            ),
            "downstream_span": slowest_downstream,
        }
    return None


def _default_internal_slowness(metrics: dict, analysis: dict) -> dict:
    """
    Rule 5 — Default: internal service slowness.
    Falls through when no other rule matches.
    """
    target_span = _get_target_server_span(analysis)
    duration_ms = target_span["duration_ms"] if target_span else 0.0

    return {
        "root_cause":  "internal_slowness",
        "culprit":     TARGET_SERVICE,
        "confidence":  "low",
        "description": (
            f"No clear external cause identified. "
            f"'{TARGET_SERVICE}' internal processing took "
            f"{duration_ms:.3f}ms. "
            f"Possible causes: inefficient logic, memory pressure, "
            f"or GC pauses."
        ),
    }


def run_rca(
    metrics: dict,
    analysis: dict,
    baseline_rps: float = 0.0,
) -> dict:
    """
    Run all RCA rules in priority order and return the first match.

    Priority:
    1. Cascade failure  (errors across services)
    2. Resource pressure (CPU > 80%)
    3. Traffic spike    (RPS > 2x baseline)
    4. Downstream dependency (downstream slower than internal)
    5. Internal slowness (default)
    """
    logger.info("Running RCA rules...")

    # Rule 1 — Cascade failure
    result = _check_cascade_failure(analysis)
    if result:
        logger.warning("RCA Rule 1 matched: cascade_failure")
        return result

    # Rule 2 — Resource pressure
    result = _check_resource_pressure(metrics)
    if result:
        logger.warning("RCA Rule 2 matched: resource_pressure")
        return result

    # Rule 3 — Traffic spike
    result = _check_traffic_spike(metrics, baseline_rps)
    if result:
        logger.warning("RCA Rule 3 matched: traffic_spike")
        return result

    # Rule 4 — Downstream dependency
    result = _check_downstream_dependency(analysis)
    if result:
        logger.warning("RCA Rule 4 matched: downstream_dependency")
        return result

    # Rule 5 — Default
    logger.info("RCA Rule 5 matched: internal_slowness (default)")
    return _default_internal_slowness(metrics, analysis)