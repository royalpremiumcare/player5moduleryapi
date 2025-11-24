# Migration Guide: server.py → Clean Architecture

## 🎯 Overview

This guide helps you migrate from the monolithic `server.py` (6578 lines) to the new Clean Architecture structure.

## 📊 Current Status

### Completed Modules (23 endpoints)
- ✅ **Auth** (5 endpoints) - Register, Login, Token, Password Reset
- ✅ **Appointments** (5 endpoints) - Full CRUD with quota management
- ✅ **Services** (5 endpoints) - Full CRUD (admin-only writes)
- ✅ **Customers** (5 endpoints) - Full CRUD with search
- ✅ **Plans** (2 endpoints) - List plans, current plan
- ✅ **Payments** (2 endpoints) - Stripe checkout, webhook

### Remaining in Old server.py
- ⏳ Staff Management
- ⏳ Stats & Analytics
- ⏳ Finance (Transactions, Expenses)
- ⏳ Settings
- ⏳ Socket.IO events
- ⏳ Background schedulers

## 🚀 Running Both APIs in Parallel

### Old API (Production)
```bash
# Port 8002
uvicorn server:socket_app --host 127.0.0.1 --port 8002
```

### New API (Clean Architecture)
```bash
# Port 8003
uvicorn app.main:app --host 127.0.0.1 --port 8003
```

**Both can run simultaneously!** No downtime required during migration.

## 📝 Migration Strategy

### Phase 1: Core Modules (✅ COMPLETED)
```
1. Setup Clean Architecture structure
2. Extract Core layer (config, security, constants)
3. Setup Infrastructure (MongoDB, Redis)
4. Migrate Auth endpoints
5. Migrate Appointments endpoints
6. Migrate Services endpoints
7. Migrate Customers endpoints
8. Migrate Plans & Payments endpoints
```

### Phase 2: Optional Extensions (⏳ OPTIONAL)
```
9. Migrate Staff Management
10. Migrate Stats endpoints
11. Migrate Finance endpoints
12. Migrate Settings endpoints
13. Add Socket.IO workers
14. Add Background schedulers
```

### Phase 3: Production Switch (When ready)
```
15. Update nginx config to point to new app
16. Test all endpoints in production
17. Monitor for issues
18. Deprecate old server.py
```

## 🔧 How to Migrate an Endpoint

### Example: Migrating a GET endpoint

**Old (server.py):**
```python
@api_router.get("/api/example")
async def get_example(
    request: Request,
    current_user: UserInDB = Depends(get_current_user)
):
    db = await get_db_from_request(request)
    # ... logic ...
    return result
```

**New (Clean Architecture):**

1. **Create Schema** (`app/api/schemas/example.py`):
```python
from pydantic import BaseModel

class ExampleResponse(BaseModel):
    id: str
    name: str
```

2. **Create Endpoint** (`app/api/v1/endpoints/example.py`):
```python
from fastapi import APIRouter, Depends
from ....core.dependencies import get_current_user, UserInDB
from ....infrastructure.database.mongodb import get_db
from ...schemas.example import ExampleResponse

router = APIRouter()

@router.get("", response_model=ExampleResponse)
async def get_example(
    current_user: UserInDB = Depends(get_current_user),
    db = Depends(get_db)
):
    # ... logic ...
    return ExampleResponse(**data)
```

3. **Register Router** (`app/api/v1/router.py`):
```python
from .endpoints import example

api_router.include_router(example.router, prefix="/example", tags=["Example"])
```

## 🧪 Testing After Migration

```bash
# Test new endpoint
curl http://localhost:8003/api/example \
  -H "Authorization: Bearer $TOKEN"

# Compare with old endpoint
curl http://localhost:8002/api/example \
  -H "Authorization: Bearer $TOKEN"

# Both should return same data
```

## 🔄 Rollback Plan

If issues occur:
1. Keep old `server.py` running on port 8002
2. Stop new app on port 8003
3. Point nginx back to port 8002
4. Debug new app without affecting production

## 📈 Benefits of Clean Architecture

1. **Modularity** - Each feature in separate module
2. **Testability** - Easy to unit test isolated components
3. **Scalability** - Ready for microservices split
4. **Maintainability** - Clear separation of concerns
5. **Type Safety** - Pydantic schemas everywhere
6. **Documentation** - Auto-generated OpenAPI docs

## 🎯 Next Steps

1. **Test current modules** - Verify all 23 endpoints work
2. **Migrate remaining endpoints** - Staff, Stats, Finance, Settings
3. **Add Socket.IO** - Real-time event handlers
4. **Add Schedulers** - Background jobs (SMS reminders, etc.)
5. **Production switch** - Update nginx, monitor, deprecate old

## 📚 Resources

- **OpenAPI Docs**: `http://localhost:8003/docs`
- **ReDoc**: `http://localhost:8003/redoc`
- **Health Check**: `http://localhost:8003/health`
- **Main README**: `app/README.md`

## ⚠️ Important Notes

- **Database**: Both apps use same MongoDB database
- **Redis**: Both apps use same Redis instance
- **No schema changes**: Clean Architecture uses existing collections
- **Backward compatible**: Old and new APIs are compatible
- **Zero downtime**: Can migrate gradually

---

**Questions?** Check `app/README.md` or examine existing modules for patterns.
