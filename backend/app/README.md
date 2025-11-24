# PLANN API - Clean Architecture

**Modular FastAPI Backend with Clean Architecture Principles**

## 🏗️ Architecture

```
app/
├── core/                    # Core Layer (Config, Security, Business Constants)
│   ├── config.py           # Environment variables & settings
│   ├── security.py         # JWT, password hashing
│   ├── constants.py        # PLANS, defaults
│   ├── exceptions.py       # Custom exception classes
│   └── dependencies.py     # FastAPI dependencies (auth, db)
│
├── infrastructure/          # Infrastructure Layer (External Services)
│   └── database/
│       ├── mongodb.py      # MongoDB connection manager
│       └── redis_client.py # Redis connection manager
│
├── api/                     # Presentation Layer (API Routes)
│   ├── schemas/            # Pydantic request/response models
│   │   └── auth.py        # Auth schemas
│   └── v1/
│       ├── router.py       # Main API v1 router
│       └── endpoints/      # API endpoint modules
│           └── auth.py     # Authentication endpoints
│
└── main.py                 # FastAPI application entry point
```

## 🚀 Quick Start

### Run the Application

```bash
# Activate virtual environment
source venv/bin/activate

# Run on port 8003 (parallel with old server.py on 8002)
uvicorn app.main:app --host 127.0.0.1 --port 8003 --reload
```

### Test Endpoints

```bash
# Health check
curl http://127.0.0.1:8003/health

# API documentation
open http://127.0.0.1:8003/docs

# Register user
curl -X POST http://127.0.0.1:8003/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "test@test.com", "password": "test123"}'

# Login
curl -X POST http://127.0.0.1:8003/api/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@test.com&password=test123"
```

## ✅ Completed Modules

- ✅ Core (Config, Security, Constants, Dependencies)
- ✅ Infrastructure (MongoDB, Redis)
- ✅ Auth API (Register, Login, Me, Password Reset)

## 🔄 In Progress

- ⏳ Appointments API
- ⏳ Customers API
- ⏳ Services API
- ⏳ Staff API
- ⏳ Payments API
- ⏳ Socket.IO Workers
- ⏳ Background Schedulers

## 🎯 Benefits

1. **Modularity**: Each feature in separate module
2. **Testability**: Easy to unit test
3. **Scalability**: Ready for microservices
4. **Maintainability**: Clean separation of concerns
5. **Security**: Centralized auth & validation

## 📦 Dependencies

- FastAPI
- Motor (MongoDB async driver)
- Redis (caching & rate limiting)
- Pydantic (data validation)
- Jose (JWT tokens)
- Passlib (password hashing)

## 🔐 Environment Variables

See `.env` file for required configuration:
- `JWT_SECRET_KEY`
- `MONGODB_URL`
- `REDIS_HOST`
- `STRIPE_SECRET_KEY`
- etc.

## 📝 Notes

- Old `server.py` still running on port **8002**
- New clean architecture on port **8003**
- Both can run in parallel during migration
- Gradually migrate endpoints from old to new structure
