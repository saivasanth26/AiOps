# Tools/trace_analyzer.py

import logging
import requests
from Configs.settings import JAEGER_URL, TARGET_SERVICE

logger = logging.getLogger(__name__)

TRACES_ENDPOINT = f"{JAEGER_URL}/api/traces"


def fetch_traces(limit: int = 5) -> list[dict]:
    """
    Fetch recent traces for the target service from Jaeger.
    Returns list of trace dicts or empty list on failure.
    """
    try:
        response = requests.get(
            TRACES_ENDPOINT,
            params={
                "service": TARGET_SERVICE,
                "limit":   limit,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        traces = data.get("data", [])
        logger.info("Fetched %d traces for service '%s'", len(traces), TARGET_SERVICE)
        return traces

    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to Jaeger at %s", JAEGER_URL)
        return []
    except requests.exceptions.Timeout:
        logger.error("Jaeger request timed out")
        return []
    except requests.exceptions.HTTPError as e:
        logger.error("Jaeger HTTP error: %s", e)
        return []
    except (KeyError, ValueError) as e:
        logger.error("Failed to parse Jaeger response: %s", e)
        return []


def parse_spans(trace: dict) -> list[dict]:
    """
    Parse spans from a trace and enrich with service name.
    Returns list of span dicts with service_name, operation,
    duration_us, span_id, parent_span_id.
    """
    processes = trace.get("processes", {})
    spans     = trace.get("spans", [])
    parsed    = []

    for span in spans:
        pid          = span.get("processID", "")
        service_name = processes.get(pid, {}).get("serviceName", "unknown")
        references   = span.get("references", [])
        parent_id    = None

        for ref in references:
            if ref.get("refType") == "CHILD_OF":
                parent_id = ref.get("spanID")
                break

        parsed.append({
            "span_id":        span["spanID"],
            "parent_span_id": parent_id,
            "operation":      span["operationName"],
            "service_name":   service_name,
            "duration_us":    span["duration"],
            "duration_ms":    round(span["duration"] / 1000, 3),
        })

    return parsed


def get_slowest_span(spans: list[dict]) -> dict | None:
    """
    Return the single slowest span from the list.
    """
    if not spans:
        return None
    return max(spans, key=lambda s: s["duration_us"])


def get_service_spans(spans: list[dict], service_name: str) -> list[dict]:
    """
    Filter spans by service name.
    """
    return [s for s in spans if s["service_name"] == service_name]


def get_downstream_spans(spans: list[dict]) -> list[dict]:
    """
    Return spans from services other than the target service.
    These represent downstream dependency calls.
    """
    return [s for s in spans if s["service_name"] != TARGET_SERVICE]


def analyze_trace(trace: dict) -> dict:
    """
    Analyze a single trace and return structured analysis:
    - all spans enriched with service names
    - slowest span
    - target service spans
    - downstream spans
    - max downstream duration
    - target service internal duration
    """
    spans              = parse_spans(trace)
    slowest            = get_slowest_span(spans)
    target_spans       = get_service_spans(spans, TARGET_SERVICE)
    downstream_spans   = get_downstream_spans(spans)

    target_max_ms = max(
        (s["duration_ms"] for s in target_spans), default=0.0
    )
    downstream_max_ms = max(
        (s["duration_ms"] for s in downstream_spans), default=0.0
    )
    slowest_downstream = (
        max(downstream_spans, key=lambda s: s["duration_us"])
        if downstream_spans else None
    )

    return {
        "trace_id":             trace["traceID"],
        "total_spans":          len(spans),
        "all_spans":            spans,
        "slowest_span":         slowest,
        "target_spans":         target_spans,
        "downstream_spans":     downstream_spans,
        "slowest_downstream":   slowest_downstream,
        "target_max_ms":        target_max_ms,
        "downstream_max_ms":    downstream_max_ms,
        "services_in_trace":    list({s["service_name"] for s in spans}),
    }


def get_trace_analysis() -> dict | None:
    """
    Main entry point — fetch latest traces and return
    analysis of the most recent one.
    Returns None if no traces available.
    """
    traces = fetch_traces(limit=5)
    if not traces:
        logger.warning("No traces available for analysis")
        return None

    # Analyze the most recent trace
    analysis = analyze_trace(traces[0])

    logger.info(
        "Trace analysis — trace_id: %s, spans: %d, "
        "target_max_ms: %.3f, downstream_max_ms: %.3f, "
        "services: %s",
        analysis["trace_id"],
        analysis["total_spans"],
        analysis["target_max_ms"],
        analysis["downstream_max_ms"],
        analysis["services_in_trace"],
    )

    return analysis