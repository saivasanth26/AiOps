# AIOps Observability System

> Automated anomaly detection and root cause analysis for Kubernetes microservices using OpenTelemetry, Isolation Forest, and deterministic RCA rules. LLM used strictly for explanation — never for decisions.

![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)
![Kubernetes](https://img.shields.io/badge/Kubernetes-1.31-326CE5?style=flat-square&logo=kubernetes)
![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-2.2.0-black?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## Architecture

> View the [animated architecture diagram](/docs/architecture.html)
```
Prometheus (metrics)          Jaeger (traces)
      ↓                             ↓
Feature Vector [p95, cpu, rps]     Span Parsing
      ↓                             ↓
Isolation Forest              RCA Rule Engine
      ↓                             ↓
  Anomaly? ────────────────► Suggestions
                                    ↓
                             LLM Explanation
                                    ↓
                            Incident Report
```

---

## Core Philosophy

| Signal | Role |
|---|---|
| Metrics | Detection |
| Traces | Reasoning |
| Rules | Correctness |
| LLM | Explanation |

---

## Project Structure
```
AiOps/
├── Configs/
│   └── settings.py           # single source of truth
├── Tools/
│   ├── metrics_fetcher.py    # prometheus queries
│   ├── trace_analyzer.py     # jaeger trace parsing
│   └── suggestion_engine.py  # fix suggestion mapping
├── Models/
│   └── anomaly_detector.py   # isolation forest
├── RCA/
│   └── rule_engine.py        # deterministic rca rules
├── LLM/
│   └── explainer.py          # ollama/mistral explainer
├── agent.py                  # main orchestrator
└── requirements.txt
```

---

## RCA Rules

| Priority | Rule | Trigger |
|---|---|---|
| 1 | Cascade Failure | Errors across multiple services |
| 2 | Resource Pressure | CPU > 80% |
| 3 | Traffic Spike | RPS > 2x baseline |
| 4 | Downstream Dependency | Downstream span > internal span |
| 5 | Internal Slowness | Default fallback |

---

## Tech Stack

- **Infrastructure:** Kubernetes 1.31, Flannel CNI
- **Observability:** OpenTelemetry, Prometheus, Jaeger v1.52, Grafana
- **Detection:** Isolation Forest, StandardScaler (scikit-learn)
- **Agent:** Python 3.12, requests, joblib, numpy
- **LLM:** Ollama (Mistral) — explanation only

---

## Status

| Module | Status |
|---|---|
| Configs/settings.py | ✅ Complete |
| Tools/metrics_fetcher.py | ✅ Complete |
| Models/anomaly_detector.py | ✅ Complete |
| Tools/trace_analyzer.py | ✅ Complete |
| RCA/rule_engine.py | ✅ Complete |
| Tools/suggestion_engine.py | ✅ Complete |
| LLM/explainer.py | 🔄 In Progress |
| agent.py | 🔄 In Progress |

---

## Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Run the agent
python3 agent.py
```

---

*Cloud Computing Master's Project — AIOps Observability System v0.1.0-alpha*
