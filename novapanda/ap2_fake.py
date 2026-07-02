"""AP2 网关 fake server：供集成测试。"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class AuthorizeBody(BaseModel):
    exchange_id: str
    amount: int
    currency: str


class RefBody(BaseModel):
    ref: str


def create_ap2_fake_app() -> FastAPI:
    app = FastAPI(title="Fake AP2 Gateway")
    refs: dict[str, dict] = {}

    @app.post("/authorize")
    def authorize(body: AuthorizeBody):
        ref = "ap2-" + uuid.uuid4().hex[:12]
        refs[ref] = {
            "exchange_id": body.exchange_id,
            "amount": body.amount,
            "currency": body.currency,
            "state": "authorized",
        }
        return {"ref": ref}

    def _move(ref: str, target: str):
        h = refs.get(ref)
        if h is None:
            raise HTTPException(404, "unknown ref")
        if h["state"] not in (target, "authorized"):
            raise HTTPException(409, f"conflict: {h['state']} -> {target}")
        h["state"] = target
        return {"ref": ref, "amount": h["amount"], "currency": h["currency"], "status": target}

    @app.post("/capture")
    def capture(body: RefBody):
        return _move(body.ref, "captured")

    @app.post("/void")
    def void(body: RefBody):
        return _move(body.ref, "voided")

    return app
