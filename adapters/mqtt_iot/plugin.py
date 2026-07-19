"""Example IoT work_fn — community may replace with real MQTT subscribe.

Does not open a broker in-process; callers pass readings in ``request`` or use defaults.
Wire with::

    from novapanda.surfaces import ProviderAdapter
    from adapters.mqtt_iot.plugin import build_deliverable
    ProviderAdapter(client, build_deliverable).fulfill(exchange_id)
"""

from __future__ import annotations

from typing import Any


def build_deliverable(request: dict[str, Any]) -> dict[str, Any]:
    """Map exchange request (+ optional sensor fields) → deliverable JSON.

    Uses invoice-shaped fields so the reference SchemaVerifier rule can accept
    the demo path; real deployments SHOULD register a dedicated rule_id.
    """
    reading = request.get("sensor") or {}
    trip_id = str(reading.get("device_id") or request.get("exchange_id") or "iot-1")
    # Keep shape compatible with R-extract-invoice-v1 for smoke demos.
    # Extra IoT fields stay outside the verified schema object for now;
    # production SHOULD register a dedicated PHYS rule_id.
    return {
        "invoice_no": f"IOT-{trip_id}"[:32],
        "total": str(reading.get("amount_display") or "1.00"),
        "currency": str(reading.get("currency") or "USD"),
    }
