import sys
import os
from redis import Redis

# 取得專案根目錄，並加入 sys.path，確保能找到 src 模組
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

from src.db.db import get_redis

def clear_redis():
    try:
        # 使用專案內建的 Redis 連線池
        redis_conn: Redis = get_redis()
        
        # 測試連線
        redis_conn.ping()
        print("✅ Redis 連線成功！")
        
        # 取得清空前的 Key 數量 (供參考)
        keys_count = len(redis_conn.keys('*'))
        print(f"📊 清空前資料庫內共有 {keys_count} 個 key。")
        
        user_input = input("⚠️  確定要清空目前資料庫的所有資料嗎？(y/N): ")
        if user_input.lower() == 'y':
            # 執行清空當前資料庫 (FLUSHDB)
            redis_conn.flushdb()
            print("🗑️  Redis 資料庫已成功清空！")
        else:
            print("❌ 操作已取消。")
            
    except Exception as e:
        print(f"❌ 發生未知的錯誤：{e}")

if __name__ == "__main__":
    clear_redis()
