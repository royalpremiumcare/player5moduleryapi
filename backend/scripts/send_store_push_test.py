"""Tek seferlik test scripti: 'royalpremiumcare' hesabının native (iOS/Android)
FCM token'larına 'OPEN_STORE' action'lı güncelleme push'u gönderir.

Bildirime dokunulduğunda mobil istemci (App.js -> openAppStore) kullanıcıyı
işletim sistemine göre native mağaza uygulamasına yönlendirir.

Çalıştırma (backend container içinde — firebase-admin-key.json ve env burada):
    docker exec plann_backend python scripts/send_store_push_test.py

Opsiyonel: farklı bir hesap için
    docker exec plann_backend python scripts/send_store_push_test.py --user royalpremiumcare
"""
import os
import sys
import argparse

from pymongo import MongoClient
import firebase_admin
from firebase_admin import credentials, messaging

# Mağaza hedefleri (App.js ile aynı)
STORE_LINKS = {
    "ios": {
        "native": "itms-apps://apps.apple.com/app/id6759719891",
        "web": "https://apps.apple.com/app/id6759719891",
    },
    "android": {
        "native": "market://details?id=co.plannapp.app",
        "web": "https://play.google.com/store/apps/details?id=co.plannapp.app",
    },
}

TITLE = "PLANN güncellendi! 🎉"
BODY = "Yeni sürüm hazır. Güncellemek için dokunun."


def init_firebase():
    if firebase_admin._apps:
        return True
    key_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "firebase-admin-key.json")
    if not os.path.exists(key_path):
        print(f"❌ firebase-admin-key.json bulunamadı: {key_path}")
        return False
    cred = credentials.Certificate(key_path)
    firebase_admin.initialize_app(cred)
    print("✅ Firebase Admin SDK başlatıldı")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="royalpremiumcare", help="user_id (username/email) içinde aranacak ifade")
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        print("❌ MONGO_URL / DB_NAME environment değişkenleri yok")
        sys.exit(1)

    client = MongoClient(mongo_url)
    db = client[db_name]

    if not init_firebase():
        sys.exit(1)

    # royalpremiumcare hesabına ait native (ios/android) abonelikleri bul
    query = {
        "user_id": {"$regex": args.user, "$options": "i"},
        "platform": {"$in": ["ios", "android"]},
    }
    subs = list(db.push_subscriptions.find(query))

    if not subs:
        print(f"⚠️ '{args.user}' için native (ios/android) push aboneliği bulunamadı.")
        # Yardımcı: hangi user_id'lerde native abonelik var göster
        distinct_users = db.push_subscriptions.distinct(
            "user_id", {"platform": {"$in": ["ios", "android"]}}
        )
        print(f"   Native aboneliği olan user_id'ler: {distinct_users}")
        sys.exit(0)

    print(f"🔔 {len(subs)} native abonelik bulundu. Push gönderiliyor...\n")

    sent, failed = 0, 0
    for sub in subs:
        platform = sub.get("platform")
        token = sub.get("endpoint")
        conf = STORE_LINKS.get(platform, STORE_LINKS["android"])
        if not token:
            print(f"  - {platform}: token yok, atlandı")
            continue

        data = {
            "action": "OPEN_STORE",
            "store_url_native": conf["native"],
            "store_url_web": conf["web"],
        }
        # FCM: tüm value'lar string olmalı
        data = {str(k): str(v) for k, v in data.items()}

        message = messaging.Message(
            token=token,
            notification=messaging.Notification(title=TITLE, body=BODY),
            data=data,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    icon="ic_stat_icon",
                    color="#2563eb",
                    click_action="FLUTTER_NOTIFICATION_CLICK",
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(badge=1, sound="default"),
                )
            ),
        )

        try:
            resp = messaging.send(message)
            sent += 1
            print(f"  ✅ {platform} ({sub.get('user_id')}) token=…{token[-12:]} -> {resp}")
        except Exception as e:
            failed += 1
            print(f"  ❌ {platform} ({sub.get('user_id')}) token=…{token[-12:]} -> {type(e).__name__}: {e}")

    print(f"\nÖzet: {sent} gönderildi, {failed} hata.")


if __name__ == "__main__":
    main()
