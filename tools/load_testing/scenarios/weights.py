"""Global group weights (entities). Must sum to 1.0.

Final scenario share = GROUP_WEIGHTS[group] * MIX[key] (MIX in each scenario file sums to 1.0).

Weight 0.0 disables the group (its scenario modules are skipped). By default observability_5xx = 0:
GET /__loadtest/http500 needs LOADTEST_HTTP_500=true on the API; enable e.g.:
  "user": 0.9, "observability_5xx": 0.1
"""

from __future__ import annotations

GROUP_WEIGHTS: dict[str, float] = {
    "user": 1.0,
    "observability_5xx": 0.0,
    # Example: enable 5xx for metrics: "user": 0.9, "observability_5xx": 0.1 and LOADTEST_HTTP_500=true
}
