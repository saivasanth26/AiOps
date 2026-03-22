# LLM/explainer.py

import logging
import requests

logger = logging.getLogger(__name__)

OLLAMA_URL    = "http://localhost:11434/api/generate"
OLLAMA_MODEL  = "mistral"


def _build_prompt(
    metrics:     dict,
    rca_result:  dict,
    suggestions: list[str],
    analysis:    dict,
) -> str:
    """
    Build a structured prompt for the LLM.
    All facts come from deterministic sources — LLM only explains.
    """
    downstream = rca_result.get("downstream_span", {})
    services   = analysis.get("services_in_trace", [])

    prompt = f"""You are an SRE incident reporter. Based on the structured data below,
write a clear, concise incident summary. Do not invent any information.
Only use the data provided. Keep the summary under 150 words.

=== INCIDENT DATA ===

Service Monitored : {rca_result.get('culprit', 'unknown')}
Root Cause        : {rca_result.get('root_cause', 'unknown')}
Confidence        : {rca_result.get('confidence', 'unknown')}
Priority          : {rca_result.get('priority', 'unknown')}

Metrics at time of anomaly:
  - P95 Latency : {metrics.get('p95_latency_ms', 'N/A')} ms
  - CPU Usage   : {metrics.get('cpu_usage', 'N/A')}
  - RPS         : {metrics.get('rps', 'N/A')} req/s

Trace Analysis:
  - Services in trace : {', '.join(services)}
  - Target max span   : {analysis.get('target_max_ms', 'N/A')} ms
  - Downstream max    : {analysis.get('downstream_max_ms', 'N/A')} ms
  {f"- Culprit span      : {downstream.get('operation', '')} ({downstream.get('duration_ms', '')} ms)" if downstream else ''}

RCA Description:
{rca_result.get('description', '')}

Top Fix Suggestions:
{chr(10).join(f'  {i+1}. {s}' for i, s in enumerate(suggestions[:3]))}

=== END OF DATA ===

Write the incident summary now:"""

    return prompt


def generate_explanation(
    metrics:    dict,
    rca_result: dict,
    analysis:   dict,
) -> str:
    """
    Call Ollama Mistral with structured incident context.
    Returns LLM-generated explanation string.
    Falls back to structured summary if Ollama is unavailable.
    """
    suggestions = rca_result.get("suggestions", [])
    prompt      = _build_prompt(metrics, rca_result, suggestions, analysis)

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 200,
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        data        = response.json()
        explanation = data.get("response", "").strip()

        if explanation:
            logger.info("LLM explanation generated successfully")
            return explanation

        logger.warning("LLM returned empty response — using fallback")
        return _fallback_explanation(metrics, rca_result)

    except requests.exceptions.ConnectionError:
        logger.error("Ollama not reachable at %s — using fallback", OLLAMA_URL)
        return _fallback_explanation(metrics, rca_result)
    except requests.exceptions.Timeout:
        logger.error("Ollama request timed out — using fallback")
        return _fallback_explanation(metrics, rca_result)
    except Exception as e:
        logger.error("Unexpected error calling Ollama: %s — using fallback", e)
        return _fallback_explanation(metrics, rca_result)


def _fallback_explanation(metrics: dict, rca_result: dict) -> str:
    """
    Structured fallback when LLM is unavailable.
    Produces a clean readable summary from structured data alone.
    """
    return (
        f"INCIDENT SUMMARY\n"
        f"Root Cause : {rca_result.get('root_cause', 'unknown')}\n"
        f"Culprit    : {rca_result.get('culprit', 'unknown')}\n"
        f"Priority   : {rca_result.get('priority', 'unknown')}\n"
        f"P95 Latency: {metrics.get('p95_latency_ms', 'N/A')} ms\n"
        f"CPU Usage  : {metrics.get('cpu_usage', 'N/A')}\n"
        f"RPS        : {metrics.get('rps', 'N/A')} req/s\n"
        f"Details    : {rca_result.get('description', 'N/A')}"
    )