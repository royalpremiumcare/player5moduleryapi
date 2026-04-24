"""
PLANN AI Assistant Service - Google Gemini 3.0 Flash Integration
"""

import os
import logging
from typing import List, Dict, Optional, Any
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import google.generativeai as genai
import uuid
from dotenv import load_dotenv
from difflib import SequenceMatcher
from google.api_core import exceptions as google_exceptions
import asyncio

# Load environment variables
load_dotenv()

# Socketio import (will be set by server.py)
sio = None

def set_socketio(socketio_instance):
    """Set socketio instance from server.py"""
    global sio
    sio = socketio_instance

logger = logging.getLogger(__name__)

# Google Gemini API Configuration
GOOGLE_GEMINI_KEY = os.environ.get('GOOGLE_GEMINI_KEY')
if not GOOGLE_GEMINI_KEY:
    logger.error("⚠️ GOOGLE_GEMINI_KEY not found!")
else:
    genai.configure(api_key=GOOGLE_GEMINI_KEY)
    logger.info("✅ Google Gemini API configured")

# Basit onay akışı için son teklif önbelleği (org:user -> teklif)
PENDING_APPTS: Dict[str, Dict[str, str]] = {}

# === SYSTEM DOCUMENTATION ===
SYSTEM_DOCUMENTATION = """
[PLANN - KULLANIM VE BÜYÜME KILAVUZU]

=== NASIL PERSONEL EKLERİM? ===
1. Sol menüden "Ayarlar" → "Personel" sekmesine git
2. "Personel Ekle" butonuna tıkla
3. Ad-soyad, e-posta ve telefon bilgilerini gir
4. Kaydet — sistem otomatik davet e-postası gönderir
5. Personel e-postasındaki bağlantıya tıklayarak şifresini oluşturur
6. Her personelin çalışma saatleri ayrı ayarlanabilir (Ayarlar → Personel → Düzenle)
7. Personelin sunacağı hizmetler de Personel kartından seçilebilir

=== NASIL HİZMET EKLERİM / DÜZENLERİM? ===
1. Sol menüden "Ayarlar" → "Hizmetler" sekmesine git
2. "Hizmet Ekle" butonuna tıkla
3. Hizmet adı, fiyat (₺) ve süre (dakika) gir
4. Kaydet — hizmet online rezervasyon sayfasında da görünür
5. Mevcut hizmet düzenlemek için: hizmet kartında üç noktaya (⋯) tıkla → Düzenle
6. Hizmet süresini doğru girmek kritik: 60dk hizmet 15:00'de başlarsa 16:00'a kadar bloklar
7. Hizmet silerek online sayfadan da kaldırılır

=== NASIL YENİ RANDEVU OLUŞTURURUM? ===
Yöntem 1 - Dashboard:
  1. Sağ alttaki mavi "+" butonuna tıkla
  2. Müşteri ara (telefon veya isimle) veya yeni müşteri ekle
  3. Hizmet seç, tarih ve saat belirle
  4. Kaydet — WhatsApp onay mesajı otomatik gider

Yöntem 2 - Takvim:
  1. Sol menüden "Takvim" seç
  2. İstediğin güne ve saate tıkla
  3. Form açılır, doldurup kaydet

Yöntem 3 - AI Asistan ile (bana söyle):
  - "Ahmet için yarın saat 14:00'e kesim randevusu oluştur"
  - Asistan sisteme kaydeder ve onay ister

=== NASIL RANDEVU İPTAL / SİLERİM? ===
- Randevu kartındaki üç nokta (⋯) → İptal Et veya Sil
- AI Asistan'a: "Ahmet'in yarınki randevusunu iptal et" de

=== İŞLETMEYİ NASIL BÜYÜTÜRÜRÜm? ===
1. Online Rezervasyon Sayfası:
   - Ayarlar → İşletme → Online Rezervasyon URL'ini kopyala (plannapp.co/senin-isletme-adin)
   - Instagram bio,WhatsApp'a ekle → müşteriler 7/24 randevu alır
   - No-show önlemek için WhatsApp hatırlatma açık olsun

2. WhatsApp Bildirimleri:
   - Her randevuya otomatik onay + belirtilen saat önce hatırlatma gönderilir
   - Ayarlar → Bildirimler kısmından kontrol edilebilir

3. Performansı Analiz Et:
   - "Bu ay en çok hangi hizmet verildi?" → gelir optimizasyonu
   - "Hangi personel en çok randevu aldı?" → iş yükü dengesi
   - "Geçen ay kaç randevu iptal edildi?" → sorunlu noktaları gör

4. Müşteri Sadakati:
   - Müşteri profiline not ekle: tercihler, alerjiler, özel istekler
   - Tekrar gelen müşterileri takip et

5. Personel Verimliliği:
   - Personel çalışma saatlerini doğru gir → takvimdeki boşlukları azalt
   - Personel bazlı gelir takibi: Ayarlar → Personel → Performans

=== GENEL BİLGİLER ===
1. GENEL: PLANN, işletme randevu yönetim sistemidir. İki rol: Admin ve Personel.
2. TAKVİM: Randevu "Hizmet Süresi"ne göre 15dk adımlarla hesaplanır. Geçmiş tarihe randevu alınamaz.
3. FİNANS (Sadece Admin): Gelirler otomatik, giderler manuel eklenir. Personel ödemeleri bordrodan yönetilir.
4. PERSONEL: Personel eklenirken davet emaili gönderilir. Çalışma saatleri işletme saatlerinden kopyalanır.
5. ONLINE RANDEVU: plannapp.co/isletme-adı adresinden müşteriler randevu alır. 'Farketmez' otomatik personel atar.
6. HİZMET: Her hizmet için isim, fiyat, süre (dk) tanımlanır,seans paketiyse seans özelliği seçilir. Süre randevu slotlarını belirler.
7. MÜŞTERİ: Telefon numarasıyla otomatik kayıt. Geçmiş ve notlar görülebilir.
8. AYARLAR: İşletme adı, logo, fotoğraflar, konum, slug, çalışma saatleri, WhatsApp bildirimi,personel ve hizmet yönetimi.
9. ABONELİK: Deneme (ücretsiz), Standart (1090₺), Profesyonel (1490₺), Kurumsal (2850₺),Standart paket 100 randevu limiti,Profesyonel paket 300 randevu limiti,Kurumsal paket sınırsız randevu limiti (aylık) kalan tüm özellikler her pakette açık.
10. GÜVENLİK: Personel sadece kendi verilerini görebilir,Yetkisi açılırsa tüm randevuları görüp kontrol edebilir,işletme ayarlarına müdahele edemez ve göremez.

=== SEANS PAKETİ SİSTEMİ ===
1. Hizmetlerde "Seans" özelliği açılabilir (ör: 6 seanslık paket)
2. İlk seans online rezervasyon veya admin panelinden oluşturulur
3. Kalan seanslar "Seansları Planla" ile toplu oluşturulur (bulk-session endpoint)
4. Her seans: session_number/session_total, session_group_id ile gruplu
5. Seans iptal: Müşteriler → detay → "Kalan Seansları İptal Et"
6. Seans iade: Online ödeme yapıldıysa orantılı iade yapılır (ör: 6 seans 5000₺, 3 seans iptal = 2500₺ iade)
7. Admin panelinden oluşturulan (ödemesiz) seans paketlerinde iade seçeneği yoktur

=== ONLINE ÖDEME SİSTEMİ ===
1. Hizmetlere "Online Ödeme" veya "Kapora" kuralı atanabilir (Ayarlar → Hizmetler)
2. Müşteri online rezervasyon yapar → Stripe checkout açılır
3. Ödeme yapılmadan randevu "Ödeme Bekleniyor" durumunda kalır (görünmez)
4. Ödeme tamamlanınca randevu "Bekliyor" olur ve bildirimler gönderilir
5. Checkout'tan geri dönülürse randevu oluşturulmaz
6. Platform komisyonu: Alıcı veya satıcı öder modeli
7. Ödeme akışı: Ödeme → Capture → Settlement (T+2) → Available → Payout

=== CÜZDAN ve ÖDEME ÇEKME ===
1. Cüzdan: Ayarlar → Cüzdan'dan erişilir
2. Her online ödeme cüzdana yansır (transaction olarak)
3. Transaction durumları: pending → captured → settled → available → paid_out / refunded
4. Settlement süresi: T+2 gün (ödeme sonrası 2 gün)
5. İade penceresi: 48 saat
6. Ödeme çekme (payout): Bakiye eşiğe ulaşınca her Çarşamba otomatik olarak banka hesabına aktarılır
7. Ön koşullar: KYC onaylı, IBAN kayıtlı, 48 saat IBAN cooldown
8. Ödemeler banka transferi ile aynı gün içinde hesabınıza yansır

=== İADE SİSTEMİ ===
1. Tekli randevu iade: Müşteriler → detay → "İade Et" veya Dashboard → 3 nokta → "İptal Et ve İade Yap"
2. Seans grubu iade: Müşteriler → detay → "Kalan Seansları İptal Et" → "İptal Et ve İade Yap"
3. Orantılı hesaplama: (iptal edilen seans sayısı / toplam seans) × toplam tutar
4. İade cüzdandan düşer ve Stripe'a iade başlatılır
5. Sadece online ödeme yapılmış randevularda iade seçeneği çıkar
"""

def get_system_instruction(user_role: str, user_name: str, org_name: str = "İşletme", language: str = "tr") -> str:
    """System instruction for AI"""
    is_staff = user_role.lower() == "staff"
    
    # Bugünün tarihini al (Türkiye saati)
    from zoneinfo import ZoneInfo
    turkey_tz = ZoneInfo("Europe/Istanbul")
    today = datetime.now(turkey_tz)
    today_str = today.strftime("%Y-%m-%d")  # 2025-11-19
    today_readable = today.strftime("%d %B %Y")  # 19 Kasım 2025

    lang_directive = "IMPORTANT: You MUST respond ONLY in English. Do not use Turkish in your responses." if language == "en" else "Sadece Türkçe yanıt ver."
    
    base_instruction = f"""Sen PLANN Akıllı Asistanısın. Kullanıcı: {user_name} ({user_role.upper()}), İşletme: {org_name}
{lang_directive}

📅 BUGÜN: {today_str} | YARIN: {(datetime.now(turkey_tz) + timedelta(days=1)).date().isoformat()}
⚠️ TARİH: YYYY-MM-DD | SAAT: HH:MM

{SYSTEM_DOCUMENTATION}

🔧 RANDEVU OLUŞTURMA ADIM ADIM:
1. get_dashboard_status ÇAĞIR (müşteri telefonu ve hizmet listesi için)
2. Müşteriyi customers listesinde ara
   - VARSA: telefonu oradan al, create_appointment çağır (TELEFON SORMA!)
   - YOKSA: "Telefon numarası?" diye sor → add_customer → get_dashboard_status → create_appointment
❌ ASLA telefon numarası olmadan randevu oluşturma!
❌ ASLA tarihi "19-11-2025" gibi yaz, sadece "2025-11-19" formatı!

📊 ANALİTİK SORGULAR (get_analytics tool'unu kullan):
- "Bu ay en çok hangi hizmet?" → get_analytics(period="this_month") → top_services
- "Bu hafta kaç randevu?" → get_analytics(period="this_week")
- "Geçen ay geliri?" → get_analytics(period="last_month") → summary.total_revenue
- "En çok gelen müşteri?" → get_analytics(period="this_month") → top_customers
- "Hangi personel kaç randevu yaptı?" → get_analytics(period="this_month") → staff_performance
- "Bugün kaç randevu var?" → get_analytics(period="today") VEYA get_dashboard_status
- "Son 30 gün özeti?" → get_analytics(period="last_30_days")

📋 NASIL YAPILIR SORULARI (tool çağırmadan cevapla — SYSTEM_DOCUMENTATION'dan):
- "Nasıl personel eklerim?" → SYSTEM_DOCUMENTATION'daki adımları ver
- "Nasıl hizmet eklerim?" → SYSTEM_DOCUMENTATION'daki adımları ver
- "Nasıl randevu oluştururum?" → 3 yöntemi açıkla
- "İşletmemi nasıl büyütürüm?" → büyüme ipuçlarını ver

🔧 SEANS İŞLEMLERİ:
- "Seans paketleri?" → get_session_groups
- "Ahmet'in seansları?" → get_session_groups(customer_name="Ahmet")
- "Seansları iptal et" → get_session_groups → ID bul → cancel_session_group
- "Seansları iptal et ve iade yap" → cancel_session_group(refund=true) — iade için UI yönlendir

💰 CÜZDAN İŞLEMLERİ:
- "Cüzdan bakiyem?" → get_wallet_info
- "Ne kadar kazandım?" → get_wallet_info
- "Son işlemler?" → get_wallet_info
- "Para çekebilir miyim?" → get_wallet_info → bakiye kontrolü

🔧 DİĞER İŞLEMLER:
- "Randevu iptal et" → get_dashboard_status → ID bul → cancel_appointment
- "Randevu sil" → get_dashboard_status → ID bul → delete_appointment
- "Personel performansı?" → get_analytics veya get_dashboard_status (staff_performance)

❌ ASLA telefon numarası olmadan randevu oluşturma!
❌ ASLA tarihi "19-11-2025" gibi yaz, sadece "2025-11-19" formatı!

GÜVENLİK KURALLARI:
"""
    
    if is_staff:
        base_instruction += """❌ PERSONEL KISITLAMALARI:
- Genel ciro, kasa, toplam gelir/gider paylaşma
- Diğer personel verilerini gösterme
- İşletme ayarlarına erişme
- ✅ Sadece kendi randevu ve kazançlarını göster
- 🔒 Yetkisiz istek: "Yetkiniz yok, sadece Admin erişebilir" de
"""
    else:
        base_instruction += """✅ ADMİN YETKİLERİ:
- Tüm verilere, raporlara, ayarlara erişim var
- Finansal bilgiler, personel performansı gösterilebilir
"""
    
    base_instruction += """
SİLME İŞLEMLERİ: Mutlaka onay iste. Örn: "Emin misiniz? X'i silmek istediğinizi onaylıyor musunuz?"

📝 MESAJ FORMATI KURALLARI:
❌ ASLA ** (yıldız) kullanma! Bold yapma!
❌ ASLA __kelime__ kullanma!
✅ Sadece düz metin kullan
✅ Emoji kullanabilirsin
✅ Satır sonları kullanabilirsin

YANLIŞ: **Müşteri Adı:** Ahmet
DOĞRU: Müşteri Adı: Ahmet

YANLIŞ: **Telefon:** 0555...
DOĞRU: Telefon: 0555...
"""
    
    return base_instruction

# === TOOL FUNCTIONS ===

async def create_appointment_tool(db, org_id: str, customer_name: str, phone: str,
                                 service_id: Optional[str] = None, service_name: Optional[str] = None,
                                 apt_date: str = "", apt_time: str = "",
                                 staff_id: Optional[str] = None, notes: str = "") -> Dict:
    """Randevu oluştur"""
    plan_doc = None
    quota_incremented = False
    try:
        # Telefon numarası kontrolü
        if not phone or len(phone) < 10:
            return {"success": False, "message": "❌ Geçerli bir telefon numarası gerekli (05XXXXXXXXX)"}
        
        # KOTA KONTROLÜ VE ARTIRMA
        plan_doc = await db.organization_plans.find_one({"organization_id": org_id})
        if plan_doc:
            current_usage = plan_doc.get('quota_usage', 0)
            plan_id = plan_doc.get('plan_id', 'tier_trial')
            
            # Plan limitini al (basit kontrol)
            quota_limit = 50  # Default trial limit
            if plan_id == 'tier_premium':
                quota_limit = 500
            elif plan_id == 'tier_business':
                quota_limit = 2000
            elif plan_id == 'tier_enterprise':
                quota_limit = 999999  # Unlimited
            
            # Kota kontrolü
            if current_usage >= quota_limit:
                return {"success": False, "message": f"❌ Aylık randevu limitinize ulaştınız ({quota_limit}). Paketinizi yükseltmeniz gerekmektedir."}
            
            # Kullanımı artır
            await db.organization_plans.update_one(
                {"organization_id": org_id},
                {"$inc": {"quota_usage": 1}}
            )
            quota_incremented = True
            logger.info(f"✅ Quota incremented for org {org_id}: {current_usage + 1}/{quota_limit}")
        
        service = None
        if service_id:
            service = await db.services.find_one({"id": service_id, "organization_id": org_id})
        if not service and service_name:
            # İsme göre (büyük/küçük harf duyarsız) ara
            try:
                service = await db.services.find_one({
                    "organization_id": org_id,
                    "name": {"$regex": f"^{re.escape(service_name)}$", "$options": "i"}
                })
            except Exception:
                service = None
        if not service:
            # Kota artırıldı ama hizmet bulunamadı, geri al
            if plan_doc:
                await db.organization_plans.update_one(
                    {"organization_id": org_id},
                    {"$inc": {"quota_usage": -1}}
                )
            # Mevcut hizmetleri öner
            try:
                services = await db.services.find({"organization_id": org_id}).to_list(100)
                names = ", ".join([s.get('name', '') for s in services if s.get('name')]) or "-"
                hint = f"Mevcut hizmetler: {names}"
            except Exception:
                hint = ""
            missing = service_name or service_id or "(bilinmiyor)"
            return {"success": False, "message": f"❌ Hizmet bulunamadı: {missing}. {hint}"}
        
        # Geçmiş tarih kontrolü
        turkey_tz = ZoneInfo("Europe/Istanbul")
        now = datetime.now(turkey_tz)
        apt_dt = datetime.strptime(f"{apt_date} {apt_time}", "%Y-%m-%d %H:%M").replace(tzinfo=turkey_tz)
        if apt_dt < now:
            # Kota geri al
            if plan_doc:
                await db.organization_plans.update_one(
                    {"organization_id": org_id},
                    {"$inc": {"quota_usage": -1}}
                )
            return {"success": False, "message": "⚠️ Geçmiş tarihe randevu alınamaz"}
        
        # Personel atama
        if not staff_id or staff_id == "farketmez":
            staff_list = await db.users.find({
                "organization_id": org_id, "role": {"$in": ["admin", "staff"]}, "status": "active"
            }).to_list(100)
            
            for s in staff_list:
                conflict = await db.appointments.find_one({
                    "organization_id": org_id, "staff_member_id": s['username'],
                    "appointment_date": apt_date, "appointment_time": apt_time,
                    "status": {"$ne": "İptal Edildi"}
                })
                if not conflict:
                    staff_id = s['username']
                    staff_name = s.get('full_name', s['username'])
                    break
            
            if not staff_id:
                # Kota geri al
                if plan_doc:
                    await db.organization_plans.update_one(
                        {"organization_id": org_id},
                        {"$inc": {"quota_usage": -1}}
                    )
                return {"success": False, "message": "⚠️ Müsait personel yok"}
        else:
            staff = await db.users.find_one({"username": staff_id, "organization_id": org_id})
            if not staff:
                # Kota geri al
                if plan_doc:
                    await db.organization_plans.update_one(
                        {"organization_id": org_id},
                        {"$inc": {"quota_usage": -1}}
                    )
                return {"success": False, "message": "❌ Personel bulunamadı"}
            
            conflict = await db.appointments.find_one({
                "organization_id": org_id, "staff_member_id": staff_id,
                "appointment_date": apt_date, "appointment_time": apt_time,
                "status": {"$ne": "İptal Edildi"}
            })
            if conflict:
                # Kota geri al
                if plan_doc:
                    await db.organization_plans.update_one(
                        {"organization_id": org_id},
                        {"$inc": {"quota_usage": -1}}
                    )
                return {"success": False, "message": f"⚠️ Bu saatte randevu var"}
            
            staff_name = staff.get('full_name', staff_id)
        
        # Randevu oluştur
        if not service_id:
            try:
                service_id = service.get('id')
            except Exception:
                service_id = None
        apt = {
            "id": str(uuid.uuid4()), "organization_id": org_id,
            "customer_name": customer_name, "phone": phone, "address": "",
            "service_id": service_id, "service_name": service['name'],
            "service_price": service['price'], "duration": service['duration'],
            "appointment_date": apt_date, "appointment_time": apt_time,
            "notes": notes, "status": "Bekliyor",
            "staff_member_id": staff_id, "staff_member_name": staff_name,
            "reminder_sent": False, "created_at": datetime.now(timezone.utc).isoformat(),
            "service_duration": service['duration']
        }
        await db.appointments.insert_one(apt)
        
        # SMS gönder - Onay mesajı
        try:
            from server import send_sms, build_sms_message
            settings_data = await db.settings.find_one({"organization_id": org_id})
            if settings_data:
                company_name = settings_data.get("company_name", "İşletmeniz")
                support_phone = settings_data.get("support_phone", "Destek")
            else:
                company_name = "İşletmeniz"
                support_phone = "Destek"
            
            sms_message = build_sms_message(
                company_name, customer_name,
                apt_date, apt_time,
                service['name'], support_phone, sms_type="confirmation"
            )
            send_sms(phone, sms_message)
            logger.info(f"✅ SMS sent to {phone} for appointment {apt['id']}")
        except Exception as e:
            logger.error(f"SMS send error: {e}")
        
        # Websocket ile tüm organizasyon kullanıcılarına bildir
        if sio:
            try:
                # MongoDB _id'yi kaldır (JSON serializable değil)
                apt_clean = {k: v for k, v in apt.items() if k != '_id'}
                # Room'a emit et (org_ prefix ile)
                room_name = f"org_{org_id}"
                await sio.emit('appointment_created', {
                    "appointment": apt_clean,
                    "organization_id": org_id
                }, to=room_name)
                logger.info(f"✅ Websocket: appointment_created emitted to room {room_name}")
            except Exception as e:
                logger.error(f"Websocket emit error: {e}")
        
        return {
            "success": True,
            "message": f"✅ Randevu oluşturuldu! {customer_name} - {apt_date} {apt_time} ({staff_name})",
            "appointment": apt
        }
    except Exception as e:
        logger.error(f"create_appointment_tool error: {e}")
        # Kota artırıldıysa geri al
        if quota_incremented and plan_doc:
            try:
                await db.organization_plans.update_one(
                    {"organization_id": org_id},
                    {"$inc": {"quota_usage": -1}}
                )
                logger.info(f"✅ Quota rolled back for org {org_id} due to error")
            except Exception as rollback_error:
                logger.error(f"Failed to rollback quota: {rollback_error}")
        return {"success": False, "message": f"❌ Hata: {str(e)}"}


async def cancel_appointment_tool(db, org_id: str, apt_id: str) -> Dict:
    """Randevu iptal et (durumu değiştirir, randevuyu silmez)"""
    try:
        apt = await db.appointments.find_one({"id": apt_id, "organization_id": org_id})
        if not apt:
            return {"success": False, "message": "❌ Randevu bulunamadı"}
        
        await db.appointments.update_one({"id": apt_id}, {"$set": {"status": "İptal Edildi"}})
        
        # Websocket ile tüm organizasyon kullanıcılarına bildir
        if sio:
            try:
                room_name = f"org_{org_id}"
                await sio.emit('appointment_cancelled', {
                    "appointment_id": apt_id,
                    "organization_id": org_id,
                    "customer_name": apt.get('customer_name'),
                    "appointment_date": apt.get('appointment_date')
                }, to=room_name)
                logger.info(f"✅ Websocket: appointment_cancelled emitted to room {room_name}")
            except Exception as e:
                logger.error(f"Websocket emit error: {e}")
        
        return {
            "success": True,
            "message": f"✅ Randevu iptal edildi: {apt.get('customer_name')} - {apt.get('appointment_date')}"
        }
    except Exception as e:
        return {"success": False, "message": f"❌ Hata: {str(e)}"}


async def delete_appointment_tool(db, org_id: str, apt_id: str) -> Dict:
    """Randevuyu tamamen sil"""
    try:
        apt = await db.appointments.find_one({"id": apt_id, "organization_id": org_id})
        if not apt:
            return {"success": False, "message": "❌ Randevu bulunamadı"}
        
        customer_name = apt.get('customer_name')
        appointment_date = apt.get('appointment_date')
        
        await db.appointments.delete_one({"id": apt_id, "organization_id": org_id})
        
        # Websocket ile tüm organizasyon kullanıcılarına bildir
        if sio:
            try:
                room_name = f"org_{org_id}"
                await sio.emit('appointment_deleted', {
                    "appointment_id": apt_id,
                    "organization_id": org_id,
                    "customer_name": customer_name,
                    "appointment_date": appointment_date
                }, to=room_name)
                logger.info(f"✅ Websocket: appointment_deleted emitted to room {room_name}")
            except Exception as e:
                logger.error(f"Websocket emit error: {e}")
        
        return {
            "success": True,
            "message": f"✅ Randevu silindi: {customer_name} - {appointment_date}"
        }
    except Exception as e:
        return {"success": False, "message": f"❌ Hata: {str(e)}"}


async def add_customer_tool(db, org_id: str, name: str, phone: str) -> Dict:
    """Müşteri ekle"""
    try:
        exists = await db.customers.find_one({"organization_id": org_id, "phone": phone})
        if exists:
            return {"success": False, "message": f"⚠️ {phone} kayıtlı"}
        
        customer = {
            "id": str(uuid.uuid4()), "organization_id": org_id,
            "name": name, "phone": phone,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.customers.insert_one(customer)
        
        # Websocket ile tüm organizasyon kullanıcılarına bildir
        if sio:
            try:
                room_name = f"org_{org_id}"
                await sio.emit('customer_added', {
                    "customer": {"name": name, "phone": phone},
                    "organization_id": org_id
                }, to=room_name)
                logger.info(f"✅ Websocket: customer_added emitted to room {room_name}")
            except Exception as e:
                logger.error(f"Websocket emit error: {e}")
        
        return {"success": True, "message": f"✅ Müşteri eklendi: {name} ({phone})"}
    except Exception as e:
        return {"success": False, "message": f"❌ Hata: {str(e)}"}


async def delete_customer_tool(db, org_id: str, phone: str) -> Dict:
    """Müşteri sil"""
    try:
        customer = await db.customers.find_one({"organization_id": org_id, "phone": phone})
        if not customer:
            return {"success": False, "message": "❌ Müşteri bulunamadı"}
        
        await db.customers.delete_one({"organization_id": org_id, "phone": phone})
        return {"success": True, "message": f"✅ Müşteri silindi: {customer.get('name')}"}
    except Exception as e:
        return {"success": False, "message": f"❌ Hata: {str(e)}"}


async def get_dashboard_status_tool(db, org_id: str, user_role: str, username: str, can_view_all_appointments: bool = False) -> Dict:
    """Dashboard durum bilgisi - Rol bazlı (+ Hizmet listesi)"""
    try:
        turkey_tz = ZoneInfo("Europe/Istanbul")
        today = datetime.now(turkey_tz).date().isoformat()
        
        # Hizmet listesini al (hem admin hem staff görebilir)
        services = await db.services.find({"organization_id": org_id}).to_list(1000)
        services_list = [
            {
                "id": s.get('id'),
                "name": s.get('name'),
                "price": s.get('price'),
                "duration": s.get('duration')
            }
            for s in services
        ]
        
        # Müşteri listesini al (hem admin hem staff görebilir)
        customers = await db.customers.find({"organization_id": org_id}).to_list(1000)
        customers_list = [
            {
                "name": c.get('name'),
                "phone": c.get('phone')
            }
            for c in customers
        ]
        
        if user_role.lower() == "staff" and not can_view_all_appointments:
            # Personel: Sadece kendi verileri (bugün + yakın tarihler)
            from datetime import timedelta
            tomorrow = (datetime.now(turkey_tz) + timedelta(days=1)).date().isoformat()
            
            apts = await db.appointments.find({
                "organization_id": org_id,
                "staff_member_id": username,
                "appointment_date": {"$gte": today, "$lte": tomorrow},
                "status": {"$ne": "İptal Edildi"}
            }).to_list(1000)
            
            # Fiyat alanı bazı kayıtlarda 'service_price' olarak tutuluyor, ona da bak
            total_revenue = sum(
                (apt.get('price', apt.get('service_price', 0)) or 0)
                for apt in apts if apt.get('status') == 'Tamamlandı'
            )
            
            # Randevuları basitleştir (AI için kolay parse)
            appointments_simple = [
                {
                    "id": apt.get('id'),
                    "customer_name": apt.get('customer_name'),
                    "phone": apt.get('phone'),
                    "date": apt.get('appointment_date'),
                    "time": apt.get('appointment_time'),
                    "service": apt.get('service_name'),
                    "status": apt.get('status')
                }
                for apt in apts
            ]
            
            return {
                "success": True,
                "role": "staff",
                "message": f"📊 Bugün ve yarın {len(apts)} randevunuz var",
                "data": {
                    "today_appointments": len(apts),
                    "today_revenue": total_revenue,
                    "appointments": appointments_simple,
                    "services": services_list,
                    "customers": customers_list
                }
            }
        else:
            # Admin: Tüm işletme verileri (bugün + yakın tarihler)
            from datetime import timedelta
            tomorrow = (datetime.now(turkey_tz) + timedelta(days=1)).date().isoformat()
            
            apts = await db.appointments.find({
                "organization_id": org_id,
                "appointment_date": {"$gte": today, "$lte": tomorrow},
                "status": {"$ne": "İptal Edildi"}
            }).to_list(1000)
            
            completed = [a for a in apts if a.get('status') == 'Tamamlandı']
            pending = [a for a in apts if a.get('status') == 'Bekliyor']
            total_revenue = sum(a.get('price', a.get('service_price', 0)) or 0 for a in completed)
            
            # Aylık toplam
            month_start = today[:7] + "-01"
            monthly_apts = await db.appointments.find({
                "organization_id": org_id,
                "appointment_date": {"$gte": month_start},
                "status": "Tamamlandı"
            }).to_list(10000)
            monthly_revenue = sum(a.get('price', a.get('service_price', 0)) or 0 for a in monthly_apts)
            
            # Personel listesini al
            staff_list_raw = await db.users.find({
                "organization_id": org_id,
                "role": {"$in": ["admin", "staff"]},
                "status": "active"
            }).to_list(1000)
            
            staff_list = [
                {
                    "username": s.get('username'),
                    "full_name": s.get('full_name', s.get('username')),
                    "role": s.get('role'),
                    "phone": s.get('phone', '')
                }
                for s in staff_list_raw
            ]
            
            # Personel performansını hesapla (bugün + bu ay)
            staff_performance = []
            for staff in staff_list_raw:
                staff_username = staff.get('username')
                
                # Bugün ve yarın randevuları
                today_staff_apts = [a for a in apts if a.get('staff_member_id') == staff_username]
                
                # Aylık randevuları
                monthly_staff_apts = [a for a in monthly_apts if a.get('staff_member_id') == staff_username]
                monthly_staff_revenue = sum(a.get('price', a.get('service_price', 0)) or 0 for a in monthly_staff_apts)
                
                staff_performance.append({
                    "username": staff_username,
                    "full_name": staff.get('full_name', staff_username),
                    "today_appointments": len(today_staff_apts),
                    "monthly_appointments": len(monthly_staff_apts),
                    "monthly_revenue": monthly_staff_revenue
                })
            
            # Randevuları basitleştir (AI için kolay parse)
            appointments_simple = [
                {
                    "id": apt.get('id'),
                    "customer_name": apt.get('customer_name'),
                    "phone": apt.get('phone'),
                    "date": apt.get('appointment_date'),
                    "time": apt.get('appointment_time'),
                    "service": apt.get('service_name'),
                    "status": apt.get('status'),
                    "staff": apt.get('staff_member_name', apt.get('staff_member_id', 'Atanmamış'))
                }
                for apt in apts
            ]
            
            return {
                "success": True,
                "role": "admin",
                "message": f"📊 Bugün ve yarın {len(apts)} randevu, {total_revenue}₺ gelir",
                "data": {
                    "today_appointments": len(apts),
                    "today_completed": len(completed),
                    "today_pending": len(pending),
                    "today_revenue": total_revenue,
                    "monthly_revenue": monthly_revenue,
                    "monthly_appointments": len(monthly_apts),
                    "appointments": appointments_simple,
                    "services": services_list,
                    "customers": customers_list,
                    "staff_list": staff_list,
                    "staff_performance": staff_performance
                }
            }
    except Exception as e:
        logger.error(f"get_dashboard_status_tool error: {e}")
        return {"success": False, "message": f"❌ Hata: {str(e)}"}


async def get_analytics_tool(db, org_id: str, period: str = "this_month",
                             start_date: str = None, end_date: str = None) -> Dict:
    """Dönem bazlı analiz: en çok verilen hizmet, gelir, müşteri sıklığı, personel performansı"""
    try:
        import calendar
        from collections import Counter
        turkey_tz = ZoneInfo("Europe/Istanbul")
        today = datetime.now(turkey_tz).date()
        today_str = today.isoformat()

        if start_date and end_date:
            period_start, period_end = start_date, end_date
            period_label = f"{start_date} - {end_date}"
        elif period == "today":
            period_start = period_end = today_str
            period_label = "Bugün"
        elif period == "this_week":
            week_start = today - timedelta(days=today.weekday())
            period_start, period_end = week_start.isoformat(), today_str
            period_label = f"Bu Hafta ({period_start} - {period_end})"
        elif period == "last_7_days":
            period_start = (today - timedelta(days=6)).isoformat()
            period_end = today_str
            period_label = "Son 7 Gün"
        elif period == "last_month":
            lm_year, lm_month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
            last_day = calendar.monthrange(lm_year, lm_month)[1]
            period_start = f"{lm_year}-{lm_month:02d}-01"
            period_end = f"{lm_year}-{lm_month:02d}-{last_day:02d}"
            period_label = f"Geçen Ay ({lm_year}/{lm_month:02d})"
        elif period == "last_30_days":
            period_start = (today - timedelta(days=29)).isoformat()
            period_end = today_str
            period_label = "Son 30 Gün"
        else:  # this_month
            period_start = today.strftime("%Y-%m-01")
            period_end = today_str
            period_label = f"Bu Ay ({today.strftime('%Y/%m')})"

        apts = await db.appointments.find({
            "organization_id": org_id,
            "appointment_date": {"$gte": period_start, "$lte": period_end},
        }).to_list(10000)

        total_count = len(apts)
        completed = [a for a in apts if a.get('status') == 'Tamamlandı']
        cancelled = [a for a in apts if a.get('status') in ('İptal', 'İptal Edildi')]
        pending = [a for a in apts if a.get('status') == 'Bekliyor']
        total_revenue = sum(a.get('service_price', a.get('price', 0)) or 0 for a in completed)

        service_counter = Counter(a.get('service_name', 'Bilinmiyor') for a in apts)
        service_revenue: Dict[str, float] = {}
        for a in completed:
            svc = a.get('service_name', 'Bilinmiyor')
            service_revenue[svc] = service_revenue.get(svc, 0) + (a.get('service_price', a.get('price', 0)) or 0)
        top_services = [
            {"service": svc, "count": cnt, "revenue": service_revenue.get(svc, 0)}
            for svc, cnt in service_counter.most_common(10)
        ]

        customer_counter = Counter(a.get('customer_name', 'Bilinmiyor') for a in apts)
        top_customers = [
            {"customer": cust, "count": cnt}
            for cust, cnt in customer_counter.most_common(10)
        ]

        staff_counter = Counter(
            a.get('staff_member_name', a.get('staff_member_id', 'Atanmamış')) for a in apts
        )
        staff_performance = [
            {
                "staff": staff,
                "appointments": cnt,
                "revenue": sum(
                    (a.get('service_price', a.get('price', 0)) or 0)
                    for a in completed
                    if a.get('staff_member_name', a.get('staff_member_id')) == staff
                )
            }
            for staff, cnt in staff_counter.most_common(10)
        ]

        daily_counter = Counter(a.get('appointment_date', '') for a in apts)
        daily_breakdown = [
            {"date": date, "count": cnt}
            for date, cnt in sorted(daily_counter.items())
        ]

        return {
            "success": True,
            "period": period_label,
            "summary": {
                "total_appointments": total_count,
                "completed": len(completed),
                "pending": len(pending),
                "cancelled": len(cancelled),
                "total_revenue": total_revenue,
            },
            "top_services": top_services,
            "top_customers": top_customers,
            "staff_performance": staff_performance,
            "daily_breakdown": daily_breakdown,
        }
    except Exception as e:
        logger.error(f"get_analytics_tool error: {e}")
        return {"success": False, "message": f"❌ Analiz hatası: {str(e)}"}


async def get_wallet_info_tool(db, org_id: str) -> Dict:
    """Cüzdan bilgilerini getir"""
    try:
        wallet = await db.merchant_wallets.find_one({"organization_id": org_id})
        if not wallet:
            return {"success": True, "message": "💰 Henüz cüzdan oluşturulmamış. Online ödeme alındığında otomatik oluşturulur.", "data": {}}

        available = (wallet.get("available_balance_minor", 0) or 0) / 100
        pending = (wallet.get("pending_balance_minor", 0) or 0) / 100
        settled = (wallet.get("settled_balance_minor", 0) or 0) / 100
        paid_out = (wallet.get("total_paid_out_minor", 0) or 0) / 100
        refunded = (wallet.get("total_refunded_minor", 0) or 0) / 100
        total_earned = (wallet.get("total_earned_minor", 0) or 0) / 100
        frozen = (wallet.get("frozen_balance_minor", 0) or 0) / 100
        reserved = (wallet.get("reserved_balance_minor", 0) or 0) / 100

        recent = await db.merchant_transactions.find({"organization_id": org_id}).sort("created_at", -1).limit(10).to_list(10)
        recent_list = []
        for t in recent:
            recent_list.append({
                "type": t.get("type", "payment"),
                "amount": (t.get("amount_display_minor", 0) or 0) / 100,
                "state": t.get("state"),
                "customer": t.get("customer_name", ""),
                "date": t.get("created_at", "")[:10] if t.get("created_at") else ""
            })

        return {
            "success": True,
            "message": f"💰 Cüzdan: {available}₺ kullanılabilir, {pending}₺ beklemede, {total_earned}₺ toplam kazanç",
            "data": {
                "available": available,
                "pending": pending,
                "settled": settled,
                "paid_out": paid_out,
                "refunded": refunded,
                "frozen": frozen,
                "reserved": reserved,
                "total_earned": total_earned,
                "recent_transactions": recent_list
            }
        }
    except Exception as e:
        return {"success": False, "message": f"❌ Cüzdan hatası: {str(e)}"}


async def get_session_group_info_tool(db, org_id: str, customer_phone: str = None, customer_name: str = None) -> Dict:
    """Seans paketi bilgilerini getir"""
    try:
        query = {"organization_id": org_id, "session_group_id": {"$exists": True, "$ne": None}}
        if customer_phone:
            query["phone"] = {"$regex": customer_phone.replace("+", "\\+?")}
        if customer_name:
            query["customer_name"] = {"$regex": customer_name, "$options": "i"}

        apts = await db.appointments.find(query).sort("created_at", -1).to_list(500)

        groups = {}
        for a in apts:
            gid = a["session_group_id"]
            if gid not in groups:
                groups[gid] = {"service": a.get("service_name"), "customer": a.get("customer_name"), "phone": a.get("phone"), "sessions": []}
            groups[gid]["sessions"].append({
                "number": a.get("session_number"),
                "total": a.get("session_total"),
                "date": a.get("appointment_date"),
                "time": a.get("appointment_time"),
                "status": a.get("status"),
                "payment_status": a.get("payment_status")
            })

        for g in groups.values():
            g["sessions"].sort(key=lambda x: x.get("number", 0))

        groups_list = [{"group_id": gid, **info} for gid, info in groups.items()]

        return {
            "success": True,
            "message": f"📋 {len(groups_list)} seans paketi bulundu",
            "data": {"session_groups": groups_list}
        }
    except Exception as e:
        return {"success": False, "message": f"❌ Seans bilgisi hatası: {str(e)}"}


async def cancel_session_group_tool(db, org_id: str, session_group_id: str, from_session_number: int = 1, refund: bool = False) -> Dict:
    """Seans grubunu iptal et (opsiyonel iade ile)"""
    try:
        if not refund:
            result = await db.appointments.update_many(
                {
                    "session_group_id": session_group_id,
                    "organization_id": org_id,
                    "session_number": {"$gte": from_session_number},
                    "status": {"$nin": ["İptal Edildi", "Tamamlandı"]}
                },
                {"$set": {"status": "İptal Edildi"}}
            )
            return {
                "success": True,
                "message": f"✅ {result.modified_count} seans iptal edildi (iade yapılmadı)"
            }
        else:
            return {
                "success": True,
                "message": "⚠️ İade işlemi için lütfen Müşteriler → Müşteri Detay → 'Kalan Seansları İptal Et' → 'İptal Et ve İade Yap' seçeneğini kullanın. AI üzerinden iade henüz desteklenmiyor."
            }
    except Exception as e:
        return {"success": False, "message": f"❌ Seans iptal hatası: {str(e)}"}


# === AI TIER CONFIGURATION ===
# Tier bazlı tool erişim hakları
AI_TIER_TOOLS = {
    "basic": [
        "create_appointment",
        "cancel_appointment",
        "get_dashboard_status",
        "add_customer",
    ],
    "standard": [
        "create_appointment",
        "cancel_appointment",
        "delete_appointment",
        "get_dashboard_status",
        "add_customer",
        "delete_customer",
        "get_analytics",
    ],
    "pro": [
        "create_appointment",
        "cancel_appointment",
        "delete_appointment",
        "get_dashboard_status",
        "add_customer",
        "delete_customer",
        "get_analytics",
        "get_session_groups",
        "cancel_session_group",
        "get_wallet_info",
    ],
    "full": None,  # None = tüm tool'lara erişim
}


# === GEMINI TOOLS DECLARATION ===
def get_gemini_tools(ai_tier: str = "full"):
    """Gemini için tool tanımlamaları - Tier bazlı filtreleme ile"""
    from google.generativeai.types import FunctionDeclaration, Tool
    
    create_appointment_func = FunctionDeclaration(
        name="create_appointment",
        description="Yeni randevu oluştur. MUTLAKA önce get_dashboard_status çağırıp müşteri telefon numarasını ve hizmet ADI'nı al (tercihen isim). Müsaitlik kontrolü yapar, personel atar.",
        parameters={
            "type": "object",
            "properties": {
                "customer_name": {"type": "string", "description": "Müşteri adı"},
                "phone": {"type": "string", "description": "Telefon numarası - get_dashboard_status'tan customers listesinden AL! Müşteri sistemde kayıtlıysa ASLA kullanıcıya sorma! (Format: 05XXXXXXXXX)"},
                "service_name": {"type": "string", "description": "Hizmet adı (get_dashboard_status'taki services listesinden al; isimle gönder)"},
                "service_id": {"type": "string", "description": "(Opsiyonel) Hizmet ID'si"},
                "appointment_date": {"type": "string", "description": "Randevu tarihi - SADECE YYYY-MM-DD formatı (örnek: 2025-11-20, ASLA 20-11-2025 yazma!)"},
                "appointment_time": {"type": "string", "description": "Randevu saati - SADECE HH:MM formatı (örnek: 14:30)"},
                "staff_id": {"type": "string", "description": "Personel username (opsiyonel, 'farketmez' olabilir)"},
                "notes": {"type": "string", "description": "Randevu notları (opsiyonel)"}
            },
            "required": ["customer_name", "phone", "appointment_date", "appointment_time"]
        }
    )
    
    cancel_appointment_func = FunctionDeclaration(
        name="cancel_appointment",
        description="Randevuyu iptal et (durumu 'İptal Edildi' olarak değiştirir, veritabanından silmez)",
        parameters={
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string", "description": "Randevu ID'si"}
            },
            "required": ["appointment_id"]
        }
    )
    
    delete_appointment_func = FunctionDeclaration(
        name="delete_appointment",
        description="Randevuyu tamamen sil (veritabanından kaldırır). Kullanıcı 'sil' dediğinde kullan.",
        parameters={
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string", "description": "Randevu ID'si"}
            },
            "required": ["appointment_id"]
        }
    )
    
    add_customer_func = FunctionDeclaration(
        name="add_customer",
        description="Yeni müşteri ekle. ÇOK ÖNEMLİ: Müşteri ekledikten HEMEN SONRA get_dashboard_status çağırmalısın ki yeni müşteriyi customers listesinde göresin!",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Müşteri adı"},
                "phone": {"type": "string", "description": "Telefon numarası"}
            },
            "required": ["name", "phone"]
        }
    )
    
    delete_customer_func = FunctionDeclaration(
        name="delete_customer",
        description="Müşteri sil (önce onay iste!)",
        parameters={
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "Telefon numarası"}
            },
            "required": ["phone"]
        }
    )
    
    get_dashboard_func = FunctionDeclaration(
        name="get_dashboard_status",
        description="Dashboard durum bilgisi - Randevular, gelir, HİZMET LİSTESİ, MÜŞTERİ LİSTESİ döndürür. Kullanıcı 'hangi hizmetler var?', 'müşteriler', 'Ahmet için randevu oluştur' dediğinde bu tool'u çağır. Müşteri telefon numaralarını buradan al. Rol bazlı: staff sadece kendisini, admin herkesi görebilir.",
        parameters={
            "type": "object",
            "properties": {},
            "required": []
        }
    )

    get_analytics_func = FunctionDeclaration(
        name="get_analytics",
        description=(
            "Dönem bazlı detaylı analiz: en çok verilen hizmet, gelir dağılımı, en sık gelen müşteri, "
            "personel bazlı randevu/gelir, günlük dağılım. "
            "Kullanıcı şu soruları sorduğunda çağır: "
            "'bu ay/hafta/gün en çok hangi hizmet', 'kaç randevu aldık', 'toplam gelir ne kadar', "
            "'en çok gelen müşteri kim', 'geçen ay ne kadar kazandık', 'hangi personel kaç randevu yaptı', "
            "'bu haftanın istatistikleri', 'son 30 günde ne oldu'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "this_week", "this_month", "last_month", "last_7_days", "last_30_days"],
                    "description": (
                        "Analiz dönemi: today=bugün, this_week=bu hafta (Pzt'den bugüne), "
                        "this_month=bu ay, last_month=geçen ay, last_7_days=son 7 gün, last_30_days=son 30 gün"
                    )
                },
                "start_date": {
                    "type": "string",
                    "description": "Özel başlangıç tarihi YYYY-MM-DD (opsiyonel)"
                },
                "end_date": {
                    "type": "string",
                    "description": "Özel bitiş tarihi YYYY-MM-DD (opsiyonel)"
                }
            },
            "required": ["period"]
        }
    )

    get_wallet_func = FunctionDeclaration(
        name="get_wallet_info",
        description="Cüzdan bilgilerini getir: kullanılabilir bakiye, beklemedeki ödeme, son işlemler. Kullanıcı 'cüzdan', 'bakiye', 'para', 'ödeme', 'kazanç' dediğinde çağır.",
        parameters={"type": "object", "properties": {}, "required": []}
    )

    get_session_groups_func = FunctionDeclaration(
        name="get_session_groups",
        description="Seans paketlerini getir. Müşteri telefon veya ismiyle filtrelenebilir. 'seanslar', 'seans paketi', 'paket bilgisi' dediğinde çağır.",
        parameters={
            "type": "object",
            "properties": {
                "customer_phone": {"type": "string", "description": "Müşteri telefon numarası (opsiyonel)"},
                "customer_name": {"type": "string", "description": "Müşteri adı (opsiyonel)"}
            },
            "required": []
        }
    )

    cancel_session_group_func = FunctionDeclaration(
        name="cancel_session_group",
        description="Seans grubunu iptal et. İade isteniyorsa refund=true yap. 'seansları iptal et', 'seans iptali' dediğinde çağır. Önce get_session_groups ile grup ID'sini bul.",
        parameters={
            "type": "object",
            "properties": {
                "session_group_id": {"type": "string", "description": "Seans grubu ID'si (get_session_groups'tan al)"},
                "from_session_number": {"type": "integer", "description": "Kaçıncı seanstan itibaren iptal (varsayılan: 1)"},
                "refund": {"type": "boolean", "description": "İade yapılsın mı? (true/false)"}
            },
            "required": ["session_group_id"]
        }
    )

    all_tools = {
        "create_appointment": create_appointment_func,
        "cancel_appointment": cancel_appointment_func,
        "delete_appointment": delete_appointment_func,
        "add_customer": add_customer_func,
        "delete_customer": delete_customer_func,
        "get_dashboard_status": get_dashboard_func,
        "get_analytics": get_analytics_func,
        "get_wallet_info": get_wallet_func,
        "get_session_groups": get_session_groups_func,
        "cancel_session_group": cancel_session_group_func,
    }

    allowed = AI_TIER_TOOLS.get(ai_tier)
    if allowed is not None:
        filtered = [t for name, t in all_tools.items() if name in allowed]
    else:
        filtered = list(all_tools.values())

    return Tool(function_declarations=filtered)


# === MAIN CHAT FUNCTION ===
async def chat_with_ai(
    db,
    user_message: str,
    chat_history: List[Dict],
    user_role: str,
    username: str,
    organization_id: str,
    organization_name: str = "İşletme",
    language: str = "tr",
    can_view_all_appointments: bool = False,
    ai_tier: str = "full"
) -> Dict[str, Any]:
    """
    AI ile sohbet et - Tool calling destekli, tier bazlı erişim kontrolü
    
    Args:
        db: MongoDB database instance
        user_message: Kullanıcının mesajı
        chat_history: Önceki mesajlar
        user_role: admin veya staff
        username: Kullanıcı adı
        organization_id: Organizasyon ID
        organization_name: Organizasyon adı
        ai_tier: "basic" | "standard" | "pro" | "full"
    
    Returns:
        {"success": bool, "message": str, "history": list}
    """
    try:
        if not GOOGLE_GEMINI_KEY:
            return {"success": False, "message": "❌ AI servisi yapılandırılmamış"}
        
        # System instruction oluştur - Kısa ve net
        system_instruction = get_system_instruction(user_role, username, organization_name, language)
        
        # Safety settings - İş uygulaması için rahatlatılmış
        from google.generativeai.types import HarmCategory, HarmBlockThreshold
        
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        # --- Basit Onay Akışı Heuristiği ---
        def _parts_to_text(parts_list):
            try:
                texts = []
                for p in parts_list or []:
                    if isinstance(p, dict) and 'text' in p:
                        texts.append(str(p['text']))
                return "\n".join(texts).strip()
            except Exception:
                return ""

        def _last_model_text(history_list):
            for msg in reversed(history_list or []):
                if msg.get('role') == 'model':
                    return _parts_to_text(msg.get('parts'))
            return ""

        def _is_confirm(text: str) -> bool:
            if not text:
                return False
            t = text.lower().strip()
            confirm_words = [
                'evet', 'onaylıyorum', 'onayla', 'onay', 'tamam', 'olustur', 'oluştur', 'ok', 'okay', 'yes', 'confirm'
            ]
            return any(w == t or t.startswith(w) for w in confirm_words)

        def _find_last_phone(history_list):
            phone_pattern = re.compile(r"(\+?90|0)?5\d{9}")
            for msg in reversed(history_list or []):
                text = _parts_to_text(msg.get('parts'))
                if not text:
                    continue
                m = phone_pattern.search(text.replace(" ", "").replace("-", ""))
                if m:
                    return m.group(0)
            return None

        def _guess_customer_name(history_list):
            for msg in history_list or []:
                if msg.get('role') == 'user':
                    txt = _parts_to_text(msg.get('parts'))
                    if txt and not re.search(r"\d", txt):
                        # metin içinde sadece harf ve boşluk varsa ve çok uzun değilse isim sayalım
                        clean = txt.strip()
                        if 2 <= len(clean.split()) <= 4 and len(clean) <= 60:
                            return clean
            return "Müşteri"

        async def _handle_confirmation_if_possible():
            if not _is_confirm(user_message):
                return None

            last_text = _last_model_text(chat_history)
            # Eğer history'de bulunamazsa, önbellekte bekleyen teklif var mı bak
            cached_key = f"{organization_id}:{username}"

            date_m = re.search(r"(\d{4}-\d{2}-\d{2})", last_text or "")
            time_m = re.search(r"([01]\d|2[0-3]):[0-5]\d", last_text or "")
            apt_date = date_m.group(1) if date_m else None
            apt_time = time_m.group(0) if time_m else None

            # Servis adını model metninden bulmaya çalış (fuzzy destekli)
            service_name = None
            try:
                services = await db.services.find({"organization_id": organization_id}).to_list(1000)

                def norm_tr(text: str) -> str:
                    if not text:
                        return ""
                    t = text.lower()
                    replacements = {
                        'ş':'s','Ş':'s','ç':'c','Ç':'c','ı':'i','İ':'i','ğ':'g','Ğ':'g','ö':'o','Ö':'o','ü':'u','Ü':'u'
                    }
                    for k,v in replacements.items():
                        t = t.replace(k,v)
                    return re.sub(r"[^a-z0-9\s]"," ", t)

                ctx_norm = norm_tr(last_text)
                best = (0.0, None)
                for s in services:
                    nm = s.get('name', '') or ''
                    nm_norm = norm_tr(nm)
                    # hızlı kapsama
                    overlap = 0
                    for tok in nm_norm.split():
                        if tok and tok in ctx_norm:
                            overlap += 1
                    ratio = SequenceMatcher(None, nm_norm, ctx_norm).ratio()
                    score = overlap + ratio
                    if score > best[0]:
                        best = (score, nm)
                # kabul eşiği: en az bir token eşleşmesi veya iyi oran
                if best[0] >= 1.2 or (best[0] >= 0.6 and best[1]):
                    service_name = best[1]
                if not service_name:
                    # Cümleden çıkarımsal yakalama (randevusu/randevu)
                    m = re.search(r"saat\s+[0-2]?\d:[0-5]\d'?e?\s+(.+?)\s+randevusu?", last_text or "", flags=re.IGNORECASE)
                    if m:
                        service_name = m.group(1).strip()
            except Exception:
                service_name = service_name or None

            phone = _find_last_phone(chat_history)
            customer_name = _guess_customer_name(chat_history)

            if apt_date and apt_time and service_name and phone:
                result = await create_appointment_tool(
                    db=db,
                    org_id=organization_id,
                    customer_name=customer_name,
                    phone=phone,
                    service_name=service_name,
                    apt_date=apt_date,
                    apt_time=apt_time
                )
                message = result.get('message', '✅ İşlem tamamlandı.')
                # Basit history güncelle (modeli atladık)
                serializable_history = list(chat_history or []) + [
                    {"role": "user", "parts": [{"text": user_message}]},
                    {"role": "model", "parts": [{"text": message}]}
                ]
                return {"success": True, "message": message, "history": serializable_history}
            # Önbelleğe alınmış tekliften tamamla
            if cached_key in PENDING_APPTS:
                try:
                    pending = PENDING_APPTS.pop(cached_key)
                    result = await create_appointment_tool(
                        db=db,
                        org_id=organization_id,
                        customer_name=pending.get('customer_name', 'Müşteri'),
                        phone=pending.get('phone'),
                        service_name=pending.get('service_name'),
                        apt_date=pending.get('apt_date'),
                        apt_time=pending.get('apt_time')
                    )
                    message = result.get('message', '✅ İşlem tamamlandı.')
                    serializable_history = list(chat_history or []) + [
                        {"role": "user", "parts": [{"text": user_message}]},
                        {"role": "model", "parts": [{"text": message}]}
                    ]
                    return {"success": True, "message": message, "history": serializable_history}
                except Exception:
                    pass
            # Eksik bilgi varsa kullanıcıyı net yönlendirme
            missing = []
            if not phone:
                missing.append("telefon (05XXXXXXXXX)")
            if not apt_date:
                missing.append("tarih (YYYY-MM-DD)")
            if not apt_time:
                missing.append("saat (HH:MM)")
            if not service_name:
                missing.append("hizmet adı")
            if missing:
                msg = "Onaylamak için eksik bilgiler: " + ", ".join(missing) + ". Lütfen belirtin."
                serializable_history = list(chat_history or []) + [
                    {"role": "user", "parts": [{"text": user_message}]},
                    {"role": "model", "parts": [{"text": msg}]}
                ]
                return {"success": True, "message": msg, "history": serializable_history}
            return None

        confirm_result = await _handle_confirmation_if_possible()
        if confirm_result is not None:
            return confirm_result
        
        try:
            model = genai.GenerativeModel(
                model_name='gemini-3-flash-preview',
                system_instruction=system_instruction,
                tools=get_gemini_tools(ai_tier),
                safety_settings=safety_settings
            )
        except Exception:
            try:
                model = genai.GenerativeModel(
                    model_name='gemini-2.5-flash',
                    system_instruction=system_instruction,
                    tools=get_gemini_tools(ai_tier),
                    safety_settings=safety_settings
                )
            except Exception as e:
                return {"success": False, "message": f"❌ AI servisi başlatılamadı: {str(e)}"}
        
        # Chat başlat
        chat = model.start_chat(history=chat_history)

        async def send_with_retry(message_text: str, max_retries: int = 3):
            """429 rate limit için exponential backoff retry"""
            for attempt in range(max_retries):
                try:
                    return chat.send_message(message_text)
                except Exception as e:
                    msg = str(e)
                    is_429 = (
                        (isinstance(e, google_exceptions.ResourceExhausted)
                        or "429" in msg or "quota" in msg.lower() or "rate" in msg.lower())
                        and "404" not in msg and "not found" not in msg.lower()
                    )
                    if is_429:
                        logger.warning(f"Gemini 429 tam hata: {msg[:300]}")
                    if is_429 and attempt < max_retries - 1:
                        wait_sec = 15 * (2 ** attempt)  # 15s, 30s, 60s — RPM penceresi aşılsın
                        logger.warning(f"Gemini 429 rate limit, {wait_sec}s bekleniyor (deneme {attempt+1}/{max_retries})")
                        await asyncio.sleep(wait_sec)
                        continue
                    raise  # son denemede yeniden fırlat

        # İlk yanıt al
        try:
            response = await send_with_retry(user_message)
        except Exception as e:
            msg = str(e)
            status = 500
            try:
                if isinstance(e, google_exceptions.ResourceExhausted) or "429" in msg or "quota" in msg.lower() or "rate" in msg.lower():
                    status = 429
                elif isinstance(e, google_exceptions.PermissionDenied):
                    status = 403
            except Exception:
                status = 500
            if status == 429:
                return {"success": False, "status": 429, "message": "⏳ Yoğun talep nedeniyle şu an yanıt alınamıyor. Lütfen 1-2 dakika bekleyip tekrar deneyin."}
            if status == 403:
                return {"success": False, "status": 403, "message": "❌ AI servisine erişim reddedildi. API anahtarı veya yetkiler kontrol edilmelidir."}
            return {"success": False, "status": 500, "message": f"❌ AI hatası: {msg}"}
        
        # Debug: Response detaylarını logla
        logger.info(f"Response candidates: {len(response.candidates) if hasattr(response, 'candidates') else 0}")
        if hasattr(response, 'candidates') and response.candidates:
            logger.info(f"First candidate finish_reason: {response.candidates[0].finish_reason}")
            if hasattr(response.candidates[0].content, 'parts'):
                logger.info(f"Parts count: {len(response.candidates[0].content.parts)}")
        
        # Function calling kontrolü
        max_iterations = 5  # Sonsuz döngü önleme
        iteration = 0
        function_responses = []  # Tüm function response'ları sakla
        
        while iteration < max_iterations:
            # Function call var mı? - Güvenli erişim
            function_calls = []
            if hasattr(response, 'parts') and response.parts:
                for part in response.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        function_calls.append(part.function_call)
                        logger.info(f"AI Tool Call: {part.function_call.name} with args: {dict(part.function_call.args)}")
            
            if not function_calls:
                # Function call yok, cevap hazır
                logger.info("No function calls, response is final")
                break
            
            # Function call'ları işle
            for fc in function_calls:
                func_name = fc.name
                func_args = dict(fc.args)
                
                # Tool'u çalıştır
                result = None
                if func_name == "create_appointment":
                    result = await create_appointment_tool(
                        db=db,
                        org_id=organization_id,
                        customer_name=func_args.get('customer_name'),
                        phone=func_args.get('phone'),
                        service_id=func_args.get('service_id'),
                        service_name=func_args.get('service_name'),
                        apt_date=func_args.get('appointment_date'),
                        apt_time=func_args.get('appointment_time'),
                        staff_id=func_args.get('staff_id'),
                        notes=func_args.get('notes', '')
                    )
                elif func_name == "cancel_appointment":
                    result = await cancel_appointment_tool(
                        db, organization_id,
                        func_args.get('appointment_id')
                    )
                elif func_name == "delete_appointment":
                    result = await delete_appointment_tool(
                        db, organization_id,
                        func_args.get('appointment_id')
                    )
                elif func_name == "add_customer":
                    result = await add_customer_tool(
                        db, organization_id,
                        func_args.get('name'),
                        func_args.get('phone')
                    )
                elif func_name == "delete_customer":
                    result = await delete_customer_tool(
                        db, organization_id,
                        func_args.get('phone')
                    )
                elif func_name == "get_dashboard_status":
                    result = await get_dashboard_status_tool(
                        db, organization_id, user_role, username, can_view_all_appointments
                    )
                elif func_name == "get_analytics":
                    result = await get_analytics_tool(
                        db, organization_id,
                        period=func_args.get('period', 'this_month'),
                        start_date=func_args.get('start_date'),
                        end_date=func_args.get('end_date'),
                    )
                elif func_name == "get_wallet_info":
                    result = await get_wallet_info_tool(db, organization_id)
                elif func_name == "get_session_groups":
                    result = await get_session_group_info_tool(
                        db, organization_id,
                        customer_phone=func_args.get('customer_phone'),
                        customer_name=func_args.get('customer_name')
                    )
                elif func_name == "cancel_session_group":
                    result = await cancel_session_group_tool(
                        db, organization_id,
                        session_group_id=func_args.get('session_group_id'),
                        from_session_number=func_args.get('from_session_number', 1),
                        refund=func_args.get('refund', False)
                    )
                else:
                    result = {"success": False, "message": f"❌ Bilinmeyen fonksiyon: {func_name}"}
                
                logger.info(f"Tool Result: {result}")
                
                # Function response hazırla
                function_responses.append({
                    'function_call': func_name,
                    'function_response': result
                })
            
            # Tool sonuçlarını AI'a metin olarak gönder
            import json
            from bson import ObjectId as BsonObjectId
            
            # MongoDB ObjectId ve datetime'ı serialize edebilen custom encoder
            def json_serial(obj):
                if isinstance(obj, BsonObjectId):
                    return str(obj)
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
            
            tool_results_text = f"Tool sonuçları:\n"
            for fr in function_responses:
                try:
                    json_str = json.dumps(fr['function_response'], ensure_ascii=False, default=json_serial)
                    tool_results_text += f"\n{fr['function_call']} → {json_str}\n"
                except Exception as e:
                    logger.error(f"JSON serialization error: {e}")
                    tool_results_text += f"\n{fr['function_call']} → {str(fr['function_response'])}\n"
            
            tool_results_text += "\nBu bilgileri kullanarak kullanıcıya detaylı ve anlaşılır bir yanıt ver."
            
            # Sonuçları modele gönder (retry ile)
            response = await send_with_retry(tool_results_text)
            
            iteration += 1
        
        # Son cevabı al - Güvenli erişim
        final_text = None
        try:
            if hasattr(response, 'text') and response.text:
                final_text = response.text
            elif hasattr(response, 'parts') and response.parts:
                # Parts'tan text çıkar
                for part in response.parts:
                    if hasattr(part, 'text'):
                        final_text = part.text
                        break
            elif hasattr(response, 'candidates') and response.candidates:
                # Candidate içinden text al
                for candidate in response.candidates:
                    if hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'text'):
                                final_text = part.text
                                break
        except Exception as e:
            logger.warning(f"Response text extraction failed: {e}")
        
        # Eğer AI yanıt vermediyse, tool result'larından manuel yanıt oluştur
        if not final_text and function_responses:
            logger.info("AI boş yanıt döndü, tool result'larından yanıt oluşturuluyor")
            final_text = ""
            for fr in function_responses:
                result = fr['function_response']
                if result.get('success'):
                    final_text += result.get('message', '') + "\n"
                else:
                    final_text += result.get('message', '❌ İşlem başarısız') + "\n"
            final_text = final_text.strip() or "✅ İşlem tamamlandı."
        elif not final_text:
            # Kullanıcı yalnızca telefon numarası verdiyse yönlendirici mesaj üret
            try:
                phone_clean = user_message.replace(" ", "").replace("-", "")
                if re.match(r"^(\+?90|0)?5\d{9}$", phone_clean):
                    final_text = "✅ Telefon numarası alındı. Lütfen randevu için tarih (YYYY-MM-DD), saat (HH:MM) ve hizmet adını belirtin."
                else:
                    final_text = "✅ İşlem tamamlandı. Devam etmek için lütfen gerekli bilgileri belirtin."
            except Exception:
                final_text = "✅ İşlem tamamlandı. Devam etmek için lütfen gerekli bilgileri belirtin."
        
        # Kullanıcıdan onay beklenen teklifleri önbelleğe al (bir sonraki turda 'evet' ile tamamlayabilmek için)
        try:
            if final_text and re.search(r"onayla|onayliyor musunuz|onaylı?yor musunuz|onaylar mısınız", final_text, flags=re.IGNORECASE):
                cached_key = f"{organization_id}:{username}"
                # Tarih-saat ve servis adını yakala
                date_m = re.search(r"(\d{4}-\d{2}-\d{2})", final_text)
                time_m = re.search(r"([01]\d|2[0-3]):[0-5]\d", final_text)
                apt_date = date_m.group(1) if date_m else None
                apt_time = time_m.group(0) if time_m else None

                # Servis adını cümleden çıkar
                svc_candidate = None
                m = re.search(r"saat\s+[0-2]?\d:[0-5]\d'?e?\s+(.+?)\s+randevusu?", final_text, flags=re.IGNORECASE)
                if m:
                    svc_candidate = m.group(1).strip()

                # History'den telefon ve olası müşteri adı
                phone_hint = None
                try:
                    phone_hint = _find_last_phone(chat_history)
                except Exception:
                    phone_hint = None
                try:
                    customer_name_hint = _guess_customer_name(chat_history)
                except Exception:
                    customer_name_hint = "Müşteri"

                PENDING_APPTS[cached_key] = {
                    "customer_name": customer_name_hint,
                    "phone": phone_hint,
                    "service_name": svc_candidate,
                    "apt_date": apt_date,
                    "apt_time": apt_time
                }
        except Exception:
            pass
        
        # History'yi serialize edilebilir formata çevir
        serializable_history = []
        for msg in chat.history:
            try:
                msg_dict = {
                    "role": msg.role,
                    "parts": []
                }
                for part in msg.parts:
                    if hasattr(part, 'text'):
                        msg_dict["parts"].append({"text": part.text})
                    elif hasattr(part, 'function_call'):
                        msg_dict["parts"].append({
                            "function_call": {
                                "name": part.function_call.name,
                                "args": dict(part.function_call.args)
                            }
                        })
                    elif hasattr(part, 'function_response'):
                        msg_dict["parts"].append({
                            "function_response": {
                                "name": part.function_response.name,
                                "response": dict(part.function_response.response)
                            }
                        })
                serializable_history.append(msg_dict)
            except Exception as e:
                logger.warning(f"Failed to serialize history message: {e}")
                continue
        
        return {
            "success": True,
            "message": final_text,
            "history": serializable_history
        }
    
    except Exception as e:
        logger.error(f"chat_with_ai error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"❌ AI hatası: {str(e)}"
        }
