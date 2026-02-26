FROM python:3.10-slim

WORKDIR /app

# 1. Sistem kütüphanelerini kur (Bazı Python paketleri derleme için buna ihtiyaç duyar)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Pip'i güncelle
RUN pip install --upgrade pip

# 3. requirements.txt varsa önce onu kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || echo "Requirements dosyası boş veya eksik, devam ediliyor..."

# 4. TÜM EKSİK PAKETLERİ TEK SEFERDE KURUYORUZ (Senin listenin özeti)
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    python-dotenv \
    motor \
    pymongo \
    pydantic \
    requests \
    python-multipart \
    python-jose[cryptography] \
    passlib[bcrypt] \
    apscheduler \
    python-socketio \
    sib-api-v3-sdk \
    pywebpush \
    cryptography \
    slowapi \
    firebase-admin \
    stripe

# 5. Tüm kodları kopyala
COPY . .

# 6. Uygulamayı senin belirttiğin port ve dosya ile başlat
CMD ["uvicorn", "server:socket_app", "--host", "0.0.0.0", "--port", "8002"]
