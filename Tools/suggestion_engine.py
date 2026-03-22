# Tools/suggestion_engine.py

import logging
from Configs.settings import TARGET_SERVICE

logger = logging.getLogger(__name__)

# Fix suggestion mapping per root cause
SUGGESTION_MAP = {
    "downstream_dependency": [
        "Check the health and resource usage of the culprit service.",
        "Review recent deployments or config changes in the culprit service.",
        "Inspect culprit service logs for errors or slow queries.",
        "Consider adding a cache layer for frequent downstream calls.",
        "Evaluate circuit breaker or timeout policies for the downstream call.",
        "Scale up the culprit service if it is under resource pressure.",
    ],
    "resource_pressure": [
        f"Scale up the '{TARGET_SERVICE}' deployment replicas.",
        f"Review resource limits and requests for '{TARGET_SERVICE}' pod.",
        "Check for memory leaks or inefficient loops in the service code.",
        "Enable horizontal pod autoscaling (HPA) for the service.",
        "Review GC activity if the service is JVM or Python based.",
    ],
    "traffic_spike": [
        "Enable or review Horizontal Pod Autoscaler (HPA) configuration.",
        "Check if the traffic spike is expected (e.g. campaign, batch job).",
        "Review rate limiting policies at the ingress/gateway level.",
        "Consider pre-warming replicas during known high-traffic periods.",
        "Check load balancer distribution across service replicas.",
    ],
    "cascade_failure": [
        "Identify the first failing service in the call chain.",
        "Check recent deployments across all affected services.",
        "Review inter-service timeout and retry configurations.",
        "Enable circuit breakers to prevent cascade propagation.",
        "Check shared infrastructure (DB, cache, message broker) health.",
        "Review distributed tracing for the first error span.",
    ],
    "internal_slowness": [
        f"Profile '{TARGET_SERVICE}' for CPU or memory bottlenecks.",
        "Review recent code changes or dependency updates.",
        "Check for N+1 query patterns or inefficient data processing.",
        "Review garbage collection logs if applicable.",
        "Add more detailed instrumentation to isolate the slow code path.",
    ],
}


def get_suggestions(rca_result: dict) -> dict:
    """
    Map RCA result to actionable fix suggestions.
    Returns enriched result with suggestions added.
    """
    root_cause = rca_result.get("root_cause", "internal_slowness")
    culprit    = rca_result.get("culprit", TARGET_SERVICE)

    suggestions = SUGGESTION_MAP.get(
        root_cause,
        SUGGESTION_MAP["internal_slowness"]
    )

    # Personalise top suggestion with culprit name
    if root_cause == "downstream_dependency" and culprit:
        suggestions = [
            f"Investigate '{culprit}' service immediately — "
            f"it is the identified bottleneck."
        ] + suggestions

    enriched = {
        **rca_result,
        "suggestions": suggestions,
        "priority":    _get_priority(root_cause),
        "action":      _get_action(root_cause, culprit),
    }

    logger.info(
        "Suggestions generated for root_cause='%s', culprit='%s', "
        "priority='%s'",
        root_cause, culprit, enriched["priority"]
    )

    return enriched


def _get_priority(root_cause: str) -> str:
    """Return incident priority based on root cause."""
    priority_map = {
        "cascade_failure":       "P1 — Critical",
        "resource_pressure":     "P2 — High",
        "downstream_dependency": "P2 — High",
        "traffic_spike":         "P3 — Medium",
        "internal_slowness":     "P3 — Medium",
    }
    return priority_map.get(root_cause, "P3 — Medium")


def _get_action(root_cause: str, culprit: str) -> str:
    """Return one-line immediate action."""
    action_map = {
        "cascade_failure":       "Immediately check all failing services and shared infrastructure.",
        "resource_pressure":     f"Scale up '{culprit}' or increase resource limits now.",
        "downstream_dependency": f"Investigate and restart '{culprit}' if unresponsive.",
        "traffic_spike":         "Activate autoscaling and review rate limiting policies.",
        "internal_slowness":     f"Profile '{culprit}' service for performance bottlenecks.",
    }
    return action_map.get(root_cause, "Investigate the service manually.")