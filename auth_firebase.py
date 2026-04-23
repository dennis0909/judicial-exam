"""Firebase Auth — 驗證前端送來的 Google ID token。

Flow:
1. 前端用 Firebase JS SDK + Google provider 完成登入
2. 前端每次 API 請求帶 `Authorization: Bearer <id_token>` header
3. 後端在這裡 verify token 並回傳 decoded claims(uid/email/name/picture)

無狀態 — 不用 server session cookie、不依賴 SQLite 持久化。
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

logger = logging.getLogger(__name__)

# Firebase Console → Project Settings → 專案 ID(非 number)
PROJECT_ID: str = os.environ.get("FIREBASE_PROJECT_ID", "").strip()

# google-auth 會自動 cache Google public keys,重複用同一個 Request 物件即可
_REQUEST = google_requests.Request()


def is_configured() -> bool:
    return bool(PROJECT_ID)


def verify_id_token(token: str) -> Optional[dict[str, Any]]:
    """Verify Firebase ID token。成功回 claims dict,失敗回 None。

    claims 重要欄位:
    - `sub` / `user_id` / `uid` — Firebase UID(唯一使用者 ID)
    - `email`, `email_verified`
    - `name`, `picture`
    - `firebase.sign_in_provider` — 例如 `google.com`
    """
    if not token:
        return None
    if not PROJECT_ID:
        logger.warning("auth_firebase: FIREBASE_PROJECT_ID 未設定,無法 verify")
        return None
    try:
        claims = google_id_token.verify_firebase_token(
            token, _REQUEST, audience=PROJECT_ID
        )
    except ValueError as exc:
        logger.info("auth_firebase: verify 失敗: %s", exc)
        return None
    if not claims:
        return None
    return claims


def extract_bearer(auth_header: Optional[str]) -> Optional[str]:
    """從 `Authorization: Bearer xxx` header 取 token。"""
    if not auth_header:
        return None
    parts = auth_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None
