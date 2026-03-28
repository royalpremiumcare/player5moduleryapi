import re

with open('backend/server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Çökmeye sebep olan 503 kısımlarını kaldır
content = re.sub(
    r'(redis_client = getattr[^\n]+)\s+if redis_client is None:\s+raise HTTPException\(status_code=503, detail="SSO temporarily unavailable"\)',
    r'\1',
    content
)

# 2. Token Oluşturma (Create) endpointine MongoDB Yedeği Ekle
pattern_create = r'(redis_key = f"sso:\{code\}")\s+(payload = \{[^\}]+\})\s+await redis_client\.set\(redis_key, json\.dumps\(payload\), ex=ttl_seconds\)'
replace_create = r'''\2
        if redis_client:
            \1
            await redis_client.set(redis_key, json.dumps(payload), ex=ttl_seconds)
        else:
            db_inst = getattr(request.app, 'db', None)
            if db_inst is not None:
                from datetime import timedelta
                await db_inst.sso_codes.insert_one({"code": code, "payload": json.dumps(payload), "expire_at": datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)})
            else:
                raise HTTPException(status_code=503, detail="SSO unavailable")'''
content = re.sub(pattern_create, replace_create, content)

# 3. Token Bozdurma (Exchange) endpointine MongoDB Yedeği Ekle
pattern_exchange = r'(redis_key = f"sso:\{code\}")\s+raw = None\s+try:\s+raw = await redis_client\.getdel\(redis_key\)\s+except Exception:\s+raw = await redis_client\.get\(redis_key\)\s+if raw is not None:\s+await redis_client\.delete\(redis_key\)'
replace_exchange = r'''raw = None
        if redis_client:
            \1
            try:
                raw = await redis_client.getdel(redis_key)
            except Exception:
                raw = await redis_client.get(redis_key)
                if raw is not None:
                    await redis_client.delete(redis_key)
        else:
            sso_doc = await db.sso_codes.find_one_and_delete({"code": code})
            if sso_doc:
                expire_at = sso_doc.get("expire_at")
                if expire_at and expire_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
                    raw = sso_doc.get("payload")'''
content = re.sub(pattern_exchange, replace_exchange, content)

with open('backend/server.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ server.py basariyla güncellendi. Redis baglantisi kopsa bile artik MongoDB kullanilacak.")
