"""Remote HMAC signing endpoint for the Polymarket Builder program.

Why this exists
---------------
Polymarket's Builder program lets a 3rd-party site like Foresight route
its users' orders to the Polymarket CLOB while attributing those orders
to the builder for fee rebates. Each request to the CLOB API must carry
4 builder headers (signature, timestamp, api-key, passphrase) computed
from a SECRET that must NEVER reach the browser.

The pattern (per Polymarket's official wagmi-safe-builder-example):

  Browser  -- POST /api/polymarket/sign {method, path, body}
           -> Foresight server (this file) signs HMAC with secret
           <- returns {signature, timestamp, api-key, passphrase}
  Browser  -- attaches those as headers, POSTs the user-signed order
              directly to https://clob.polymarket.com (which validates
              the builder headers + the user's EIP-712 order signature)

The user's order signature stays in their MetaMask. The builder secret
stays on our server. Foresight is NOT a custodian — it just attributes
the order to itself for rebate purposes.

Security
--------
* The builder secret is read from env (`polymarket_builder_api_secret`)
  and never echoed to a client.
* The endpoint requires JWT auth — only signed-in Foresight users can
  request HMAC headers; an open endpoint would let any actor route
  their own orders through our builder code (and consume our quota).
* `path` is restricted to /api/v1/* on clob.polymarket.com to prevent
  the builder credential being used for unrelated calls (e.g.,
  reaching some admin endpoint we shouldn't authorize).

Library
-------
Uses `py-builder-signing-sdk` (the official Polymarket Python SDK).
Adding it to pyproject.toml in the same PR.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.routes.auth import get_current_user
from app.core.config import get_settings
from app.db.models import UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/polymarket", tags=["polymarket"])


# Restrict the builder credential to the CLOB API surface. Anything
# outside this allow-list is rejected — narrows blast radius if the
# endpoint is ever called maliciously.
_ALLOWED_PATH_PREFIXES = (
    "/api/v1/",        # main CLOB API surface (orders, markets, etc.)
    "/relayer-rpc/",   # relayer for Safe deployment + USDC approvals
    "/data-api/",      # public data (markets, prices) — safe to allow
)


class SignRequest(BaseModel):
    method: str  # GET, POST, PUT, DELETE
    path: str    # request path on clob.polymarket.com
    body: Optional[str] = None  # raw request body (string, exactly as sent)


class SignResponse(BaseModel):
    """Headers the browser must attach to its CLOB request.

    Field names mirror the Polymarket Builder header convention exactly
    so the frontend SDK (`@polymarket/clob-client` with builderConfig)
    can splat them into the request without renaming.
    """
    POLY_BUILDER_SIGNATURE: str
    POLY_BUILDER_TIMESTAMP: str
    POLY_BUILDER_API_KEY: str
    POLY_BUILDER_PASSPHRASE: str


def _validate_path(path: str) -> None:
    if not path.startswith(_ALLOWED_PATH_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"path must start with one of {_ALLOWED_PATH_PREFIXES}",
        )
    if not re.fullmatch(r"[\x20-\x7e]+", path):
        # Reject control characters that could splice the HMAC input
        # (timestamp+method+path+body). HMAC is binary-safe but we do
        # not want unexpected bytes in our error logs either.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="path contains non-printable characters",
        )


def _validate_method(method: str) -> str:
    method_upper = method.upper()
    if method_upper not in ("GET", "POST", "PUT", "DELETE"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"method must be GET/POST/PUT/DELETE, got {method!r}",
        )
    return method_upper


@router.post("/sign", response_model=SignResponse)
async def sign_request(
    req: SignRequest,
    user: UserProfile = Depends(get_current_user),
) -> SignResponse:
    """Build HMAC headers for a Polymarket CLOB request.

    The browser sends `(method, path, body)`; this endpoint computes the
    HMAC-SHA256 over `timestamp + method + path + body` and returns the
    four builder headers. The browser attaches them and POSTs to
    `clob.polymarket.com` directly — Foresight's server never sees the
    user-signed order itself.
    """
    s = get_settings()

    # Fail loud if the deploy is missing builder creds — the alternative
    # is silently returning empty strings and letting Polymarket reject
    # every order downstream with an opaque 401.
    if not (s.builder_api_key and s.builder_api_secret and s.builder_api_passphrase):
        logger.error(
            "builder_api_* not configured — refusing to sign for user %s",
            user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Polymarket builder credentials not configured on this deployment",
        )

    method = _validate_method(req.method)
    _validate_path(req.path)
    body = req.body or ""

    try:
        # Imports are inside-function because the SDK's top-level
        # `__init__.py` is empty (verified at SDK 0.0.2) — the classes
        # live in submodules.
        from py_builder_signing_sdk.config import BuilderConfig
        from py_builder_signing_sdk.sdk_types import BuilderApiKeyCreds
    except ImportError as exc:
        logger.exception("py_builder_signing_sdk not available")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="builder signing sdk not installed in this container",
        ) from exc

    creds = BuilderApiKeyCreds(
        key=s.builder_api_key,
        secret=s.builder_api_secret,
        passphrase=s.builder_api_passphrase,
    )
    config = BuilderConfig(local_builder_creds=creds)

    # Returns a `BuilderHeaderPayload` dataclass with the 4 fields
    # Polymarket expects on every CLOB request.
    payload = config.generate_builder_headers(method, req.path, body)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="builder header generation returned no payload",
        )

    return SignResponse(
        POLY_BUILDER_SIGNATURE=payload.POLY_BUILDER_SIGNATURE,
        POLY_BUILDER_TIMESTAMP=payload.POLY_BUILDER_TIMESTAMP,
        POLY_BUILDER_API_KEY=payload.POLY_BUILDER_API_KEY,
        POLY_BUILDER_PASSPHRASE=payload.POLY_BUILDER_PASSPHRASE,
    )
