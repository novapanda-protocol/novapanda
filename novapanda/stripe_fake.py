"""Stripe API fake（PaymentIntent 子集）— 本地测试，不连真网。

路由相对 base `…/v1`（与真 Stripe 一致）。
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException, Request


def create_stripe_fake_app() -> FastAPI:
    app = FastAPI(title="Fake Stripe API v1")
    intents: dict[str, dict] = {}

    @app.post("/payment_intents")
    async def create_pi(request: Request):
        form = await request.form()
        amount = int(form.get("amount", 0))
        currency = str(form.get("currency", "usd")).lower()
        capture_method = str(form.get("capture_method", "automatic"))
        pid = "pi_fake_" + uuid.uuid4().hex[:12]
        status = "requires_capture" if capture_method == "manual" else "succeeded"
        intents[pid] = {
            "id": pid,
            "amount": amount,
            "currency": currency,
            "status": status,
            "capture_method": capture_method,
        }
        return intents[pid]

    @app.post("/payment_intents/{pid}/capture")
    def capture_pi(pid: str):
        pi = intents.get(pid)
        if pi is None:
            raise HTTPException(404, "unknown pi")
        if pi["status"] != "requires_capture":
            raise HTTPException(409, f"bad state {pi['status']}")
        pi["status"] = "succeeded"
        return pi

    @app.post("/payment_intents/{pid}/cancel")
    def cancel_pi(pid: str):
        pi = intents.get(pid)
        if pi is None:
            raise HTTPException(404, "unknown pi")
        if pi["status"] not in ("requires_capture", "requires_payment_method"):
            raise HTTPException(409, f"bad state {pi['status']}")
        pi["status"] = "canceled"
        return pi

    return app
