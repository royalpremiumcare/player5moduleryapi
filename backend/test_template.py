import os
import json
from twilio.rest import Client
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Ayarları al
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
from_number = os.getenv('TWILIO_FROM_NUMBER')

# ⚠️ BURAYA DİKKAT: Twilio Panelinden aldığın HX ile başlayan kodu buraya yapıştır
# Eğer panelde birden fazla varsa, durumu "Approved" olanı al.
TEMPLATE_SID = "HXc9d5674a770f66306b6b68ca0ecc3e34"  # <-- KONTROL ET: Senin SID'in bu mu?

# Test edilecek numara (Kendi numaranı yaz)
TO_NUMBER = "whatsapp:+905434793213" 

def test_send():
    print("🚀 Test Başlatılıyor...")
    print(f"Kullanılan SID: {TEMPLATE_SID}")

    if not account_sid or not auth_token:
        print("❌ HATA: .env dosyasında TWILIO_ACCOUNT_SID veya AUTH_TOKEN yok!")
        return

    client = Client(account_sid, auth_token)

    # Değişkenleri hazırla (Senin şablonuna göre 1,2,3,4,5,6 var)
    variables = {
        "1": "Test Müşteri",
        "2": "PLANN Test",
        "3": "20.12.2025",
        "4": "14:00",
        "5": "Test Hizmeti",
        "6": "+44 7474 626 900"
    }

    try:
        # Sadece Template gönderiyoruz, body YOK.
        message = client.messages.create(
            content_sid=TEMPLATE_SID,
            content_variables=json.dumps(variables),
            from_=from_number,
            to=TO_NUMBER
        )
        print(f"✅ BAŞARILI! Mesaj SID: {message.sid}")
        print("Mesaj telefonuna geldiyse, sorun senin server.py dosyanda demektir.")
        
    except Exception as e:
        print("\n❌ GÖNDERİM BAŞARISIZ OLDU!")
        print(f"Hata Detayı: {e}")
        print("-" * 30)
        if "63016" in str(e):
            print("🛑 ANALİZ: Hata hala 63016.")
            print("Bu şu anlama gelir: Twilio bu 'TEMPLATE_SID'yi geçerli bir şablon olarak görmüyor.")
            print("Lütfen Twilio Paneline girip bu HX kodunun 'Approved' (Onaylı) olup olmadığına bak.")

if __name__ == "__main__":
    test_send()