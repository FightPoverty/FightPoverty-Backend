import os
import sys
import json
import uuid
import secrets
import argparse
from datetime import datetime, timezone, timedelta

# 取得專案根目錄，並加入 sys.path，確保能找到 src 模組
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

# 台灣時區 (UTC+8)
TW_TIMEZONE = timezone(timedelta(hours=8))
import bcrypt
from redis import Redis

from src.db.db import get_redis


# =========================================================
# 工具函式
# =========================================================
def hash_password(plain: str) -> str:
    """使用 bcrypt 將明碼轉成 hash 字串"""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def generate_qr_code(prefix: str) -> str:
    """生成唯一 QR Code"""
    return f"{prefix}_{secrets.token_hex(5).upper()}"


def main(file_name: str) -> None:
    # 讀取指定的 JSON 檔案
    # 如果使用者輸入的是絕對路徑，os.path.join 會直接使用該絕對路徑
    seed_file_path = os.path.join(os.path.dirname(__file__), file_name)
    example_file_path = os.path.join(os.path.dirname(__file__), "seed_data.json.example")
    
    if not os.path.exists(seed_file_path):
        print(f"❌ 找不到測試資料設定檔：{seed_file_path}")
        if file_name == "seed_data.json":
            print(f"💡 請先複製一份範例檔並根據需要修改：")
            print(f"   cp {example_file_path} {seed_file_path}")
        sys.exit(1)
        
    try:
        with open(seed_file_path, "r", encoding="utf-8") as f:
            seed_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ 讀取 {seed_file_path} 失敗，請確認 JSON 格式是否正確。({e})")
        sys.exit(1)

    redis_conn: Redis = get_redis()  # type: ignore
    now = datetime.now(TW_TIMEZONE).isoformat()

    print("🚀 開始寫入測試資料到 Redis...\n")

    # ─────────────────────────────────────────────────────────
    # 1. 建立測試街友資料
    # ─────────────────────────────────────────────────────────
    print("📝 建立測試街友資料...")
    homeless_info = seed_data["homeless"]
    homeless_id = str(uuid.uuid4())
    homeless_qr_code = generate_qr_code("HL")
    homeless_data_to_save = {
        "id": homeless_id,
        "name": homeless_info["name"],
        "id_number": homeless_info["id_number"],
        "qr_code": homeless_qr_code,
        "balance": homeless_info["balance"],
        "phone": homeless_info["phone"],
        "address": homeless_info["address"],
        "emergency_contact": homeless_info["emergency_contact"],
        "emergency_phone": homeless_info["emergency_phone"],
        "notes": homeless_info["notes"],
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    redis_conn.hset(f"homeless:{homeless_id}", mapping=homeless_data_to_save)
    redis_conn.set(f"homeless:qr:{homeless_qr_code}", homeless_id)
    redis_conn.set(f"homeless:id_number:{homeless_data_to_save['id_number']}", homeless_id)
    redis_conn.sadd("homeless:all", homeless_id)
    print(f"  ✔ 測試街友 (ID: {homeless_id[:8]}...) - {homeless_data_to_save['name']}")

    # ─────────────────────────────────────────────────────────
    # 2. 建立測試商店資料
    # ─────────────────────────────────────────────────────────
    print("📝 建立測試商店資料...")
    store_info = seed_data["store"]
    store_id = str(uuid.uuid4())
    store_qr_code = generate_qr_code("ST")
    store_data_to_save = {
        "id": store_id,
        "name": store_info["name"],
        "qr_code": store_qr_code,
        "category": store_info["category"],
        "address": store_info["address"],
        "phone": store_info["phone"],
        "total_income": "0",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    redis_conn.hset(f"store:{store_id}", mapping=store_data_to_save)
    redis_conn.set(f"store:qr:{store_qr_code}", store_id)
    redis_conn.sadd("store:all", store_id)
    print(f"  ✔ 測試商店 (ID: {store_id[:8]}...) - {store_data_to_save['name']}")

    # ─────────────────────────────────────────────────────────
    # 2.5 建立測試商圈資料
    # ─────────────────────────────────────────────────────────
    print("📝 建立測試商圈資料...")
    assoc_info = seed_data["association"]
    association_id = str(uuid.uuid4())
    association_data_to_save = {
        "id": association_id,
        "name": assoc_info["name"],
        "description": assoc_info["description"],
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    redis_conn.hset(f"association:{association_id}", mapping=association_data_to_save)
    redis_conn.sadd("associations:all", association_id)
    # 將商店加入商圈
    redis_conn.sadd(f"association:{association_id}:stores", store_id)
    # 更新商店的 association_id
    redis_conn.hset(f"store:{store_id}", "association_id", association_id)
    print(f"  ✔ 測試商圈 (ID: {association_id[:8]}...) - {association_data_to_save['name']}")

    # 建立測試商品
    product_info = seed_data["product"]
    product_id = str(uuid.uuid4())
    product_data_to_save = {
        "id": product_id,
        "store_id": store_id,
        "name": product_info["name"],
        "points": product_info["points"],
        "category": product_info["category"],
        "description": product_info["description"],
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    redis_conn.hset(f"product:{product_id}", mapping=product_data_to_save)
    redis_conn.sadd(f"store:{store_id}:products", product_id)
    print(f"  ✔ 測試商品: {product_data_to_save['name']} ({product_data_to_save['points']}點)")

    # ─────────────────────────────────────────────────────────
    # 3. 建立測試使用者帳號
    # ─────────────────────────────────────────────────────────
    print("\n📝 建立測試使用者帳號...")
    test_users = seed_data["users"]
    
    if not test_users:
        print(f"⚠️ 未在 {seed_file_path} 中找到 users 資料。")
    else:
        for u in test_users:
            user_id = str(uuid.uuid4())
            username = u["username"]
    
            # 主資料
            user_data = {
                "id": user_id,
                "username": username,
                "password": hash_password(u["password"]),
                "name": u["name"],
                "role": u["role"],
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
    
            # 根據 link 欄位自動關聯對應的實體 ID
            link_type = u.get("link")
            if link_type == "store":
                user_data["store_id"] = store_id
            elif link_type == "homeless":
                user_data["homeless_id"] = homeless_id
            elif link_type == "association":
                user_data["association_id"] = association_id
    
            # 使用新的 key 結構
            redis_conn.hset(f"user:{user_id}", mapping=user_data)
            redis_conn.set(f"user:username:{username}", user_id)
    
            # 加入角色索引（用於帳號管理列表）
            redis_conn.sadd(f"users:role:{u['role']}", user_id)
            redis_conn.sadd("users:all", user_id)
    
            # 如果有 association_id，加入商圈使用者索引
            if "association_id" in user_data:
                redis_conn.sadd(f"association:{user_data['association_id']}:users", user_id)
    
            # 保留舊的 key 結構以保持向後相容
            redis_conn.hset(f"user:{username}", mapping=user_data)
    
            extra_info = ""
            if "store_id" in user_data:
                extra_info = f" → 商店:{store_qr_code}"
            if "homeless_id" in user_data:
                extra_info = f" → 街友:{homeless_qr_code}"
            if "association_id" in user_data:
                extra_info = f" → 商圈:{association_id[:8]}..."
            print(f"  ✔ {username} ({u['role']}){extra_info}")

    # ─────────────────────────────────────────────────────────
    # 4. 設定系統預設值
    # ─────────────────────────────────────────────────────────
    print("\n📝 設定系統預設值...")

    default_configs = {
        "max_balance_limit": {"value": "10000", "description": "最大餘額上限"},
        "max_allocation_limit": {"value": "1000", "description": "單次配額上限"},
        "default_page_size": {"value": "20", "description": "預設分頁大小"},
    }

    for key, config in default_configs.items():
        config_data = {
            "value": config["value"],
            "description": config["description"],
            "updated_at": now,
        }
        redis_conn.hset(f"config:{key}", mapping=config_data)
        print(f"  ✔ {key} = {config['value']}")

    print("\n🎉 測試資料建立完成！")
    print("\n📋 測試帳號資訊：")
    print("─" * 60)
    print(f"{'帳號':<20} {'密碼':<18} {'角色':<20}")
    print("─" * 60)
    for u in test_users:
        print(f"{u['username']:<20} {u['password']:<18} {u['role']:<20}")
    print("─" * 60)
    print(f"\n📦 測試街友 QR Code: {homeless_qr_code}")
    print(f"🏪 測試商店 QR Code: {store_qr_code}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="測試帳號初始化腳本 - 建立測試用帳號及關聯資料")
    parser.add_argument(
        "file",
        nargs="?",
        default="seed_data.json",
        help="要讀取的 JSON 資料檔名或路徑 (預設: seed_data.json)"
    )
    args = parser.parse_args()
    main(args.file)
