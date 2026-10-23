from typing import Any

import pytest


@pytest.fixture
def scenario_data() -> dict[str, Any]:
    return {
        "id": "fixture-orders-outage",
        "title": "Fixture: orders API outage after a config push",
        "source": "synthetic",
        "difficulty": 2,
        "tags": ["fixture-tag"],
        "alert": {
            "name": "OrdersErrorRateHigh",
            "service": "orders-api",
            "severity": "critical",
            "fired_at": "2026-01-10T12:05:00Z",
            "summary": "orders-api 5xx rate above 5% for 5 minutes",
        },
        "logs": [
            {
                "id": "log-001",
                "timestamp": "2026-01-10T12:01:00Z",
                "service": "orders-api",
                "level": "INFO",
                "message": "request served in 40ms",
            },
            {
                "id": "log-002",
                "timestamp": "2026-01-10T12:03:00Z",
                "service": "orders-api",
                "level": "ERROR",
                "message": "upstream inventory returned 503",
            },
        ],
        "metrics": [
            {
                "id": "met-001",
                "name": "http_5xx_rate",
                "service": "orders-api",
                "unit": "ratio",
                "points": [
                    {"timestamp": "2026-01-10T12:00:00Z", "value": 0.001},
                    {"timestamp": "2026-01-10T12:04:00Z", "value": 0.09},
                ],
            }
        ],
        "deploys": [
            {
                "id": "dep-001",
                "service": "orders-api",
                "version": "v1.4.2",
                "timestamp": "2026-01-10T11:00:00Z",
                "author": "ci-bot",
                "description": "bump logging library",
            }
        ],
        "configs": [
            {
                "id": "cfg-001",
                "service": "orders-api",
                "captured_at": "2026-01-10T12:02:00Z",
                "values": {"INVENTORY_URL": "http://inventory:9000"},
            }
        ],
        "ground_truth": {
            "root_cause": "config_error",
            "summary": "GROUND-TRUTH-SUMMARY-SENTINEL",
            "affected_service": "orders-api",
            "required_evidence": ["log-002", "cfg-001"],
            "distractors": ["dep-001"],
            "acceptable_remediations": ["REMEDIATION-SENTINEL"],
        },
        "budget": {"max_steps": 10, "max_tokens": 20000},
    }
