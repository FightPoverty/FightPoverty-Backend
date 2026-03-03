from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import Request, HTTPException, status
from fastapi.responses import Response


class JWTManager:
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_expire_minutes: int = 15,
        refresh_expire_days: int = 7,
        access_cookie_name: str = "access_token",
        refresh_cookie_name: str = "refresh_token",
        cookie_secure: bool = True,
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_expire_minutes = access_expire_minutes
        self.refresh_expire_days = refresh_expire_days
        self.access_cookie_name = access_cookie_name
        self.refresh_cookie_name = refresh_cookie_name
        self.cookie_secure = cookie_secure

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_payload(
        self,
        user_info: Dict[str, Any],
        token_type: str,
        expires_delta: timedelta,
    ) -> Dict[str, Any]:
        """
        預期 user_info 至少包含:
          - 'id'   : 使用者 ID
          - 'role' : 使用者角色 (可選)
        會輸出 payload:
          - userId, role, type, exp
          - store_id, homeless_id, association_id (若有)
        """
        user_id = user_info.get("id") or user_info.get("userId")
        if not user_id:
            raise ValueError("user_info 必須包含 'id' 或 'userId' 欄位")

        # 🔴 關鍵：不論是 UUID 或其他型別，統一轉成字串
        user_id_str = str(user_id)
        payload: Dict[str, Any] = {
            "userId": user_id_str,
            "role": user_info.get("role"),
            "type": token_type,  # "access" / "refresh"
            "exp": datetime.now(timezone.utc) + expires_delta,
        }

        # 加入關聯 ID（用於權限檢查）
        if user_info.get("store_id"):
            payload["store_id"] = str(user_info.get("store_id"))
        if user_info.get("homeless_id"):
            payload["homeless_id"] = str(user_info.get("homeless_id"))
        if user_info.get("association_id"):
            payload["association_id"] = str(user_info.get("association_id"))

        return payload

    def _create_token(self, payload: Dict[str, Any]) -> str:
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode(self, token: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token 已過期",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的 Token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def create_access_token(self, user_info: Dict[str, Any]) -> str:
        payload = self._build_payload(
            user_info=user_info,
            token_type="access",
            expires_delta=timedelta(minutes=self.access_expire_minutes),
        )
        return self._create_token(payload)

    def create_refresh_token(self, user_info: Dict[str, Any]) -> str:
        payload = self._build_payload(
            user_info=user_info,
            token_type="refresh",
            expires_delta=timedelta(days=self.refresh_expire_days),
        )
        return self._create_token(payload)

    # ------------------------------------------------------------------
    # Cookie helpers（JSONResponse / Response 皆可）
    # ------------------------------------------------------------------
    def set_auth_cookies(self, response: Response, access: str, refresh: str) -> None:
        # Access Token cookie（secure=False 時可在 HTTP 本地開發使用）
        response.set_cookie(
            key=self.access_cookie_name,
            value=access,
            httponly=True,
            max_age=self.access_expire_minutes * 60,
            samesite="none" if self.cookie_secure else "lax",
            secure=self.cookie_secure,
            path="/",
        )

        # Refresh Token cookie
        response.set_cookie(
            key=self.refresh_cookie_name,
            value=refresh,
            httponly=True,
            max_age=self.refresh_expire_days * 24 * 60 * 60,
            samesite="none" if self.cookie_secure else "lax",
            secure=self.cookie_secure,
            path="/",
        )

    def clear_auth_cookies(self, response: Response) -> None:
        response.delete_cookie(self.access_cookie_name, path="/")
        response.delete_cookie(self.refresh_cookie_name, path="/")

    # ------------------------------------------------------------------
    # 從請求中提取 token（優先 Authorization header，降級 cookie）
    # ------------------------------------------------------------------
    def _extract_token(self, request: Request, cookie_name: str) -> str | None:
        """從請求中提取 JWT token。

        優先從 Authorization: Bearer <token> header 取得，
        若不存在則降級從 cookie 取得（向後相容）。
        """
        # 優先：Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # 去除 "Bearer " 前綴

        # 降級：cookie
        return request.cookies.get(cookie_name)

    # ------------------------------------------------------------------
    # 取出目前使用者（優先 header，降級 cookie）
    # ------------------------------------------------------------------
    def get_user_from_request(self, request: Request) -> Dict[str, Any]:
        """從 Access Token 取出使用者資訊。"""
        token = self._extract_token(request, self.access_cookie_name)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="缺少 Access Token",
            )

        payload = self.decode(token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token 類型錯誤（需要 access）",
            )

        return payload


    # ------------------------------------------------------------------
    # 取出 Refresh Token payload（優先 header，降級 cookie）
    # ------------------------------------------------------------------
    def get_refresh_payload(self, request: Request) -> Dict[str, Any]:
        """從 Refresh Token 取出 payload。"""
        token = self._extract_token(request, self.refresh_cookie_name)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="缺少 Refresh Token",
            )

        payload = self.decode(token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token 類型錯誤（需要 refresh）",
            )

        return payload
