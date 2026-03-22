# config/settings.py

# ──────────────────────────────────────────
# Prometheus
# ──────────────────────────────────────────
PROMETHEUS_URL = "http://10.96.167.218:9090/api/v1/query"

# ──────────────────────────────────────────
# Jaeger
# ──────────────────────────────────────────
JAEGER_URL = "http://10.111.148.212:16686"

# ──────────────────────────────────────────
# Target service
# ──────────────────────────────────────────
TARGET_SERVICE   = "recommendation"
TARGET_NAMESPACE = "otel-demo"

# ──────────────────────────────────────────
# Prometheus queries
# ──────────────────────────────────────────
P95_QUERY = (
    'histogram_quantile(0.95, sum(rate('
    'traces_span_metrics_duration_milliseconds_bucket{'
    'service_name="recommendation",'
    'span_kind="SPAN_KIND_SERVER"}[5m])) by (le))'
)

CPU_QUERY = (
    'sum(rate(container_cpu_usage_seconds_total{'
    'namespace="otel-demo",'
    'pod=~"recommendation.*",'
    'container="recommendation"}[5m]))'
)

RPS_QUERY = (
    'sum(rate(traces_span_metrics_duration_milliseconds_count{'
    'service_name="recommendation",'
    'span_kind="SPAN_KIND_SERVER"}[5m]))'
)

# Downstream dependency query for RCA
DOWNSTREAM_QUERY = (
    'sum(rate(traces_span_metrics_duration_milliseconds_count{'
    'service_name="recommendation",'
    'span_kind="SPAN_KIND_CLIENT",'
    'span_name="/oteldemo.ProductCatalogService/ListProducts"}[5m]))'
)

# ──────────────────────────────────────────
# Isolation Forest
# ──────────────────────────────────────────
BASELINE_SAMPLES    = 20
COLLECTION_INTERVAL = 10
CONTAMINATION       = 0.1
N_ESTIMATORS        = 100
RANDOM_STATE        = 42

# ──────────────────────────────────────────
# Agent
# ──────────────────────────────────────────
MONITORING_INTERVAL     = 10
ANOMALY_SCORE_THRESHOLD = -0.1

# ──────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────
BASELINE_DATA_PATH = "data/baseline/baseline.npy"
MODEL_PATH         = "data/baseline/model.pkl"
SCALER_PATH        = "data/baseline/scaler.pkl"