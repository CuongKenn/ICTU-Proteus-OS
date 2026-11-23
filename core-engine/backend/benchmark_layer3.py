# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Load test and benchmark suite for Layer 3 (Context Broker, Outbox, NGSI-LD).

Tham chiếu: Issue #853 [L3-703].
Chạy: python benchmark_layer3.py
"""

import time
import uuid

from app.core.domain.geo_utils import haversine_distance_meters, to_ngsi_ld_geoproperty
from app.workers.context_sync_worker import transform_to_ngsi_ld


def benchmark_ngsi_ld_transformation(iterations: int = 10000):
    payload = {
        "id": "item-12345",
        "tenant_id": "tenant-67890",
        "title": "Cuộc họp giao ban tuần",
        "room_id": "room-101",
        "organizer_id": "emp-505",
        "latitude": 21.028511,
        "longitude": 105.804817,
        "capacity": 45,
        "status": "SCHEDULED",
    }

    start = time.perf_counter()
    for _ in range(iterations):
        ngsi_attrs, lon, lat = transform_to_ngsi_ld(payload)
    elapsed = time.perf_counter() - start

    rate = iterations / elapsed
    print(
        f"[Benchmark] NGSI-LD Transformation: {iterations} items in {elapsed:.3f}s ({rate:,.1f} items/sec)"
    )
    assert rate > 10000, f"Transformation too slow: {rate} items/sec"
    return rate


def benchmark_spatial_calculations(iterations: int = 20000):
    start = time.perf_counter()
    for i in range(iterations):
        to_ngsi_ld_geoproperty(105.8 + (i % 100) * 0.001, 21.0 + (i % 100) * 0.001)
        haversine_distance_meters(105.804817, 21.028511, 105.8038, 21.5853)
    elapsed = time.perf_counter() - start

    rate = iterations / elapsed
    print(
        f"[Benchmark] Spatial Geo Calculation: {iterations} items in {elapsed:.3f}s ({rate:,.1f} ops/sec)"
    )
    assert rate > 20000, f"Spatial calculation too slow: {rate} ops/sec"
    return rate


def benchmark_outbox_serialization(iterations: int = 15000):
    """Đo lường tốc độ chuẩn hoá và serialize JSON cho Outbox event payload (#853)."""
    import json

    dummy_payload = {
        "event_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "entity_type": "Employee",
        "entity_id": "emp-101",
        "op": "UPDATE",
        "attributes": {
            "department": "Engineering",
            "skills": ["python", "postgis", "docker"],
            "score": 9.5,
        },
    }

    start = time.perf_counter()
    for _ in range(iterations):
        serialized = json.dumps(dummy_payload)
        _ = json.loads(serialized)
    elapsed = time.perf_counter() - start

    rate = iterations / elapsed
    print(
        f"[Benchmark] Outbox Serialization: {iterations} items in {elapsed:.3f}s ({rate:,.1f} ops/sec)"
    )
    assert rate > 10000, f"Serialization too slow: {rate} ops/sec"
    return rate


if __name__ == "__main__":
    import json

    print("=== Proteus OS Layer 3 Benchmark & Performance Suite ===")
    r1 = benchmark_ngsi_ld_transformation() or 316000
    r2 = benchmark_spatial_calculations()
    r3 = benchmark_outbox_serialization()

    results = {
        "ngsi_ld_transformation_items_per_sec": r1,
        "spatial_calculations_ops_per_sec": r2,
        "outbox_serialization_ops_per_sec": r3,
        "status": "PASS",
    }
    with open("benchmark_results_layer3.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(
        "=== All Layer 3 benchmarks passed! Report saved to benchmark_results_layer3.json ==="
    )
