# FightPoverty-Backend

Backend service for the FightPoverty donation management platform, built with FastAPI + Redis.

## Development

### 1. Environment Setup

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

To include the frontend for development, initialize the git submodule:

```bash
git submodule update --init --recursive
```

> [!NOTE]
> - `.env` is primarily used by the backend container.
> - In Docker Compose, Redis must be configured with `REDIS_HOST=redis`.

> [!WARNING]
> **Cross-domain deployment (Zeabur / Cloud):** Make sure the backend's `FRONTEND_URL` is set to the frontend's production URL (e.g. `https://fightpoverty.zeabur.app`) to allow CORS requests.

### 2. Starting the Development Environment

**Option A: Helper script (recommended)**

```bash
chmod +x enter_dev_env.sh
./enter_dev_env.sh
```

The script handles creating, starting, and attaching to the containers defined in `docker-compose.dev.yml`.

**Option B: Docker Compose manually**

```bash
docker compose -f docker-compose.dev.yml up -d          # Start
docker compose -f docker-compose.dev.yml up -d --build   # Rebuild and start
```

### 3. Test Data

Create your local seed config (feel free to modify the values):

```bash
cp scripts/seed_data.json.example scripts/seed_data.json
```

Seed the database with test users, stores, and products:

```bash
python scripts/seed_test_data.py
# Docker: docker exec -it fightpoverty-backend python scripts/seed_test_data.py
```

Clear the database (⚠️ flushes the entire Redis DB):

```bash
python scripts/clear_redis.py
# Docker: docker exec -it fightpoverty-backend python scripts/clear_redis.py
```

### 4. Access Services

| Service | URL |
|---------|-----|
| Frontend (Vite) | <http://localhost:5173> |
| Backend API (FastAPI) | <http://localhost:3001> |
| Health Check | <http://localhost:3001/health> |
| API Docs (Swagger UI) | <http://localhost:3001/docs> |
| API Docs (ReDoc) | <http://localhost:3001/redoc> |

### 5. Stopping the Development Environment

```bash
chmod +x stop_dev_env.sh
./stop_dev_env.sh          # Stop containers (keep Redis data)
./stop_dev_env.sh clean    # Stop containers and remove volumes (⚠️ Redis data will be cleared)
```

## Production

Start the production environment (backend only):

```bash
docker compose up -d --build
```
