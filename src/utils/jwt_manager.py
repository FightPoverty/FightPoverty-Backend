from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from fastapi import HTTPException, Request, status


class JWTManager:
    """管理 JWT Token 的建立、解碼與提取。

    使用 Bearer Token（Authorization header）進行認證。
    """

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_expire_minutes: int = 15,
        refresh_expire_days: int = 7,
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_expire_minutes = access_expire_minutes
        self.refresh_expire_days = refresh_expire_days

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_payload(
        self,
        user_info: Dict[str, Any],
        token_type: str,
        expires_delta: timedelta,
    ) -> Dict[str, Any]:
        """建立 JWT payload。

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

        # 不論是 UUID 或其他型別，統一轉成字串
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
        """解碼並驗證 JWT token。"""
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
        """建立 Access Token。"""
        payload = self._build_payload(
            user_info=user_info,
            token_type="access",
            expires_delta=timedelta(minutes=self.access_expire_minutes),
        )
        return self._create_token(payload)

    def create_refresh_token(self, user_info: Dict[str, Any]) -> str:
        """建立 Refresh Token。"""
        payload = self._build_payload(
            user_info=user_info,
            token_type="refresh",
            expires_delta=timedelta(days=self.refresh_expire_days),
        )
        return self._create_token(payload)

    # ------------------------------------------------------------------
    # 從 Authorization header 提取 Bearer Token
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_bearer_token(request: Request) -> str | None:
        """從 Authorization: Bearer <token> header 提取 token。"""
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # 去除 "Bearer " 前綴
        return None

    # ------------------------------------------------------------------
    # 取出目前使用者（從 Access Token）
    # ------------------------------------------------------------------
    def get_user_from_request(self, request: Request) -> Dict[str, Any]:
        """從 Authorization header 的 Access Token 取出使用者資訊。"""
        token = self._extract_bearer_token(request)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="缺少 Access Token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        payload = self.decode(token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token 類型錯誤（需要 access）",
            )

        return payload

    # ------------------------------------------------------------------
    # 取出 Refresh Token payload
    # ------------------------------------------------------------------
    def get_refresh_payload(self, request: Request) -> Dict[str, Any]:
        """從 Authorization header 的 Refresh Token 取出 payload。"""
        token = self._extract_bearer_token(request)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="缺少 Refresh Token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        payload = self.decode(token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token 類型錯誤（需要 refresh）",
            )

        return payload
