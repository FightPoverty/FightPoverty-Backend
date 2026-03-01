import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from src.routers import auth, homeless, stores, transactions, products, allocations, config, reports, users
from src.db.db import get_redis  # 這個是有 @lru_cache 的同步 redis client


# ─────────────────────────────────────────────────────────
# 錯誤訊息對照表（Pydantic 驗證錯誤 -> 中文訊息）
# ─────────────────────────────────────────────────────────
VALIDATION_ERROR_MESSAGES = {
    "string_pattern_mismatch": "格式不正確",
    "missing": "此欄位為必填",
    "string_too_short": "長度不足",
    "string_too_long": "長度超過限制",
    "value_error": "數值錯誤",
    "type_error": "類型錯誤",
    "int_parsing": "必須為整數",
    "greater_than": "數值必須大於 {gt}",
    "less_than": "數值必須小於 {lt}",
}

FIELD_NAME_MAPPING = {
    "id_number": "身分證字號",
    "name": "姓名",
    "phone": "手機號碼",
    "address": "地址",
    "amount": "金額",
    "points": "點數",
    "username": "使用者名稱",
    "password": "密碼",
    "email": "電子郵件",
    "emergency_contact": "緊急聯絡人",
    "emergency_phone": "緊急聯絡電話",
    "notes": "備註",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_conn = None

    try:
        # 取得全域共用的 Redis client
        redis_conn = get_redis()

        # 啟動時測試一下連線狀況（同步呼叫 OK，這邊還在啟動階段）
        try:
            redis_conn.ping()
            print("✅ Successfully connected to Redis.")
        except Exception as e:
            # 不讓整個服務直接掛掉，但把錯誤印出來
            print(f"⚠️ Failed to ping Redis on startup: {e}")

        # 如果之後你想在 app.state 上共用，也可以加這行（選配）
        app.state.redis = redis_conn

        # 把控制權交回給 FastAPI（開始處理請求）
        yield

    finally:
        print("🧹 Closing Redis connection.")
        try:
            if redis_conn is not None:
                redis_conn.close()
        except Exception as e:
            print(f"⚠️ Error while closing Redis: {e}")

        # 把 @lru_cache 的 cache 清掉，確保下次重啟不會殘留舊連線物件
        try:
            get_redis.cache_clear()
        except Exception as e:
            print(f"⚠️ Failed to clear get_redis cache: {e}")


# Create FastAPI app and include routers
app = FastAPI(title="homeless-donation-api", lifespan=lifespan)

# Allow CORS so the separate frontend service on Zeabur can connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")], # Zeabur will set FRONTEND_URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(homeless.router, prefix="/api/homeless", tags=["homeless"])
app.include_router(stores.router, prefix="/api/stores", tags=["stores"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
app.include_router(products.router, prefix="/api", tags=["products"])
app.include_router(allocations.router, prefix="/api/allocations", tags=["allocations"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(users.router, prefix="/api/users", tags=["users"])


# ─────────────────────────────────────────────────────────
# 全域錯誤處理器
# ─────────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    處理 Pydantic 驗證錯誤，回傳友善的中文錯誤訊息。
    """
    errors = []
    for error in exc.errors():
        # 取得欄位名稱
        loc = error.get("loc", [])
        field = loc[-1] if loc else "unknown"
        field_name = FIELD_NAME_MAPPING.get(field, field)

        # 取得錯誤類型和訊息
        error_type = error.get("type", "")
        default_msg = VALIDATION_ERROR_MESSAGES.get(error_type, error.get("msg", "驗證錯誤"))

        errors.append({
            "field": field,
            "field_name": field_name,
            "message": f"{field_name}{default_msg}",
            "type": error_type,
        })

    # 組合錯誤訊息
    error_messages = [e["message"] for e in errors]
    combined_message = "、".join(error_messages) if error_messages else "資料驗證失敗"

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": combined_message,
            "errors": errors,
        },
    )


@app.get("/health")
def health_check():
    return JSONResponse(
        content={
            "success": True,
            "message": "Server is running",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@app.get("/")
def read_root():
    return JSONResponse(
        content={"status": 0, "message": "Server is running."},
        status_code=200
    )


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "3001")),
        reload=os.getenv("RELOAD", "0") == "1",
    )
