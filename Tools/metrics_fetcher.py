# tools/metrics_fetcher.py

import logging
import requests
from Configs.settings import (
    PROMETHEUS_URL,
    P95_QUERY,
    CPU_QUERY,
    RPS_QUERY,
)

logger = logging.getLogger(__name__)


def query_prometheus(query: str) -> float | None:
    """
    Execute a PromQL query and return a single float value.
    Returns None if query fails or result is empty.
    """
    try:
        response = requests.get(
            PROMETHEUS_URL,
            params={"query": query},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("data", {}).get("result", [])
        if not results:
            logger.warning("Empty result for query: %s", query)
            return None

        value = float(results[0]["value"][1])
        return value

    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to Prometheus at %s", PROMETHEUS_URL)
        return None
    except requests.exceptions.Timeout:
        logger.error("Prometheus query timed out")
        return None
    except requests.exceptions.HTTPError as e:
        logger.error("Prometheus HTTP error: %s", e)
        return None
    except (KeyError, IndexError, ValueError) as e:
        logger.error("Failed to parse Prometheus response: %s", e)
        return None


def get_metrics() -> dict | None:
    p95 = query_prometheus(P95_QUERY)
    cpu = query_prometheus(CPU_QUERY)
    rps = query_prometheus(RPS_QUERY)

    if p95 is None or rps is None:
        logger.warning(
            "Missing critical metrics — p95: %s, rps: %s", p95, rps
        )
        return None

    # Skip sample if CPU is missing to avoid false anomalies
    if cpu is None:
        logger.warning("CPU metric unavailable — skipping sample")
        return None

    metrics = {
        "p95_latency_ms": round(p95, 4),
        "cpu_usage":      round(cpu, 6),
        "rps":            round(rps, 4),
    }

    logger.info("Metrics fetched: %s", metrics)
    return metrics


def get_feature_vector(metrics: dict) -> list[float]:
    """
    Convert metrics dict to ordered feature vector for the model.
    Order must always match training: [p95, cpu, rps]
    """
    return [
        metrics["p95_latency_ms"],
        metrics["cpu_usage"],
        metrics["rps"],
    ]