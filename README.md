# AIOps Observability System

> An intelligent observability agent that automatically detects anomalies in Kubernetes microservices, performs root cause analysis using distributed traces, and generates human-readable incident reports — without manual intervention.

![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)
![Kubernetes](https://img.shields.io/badge/Kubernetes-1.31-326CE5?style=flat-square&logo=kubernetes)
![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-2.2.0-black?style=flat-square)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.4.2-orange?style=flat-square)

---

## Table of Contents

- [Overview](#overview)
- [Core Philosophy](#core-philosophy)
- [System Architecture](#system-architecture)
- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Module Reference](#module-reference)
- [RCA Rule Engine](#rca-rule-engine)
- [Infrastructure Setup](#infrastructure-setup)
- [Quick Start](#quick-start)
- [Tech Stack](#tech-stack)
- [Key Design Decisions](#key-design-decisions)

---

## Overview

Modern cloud-native applications run as collections of microservices. When something goes wrong, engineers must manually correlate metrics, logs, and traces across dozens of services to find the root cause — a slow, error-prone process.

This project automates that entire workflow:

1. **Continuously monitors** the recommendation service using real-time metrics from Prometheus
2. **Detects anomalies early** using Isolation Forest — a statistical ML model trained on baseline behavior
3. **Automatically identifies root cause** by analyzing distributed traces from Jaeger
4. **Generates fix suggestions** using deterministic rule-based logic
5. **Explains the incident** in plain English using a local LLM (Ollama/Mistral)

The system mirrors how a skilled SRE would investigate an incident — automatically, consistently, and with full auditability.

---

## Core Philosophy

The system is built around four strict responsibilities:

| Signal | Role | Why |
|---|---|---|
| **Metrics** | Detection | Quantitative, fast, always available |
| **Traces** | Reasoning | Shows causality across services |
| **Rules** | Correctness | Deterministic, auditable, no hallucination |
| **LLM** | Explanation | Communication only — never decision-making |

The LLM is strictly limited to formatting output. It never drives detection, RCA, or fix decisions. This prevents hallucination from affecting incident response.

---

## System Architecture
```
## System Architecture
```
╔══════════════════════════════════════════════════════════════╗
║                  LAYER 1 — INSTRUMENTATION                   ║
║                                                              ║
║   OTel Demo App (Kubernetes · 2 nodes · 28 services)         ║
║          ↓ OTLP gRPC                                         ║
║   OTel Collector                                             ║
║     ├── metrics ──→ Prometheus  :9090                        ║
║     └── traces  ──→ Jaeger v1.52 :16686                      ║
╚══════════════════════════════════════════════════════════════╝
                          │
                          ▼
╔══════════════════════════════════════════════════════════════╗
║                   LAYER 2 — DETECTION                        ║
║                                                              ║
║   metrics_fetcher.py                                         ║
║     ├── p95 latency  →  traces_span_metrics [5m]             ║
║     ├── cpu usage    →  container_cpu_usage [5m]             ║
║     └── rps          →  traces_span_metrics_count [5m]       ║
║                          ↓                                   ║
║   feature vector    →  [p95, cpu, rps]                       ║
║                          ↓                                   ║
║   StandardScaler    →  normalize                             ║
║                          ↓                                   ║
║   Isolation Forest  →  predict()                             ║
║                          ↓                                   ║
║          prediction == -1  →  ANOMALY DETECTED               ║
╚══════════════════════════════════════════════════════════════╝
                          │
                          ▼
╔══════════════════════════════════════════════════════════════╗
║                   LAYER 3 — REASONING                        ║
║                                                              ║
║   trace_analyzer.py                                          ║
║     ├── fetch latest traces from Jaeger                      ║
║     ├── parse spans → enrich with service names              ║
║     └── separate target spans from downstream spans          ║
║                          ↓                                   ║
║   rule_engine.py  (priority order)                           ║
║     ├── Rule 1 → cascade failure   (errors across services)  ║
║     ├── Rule 2 → resource pressure (CPU > 80%)               ║
║     ├── Rule 3 → traffic spike     (RPS > 2x baseline)       ║
║     ├── Rule 4 → downstream dep.   (downstream > internal)   ║
║     └── Rule 5 → internal slowness (default)                 ║
║                          ↓                                   ║
║   suggestion_engine.py                                       ║
║     └── root cause → fix suggestions + priority (P1–P3)      ║
╚══════════════════════════════════════════════════════════════╝
                          │
                          ▼
╔══════════════════════════════════════════════════════════════╗
║                  LAYER 4 — EXPLANATION                       ║
║                                                              ║
║   explainer.py                                               ║
║     ├── structured context → Ollama (Mistral)                ║
║     ├── LLM generates human-readable incident report         ║
║     └── LLM makes ZERO decisions — explanation only          ║
║                          ↓                                   ║
║   INCIDENT REPORT                                            ║
║     ├── root_cause   : downstream_dependency                 ║
║     ├── culprit      : product-catalog                       ║
║     ├── priority     : P2 — High                             ║
║     ├── suggestions  : [actionable fix list]                 ║
║     └── explanation  : LLM generated summary                 ║
╚══════════════════════════════════════════════════════════════╝
```

## How It Works

### Phase 1 — Baseline Collection

When the agent starts for the first time, it collects `BASELINE_SAMPLES` (default: 20) metric snapshots at `COLLECTION_INTERVAL` (default: 10s) intervals during normal operation. These samples form the training dataset for the Isolation Forest model.

Each sample is a feature vector: `[p95_latency_ms, cpu_usage, rps]`

The model and scaler are saved to disk after training so the agent does not need to retrain on every restart.

### Phase 2 — Continuous Monitoring

After training, the agent enters a monitoring loop. Every `MONITORING_INTERVAL` seconds it:

1. Fetches current metrics from Prometheus
2. Scales the feature vector using the saved StandardScaler
3. Runs Isolation Forest prediction
4. If `prediction == -1` → anomaly detected → triggers the agent pipeline

### Phase 3 — Root Cause Analysis

On anomaly detection:

1. Fetches the 5 most recent traces for the `recommendation` service from Jaeger
2. Parses all spans, enriches each with its service name from the process map
3. Separates target service spans from downstream dependency spans
4. Runs 5 deterministic RCA rules in priority order

### Phase 4 — Explanation

The structured RCA output (root cause, culprit, metrics, trace data, suggestions) is passed as context to a local LLM via Ollama. The LLM formats this into a readable incident report. It adds no new information — it only explains what the rule engine already determined.

---

## Project Structure
```
AiOps/
├── Configs/
│   └── settings.py           # All config — URLs, queries, model params
├── Tools/
│   ├── metrics_fetcher.py    # Prometheus query execution
│   ├── trace_analyzer.py     # Jaeger trace fetching and span parsing
│   └── suggestion_engine.py  # Root cause → fix suggestion mapping
├── Models/
│   └── anomaly_detector.py   # Isolation Forest train, predict, persist
├── RCA/
│   └── rule_engine.py        # 5 deterministic RCA rules
├── LLM/
│   └── explainer.py          # Ollama/Mistral explanation layer
├── data/
│   └── baseline/
│       ├── baseline.npy      # Saved baseline samples
│       ├── model.pkl         # Trained Isolation Forest
│       └── scaler.pkl        # Fitted StandardScaler
├── agent.py                  # Main orchestrator
└── requirements.txt
```

---

## Module Reference

### `Configs/settings.py`

Single source of truth for all configuration. Change `TARGET_SERVICE` here to monitor a different service.

Key settings:

| Variable | Default | Description |
|---|---|---|
| `PROMETHEUS_URL` | `http://10.96.167.218:9090/api/v1/query` | Prometheus API endpoint |
| `JAEGER_URL` | `http://10.111.148.212:16686` | Jaeger query API (v1.52 pod) |
| `TARGET_SERVICE` | `recommendation` | Service to monitor |
| `BASELINE_SAMPLES` | `20` | Number of baseline samples to collect |
| `COLLECTION_INTERVAL` | `10` | Seconds between baseline samples |
| `MONITORING_INTERVAL` | `10` | Seconds between monitor cycles |
| `CONTAMINATION` | `0.1` | Isolation Forest contamination factor |

---

### `Tools/metrics_fetcher.py`

Queries Prometheus and returns a feature vector for the anomaly detector.

**Three metrics collected:**

| Metric | PromQL | Purpose |
|---|---|---|
| P95 Latency | `histogram_quantile(0.95, traces_span_metrics_duration_milliseconds_bucket{service_name="recommendation", span_kind="SPAN_KIND_SERVER"}[5m])` | Primary user impact signal |
| CPU Usage | `sum(rate(container_cpu_usage_seconds_total{namespace="otel-demo", pod=~"recommendation.*"}[5m]))` | Resource pressure signal |
| RPS | `sum(rate(traces_span_metrics_duration_milliseconds_count{service_name="recommendation", span_kind="SPAN_KIND_SERVER"}[5m]))` | Traffic context |

**Key functions:**
- `query_prometheus(query)` → executes a single PromQL query, returns float or None
- `get_metrics()` → fetches all three metrics, returns dict
- `get_feature_vector(metrics)` → converts dict to `[p95, cpu, rps]` list

---

### `Models/anomaly_detector.py`

Wraps scikit-learn Isolation Forest with training, prediction, and persistence.

**Why Isolation Forest:**
- Learns "normal" from baseline data — no manual threshold setting
- Handles multi-dimensional anomalies
- Efficient on small feature sets
- Contamination parameter controls sensitivity

**Key methods:**
- `train(baseline_data)` → fits scaler + model, saves to disk
- `predict(feature_vector)` → returns `{is_anomaly, anomaly_score, prediction}`
- `load()` → loads saved model from disk, returns True/False

---

### `Tools/trace_analyzer.py`

Fetches distributed traces from Jaeger and parses span data.

**Why we deployed Jaeger v1.52 separately:**
Jaeger v2.x (used in OTel demo) removed the REST API in favour of gRPC. We deployed a separate Jaeger v1.52 pod and configured the OTel collector to send traces to both instances, preserving the REST API for our agent.

**Key functions:**
- `fetch_traces(limit)` → returns list of raw trace dicts from Jaeger
- `parse_spans(trace)` → enriches spans with service names from process map
- `get_slowest_span(spans)` → returns the single slowest span
- `get_downstream_spans(spans)` → filters out upstream callers
- `analyze_trace(trace)` → returns full structured analysis
- `get_trace_analysis()` → main entry point, returns analysis of most recent trace

**Discovered trace structure (recommendation service):**
```
load-generator → frontend → frontend-proxy
                                  ↓
                          recommendation (SPAN_KIND_SERVER)
                                  ↓
                          product-catalog (SPAN_KIND_CLIENT)
                                  ↓
                          flagd (feature flags)
```

---

### `RCA/rule_engine.py`

Applies five deterministic rules in priority order. First matching rule wins.

**Upstream services excluded from downstream analysis:**
`load-generator`, `frontend`, `frontend-proxy`, `frontend-web`

---

### `Tools/suggestion_engine.py`

Maps each root cause to a prioritised list of fixes.

**Priority assignment:**

| Root Cause | Priority |
|---|---|
| cascade_failure | P1 — Critical |
| resource_pressure | P2 — High |
| downstream_dependency | P2 — High |
| traffic_spike | P3 — Medium |
| internal_slowness | P3 — Medium |

---

## RCA Rule Engine

Rules are applied in strict priority order. The first matching rule determines the root cause.

### Rule 1 — Cascade Failure
```
IF errors detected across 2+ services in the trace
THEN root_cause = "cascade_failure"
     culprit    = first service with errors
```

### Rule 2 — Resource Pressure
```
IF cpu_usage > 0.80
THEN root_cause = "resource_pressure"
     culprit    = TARGET_SERVICE
```

### Rule 3 — Traffic Spike
```
IF current_rps > baseline_rps * 2.0
THEN root_cause = "traffic_spike"
     culprit    = "load_pattern"
```

### Rule 4 — Downstream Dependency
```
IF slowest_downstream_span.duration > target_service_span.duration * 0.5
THEN root_cause = "downstream_dependency"
     culprit    = slowest_downstream_span.service_name
```

### Rule 5 — Internal Slowness (default)
```
IF no other rule matched
THEN root_cause = "internal_slowness"
     culprit    = TARGET_SERVICE
```

---

## Infrastructure Setup

### Cluster

- 2-node Kubernetes cluster (kubeadm, bare metal)
- Master: `k8s-master` | Worker: `k8s-node1`
- CNI: Flannel (replaced Weave Net which is incompatible with K8s 1.31+)

### OTel Demo Deployment
```bash
helm install otel-demo open-telemetry/opentelemetry-demo -n otel-demo
```

### Jaeger v1.52 (Custom Pod)

The OTel demo ships with Jaeger v2.x which removed the REST API. We deploy a separate Jaeger v1.52 pod alongside:
```bash
kubectl apply -f jaeger-v1.yaml
```

The OTel collector configmap is patched to export traces to both Jaeger instances:
```yaml
exporters:
  otlp/jaeger:           # existing v2
    endpoint: jaeger:4317
  otlp/jaeger-query:     # our v1.52
    endpoint: jaeger-query:4317
```

### Port Forwarding (for local development)
```bash
kubectl port-forward svc/prometheus 9090:9090 -n otel-demo &
kubectl port-forward svc/jaeger-query 16686:16686 -n otel-demo &
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- Access to a running OTel demo cluster
- Ollama installed with Mistral pulled

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run the agent
```bash
cd AiOps
python3 agent.py
```

The agent will:
1. Collect baseline samples (20 samples × 10s = ~3 minutes)
2. Train and save the Isolation Forest model
3. Enter the monitoring loop
4. Print an incident report when an anomaly is detected

### Requirements
```
requests==2.31.0
scikit-learn==1.4.2
numpy==1.26.4
joblib==1.3.2
```

---

## Tech Stack

| Component | Technology | Role |
|---|---|---|
| Container Orchestration | Kubernetes 1.31 | Runs the demo application |
| CNI | Flannel | Pod networking |
| Instrumentation | OpenTelemetry SDK | Auto-instruments all services |
| Metrics | Prometheus | Stores and queries metrics |
| Traces | Jaeger v1.52 | Stores and queries distributed traces |
| Visualization | Grafana | Dashboards (separate from agent) |
| Anomaly Detection | Isolation Forest (scikit-learn) | Detects metric drift |
| Feature Scaling | StandardScaler (scikit-learn) | Normalizes feature vectors |
| Agent Language | Python 3.12 | Entire agent implementation |
| LLM Runtime | Ollama | Runs Mistral locally |
| LLM Model | Mistral | Generates incident explanations |

---

## Key Design Decisions

### Why Isolation Forest over thresholds?

Static thresholds require manual tuning and miss multi-dimensional anomalies. Isolation Forest learns what normal looks like from your actual traffic and flags statistically unusual combinations — for example, normal latency with abnormally high CPU and low RPS is still caught.

### Why deterministic RCA over LLM-driven RCA?

LLMs hallucinate. In incident response, a wrong root cause wastes time and can cause harm. The rule engine produces the same output for the same inputs every time — it is fully auditable and testable. The LLM only communicates what the rule engine determined.

### Why recommendation service as the target?

The recommendation service has a known downstream dependency on product-catalog, making it the richest RCA demonstration target. The architecture is service-agnostic — changing `TARGET_SERVICE` in settings.py is all that is needed to monitor a different service.

### Why Jaeger v1.52 alongside Jaeger v2?

Jaeger v2 (used in OTel demo v2.2.0) moved to gRPC-only queries, removing the REST API. Rather than implementing a gRPC client (2-3 hours, poorly documented for Python), we deployed a lightweight Jaeger v1.52 pod alongside and routed traces to both. This is a pragmatic production decision — use the right tool for the job.

### Why [5m] rate window in PromQL?

Testing revealed that `[1m]` windows returned empty results due to the Prometheus scrape interval and sparse trace data. A `[5m]` window provides sufficient data points for stable rate calculations while remaining responsive to recent changes.

---

## Module Status

| Module | Status |
|---|---|
| `Configs/settings.py` | ✅ Complete |
| `Tools/metrics_fetcher.py` | ✅ Complete |
| `Models/anomaly_detector.py` | ✅ Complete |
| `Tools/trace_analyzer.py` | ✅ Complete |
| `RCA/rule_engine.py` | ✅ Complete |
| `Tools/suggestion_engine.py` | ✅ Complete |
| `LLM/explainer.py` | 🔄 In Progress |
| `agent.py` | 🔄 In Progress |

---

*Cloud Computing Master's Project — AIOps Observability System v0.1.0-alpha*
