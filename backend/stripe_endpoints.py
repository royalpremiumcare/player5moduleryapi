"""
Stripe Endpoints
PayTR'den Stripe'a migration için yeni endpoint'ler
"""

from fastapi import HTTPException, Request, Depends
from fastapi.responses import Response
from typing import Dict, Any
import logging
from datetime import datetime, timezone, timedelta

from stripe_service import create_checkout_session, parse_webhook_event
from server import (
    get_current_user, UserInDB, PlanUpdateRequest, 
    get_db_from_request, get_plan_info, get_organization_plan,
    send_email, _brand_email,
)
from billing_lifecycle_emails import (
    build_grace_period_email,
    build_suspended_email,
    cta_for_lang,
)

logger = logging.getLogger(__name__)

# Abonelik yenileme başarısızlığı gibi kritik olaylarda bilgilendirilecek sistem yöneticisi
SUPERADMIN_ALERT_EMAIL = "fatihsenyuz12@gmail.com"


async def _find_org_plan_by_subscription(db, subscription_id):
    """
    Stripe subscription ID'sine göre işletme planını bul.

    Geçmiş veri tutarsızlığı nedeniyle abonelik ID'si bazı kayıtlarda
    'subscription_id', bazılarında 'stripe_subscription_id' alanında saklı.
    Webhook'ların sessizce kayıt bulamamasını önlemek için her iki alana da bakar.
    """
    if not subscription_id:
        return None
    return await db.organization_plans.find_one({
        "$or": [
            {"subscription_id": subscription_id},
            {"stripe_subscription_id": subscription_id},
        ]
    })

async def create_stripe_checkout_session_handler(
    request: Request,
    plan_request: PlanUpdateRequest,
    current_user: UserInDB = Depends(get_current_user)
) -> Dict[str, Any]:
    """Stripe Checkout Session oluştur"""
    try:
        # Log mesajını hem console'a hem de file'a yaz
        log_msg = f"Stripe checkout session başlatılıyor: user={current_user.username}, plan_id={plan_request.plan_id}"
        logger.info(log_msg)
        print(f"[STRIPE] {log_msg}")
        
        if current_user.role != "admin":
            logger.warning(f"Payment endpoint: Yetkisiz erişim denemesi - user={current_user.username}, role={current_user.role}")
            raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
        
        # 1. İstenen planı bul ve fiyatını al
        plan = await get_plan_info(plan_request.plan_id)
        if not plan:
            logger.error(f"Plan bulunamadı: plan_id={plan_request.plan_id}")
            raise HTTPException(status_code=404, detail="Plan bulunamadı")
        
        # Plan dict'inin gerekli alanlarını kontrol et
        if 'price_monthly' not in plan or 'name' not in plan:
            logger.error(f"Plan eksik alanlar içeriyor: plan={plan}, plan_id={plan_request.plan_id}")
            raise HTTPException(status_code=500, detail="Plan verisi eksik veya geçersiz")
        
        # Trial paketini satın alınamaz
        if plan_request.plan_id == 'tier_trial':
            raise HTTPException(status_code=400, detail="Trial paketi satın alınamaz")
        
        db = await get_db_from_request(request)
        
        # 2. İndirimi uygula (İlk ay %25)
        plan_doc = await get_organization_plan(db, current_user.organization_id)
        is_first_month = plan_doc.get('is_first_month', True) if plan_doc else True
        
        # price_monthly değerini güvenli şekilde al
        price_monthly = plan.get('price_monthly', 0)
        if not isinstance(price_monthly, (int, float)) or price_monthly < 0:
            logger.error(f"Geçersiz price_monthly değeri: {price_monthly}, plan_id={plan_request.plan_id}")
            raise HTTPException(status_code=500, detail="Plan fiyatı geçersiz")
        
        if is_first_month:
            price_to_pay = price_monthly * 0.75  # %25 indirim
        else:
            price_to_pay = price_monthly
        
        # Stripe için fiyatı pence/cent formatına çevir (GBP için)
        # TL'den GBP'ye çevrim (yaklaşık 1 GBP = 35 TL)
        price_gbp = price_to_pay / 35  # Basit çevrim
        payment_amount_pence = int(price_gbp * 100)  # GBP pence cinsinden
        
        # 3. E-posta kontrolü
        user_email = (current_user.username or "").strip().lower()
        if not user_email or "@" not in user_email:
            logger.error(f"Geçersiz email (kullanıcı: {current_user.username}): {user_email}")
            raise HTTPException(status_code=400, detail="Geçerli bir e-posta adresi gerekli")
        
        # 4. Stripe Checkout Session oluştur
        plan_name = plan.get('name', 'Plan')
        
        stripe_result = create_checkout_session(
            user_id=current_user.organization_id,
            plan_id=plan_request.plan_id,
            price_amount=payment_amount_pence,
            plan_name=plan_name,
            user_email=user_email
        )
        
        if not stripe_result:
            logger.error("Stripe checkout session oluşturulamadı")
            raise HTTPException(status_code=500, detail="Ödeme oturumu oluşturulamadı")
        
        # 5. Payment log oluştur
        await db.payment_logs.insert_one({
            "session_id": stripe_result['session_id'],
            "organization_id": current_user.organization_id,
            "user_id": current_user.username,
            "plan_id": plan_request.plan_id,
            "status": "pending",
            "amount": price_to_pay,
            "amount_gbp": price_gbp,
            "is_first_month": is_first_month,
            "payment_provider": "stripe",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"Stripe checkout session oluşturuldu: {stripe_result['session_id']} - {plan_request.plan_id}")
        
        return {
            "checkout_url": stripe_result['checkout_url'],
            "session_id": stripe_result['session_id']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stripe checkout session oluşturma hatası: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sunucu hatası: {str(e)}")

async def handle_stripe_webhook_handler(request: Request) -> Response:
    """Stripe webhook - Ödeme durumu değişikliklerini işle"""
    try:
        # Webhook payload'ını al
        payload = await request.body()
        signature = request.headers.get('stripe-signature')
        
        if not signature:
            logger.warning("Stripe webhook imzası eksik")
            return Response(content="Missing signature", status_code=400)
        
        # Webhook event'ini parse et ve doğrula
        event = parse_webhook_event(payload, signature)
        if not event:
            logger.warning("Stripe webhook doğrulama başarısız")
            return Response(content="Invalid signature", status_code=400)
        
        event_type = event['type']
        logger.info(f"Stripe webhook alındı: {event_type}")
        
        # Sadece ilgilendiğimiz event'leri işle
        if event_type == 'checkout.session.completed':
            session = event['data']['object']
            session_id = session['id']
            customer_email = session.get('customer_email')
            
            logger.info(f"Checkout session tamamlandı: {session_id}")
            
            # Payment log'u güncelle
            db = await get_db_from_request(request)
            payment_log = await db.payment_logs.find_one({"session_id": session_id})
            
            if payment_log:
                organization_id = payment_log['organization_id']
                plan_id = payment_log['plan_id']
                
                # Organization plan'ını güncelle
                update_data = {
                    "plan_id": plan_id,
                    "status": "active",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "subscription_id": session.get('subscription'),
                    "customer_id": session.get('customer'),
                    "payment_provider": "stripe"
                }
                
                # İlk ay indirimi uygulandıysa, bir sonraki ödemede normal fiyat
                if payment_log.get('is_first_month', True):
                    update_data['is_first_month'] = False
                
                await db.organization_plans.update_one(
                    {"organization_id": organization_id},
                    {"$set": update_data}
                )
                
                # Payment log'u güncelle
                await db.payment_logs.update_one(
                    {"session_id": session_id},
                    {"$set": {
                        "status": "completed",
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "stripe_customer_id": session.get('customer'),
                        "stripe_subscription_id": session.get('subscription')
                    }}
                )
                
                logger.info(f"Stripe ödeme başarılı: {session_id} - Plan güncellendi. Organization: {organization_id}, Plan: {plan_id}")

                # === Meta CAPI: Purchase event (server-side) ===
                # event_id = `stripe-{session_id}` → frontend success page'i de aynı ID
                # ile Pixel.track('Purchase', ..., { eventID }) çağırırsa Meta dedupe eder.
                try:
                    from meta_capi_service import get_meta_capi_service

                    business_name = None
                    try:
                        org_settings = await db.settings.find_one({"organization_id": organization_id})
                        if org_settings:
                            business_name = org_settings.get("company_name")
                    except Exception:
                        pass

                    amount_total = session.get("amount_total")  # minor units
                    currency = (session.get("currency") or "try").upper()
                    value = (amount_total / 100.0) if isinstance(amount_total, (int, float)) else payment_log.get("amount")

                    # Kullanıcı bilgilerini zenginleştir (email + phone + isim)
                    purchase_user_data = {}
                    if customer_email:
                        purchase_user_data["em"] = customer_email
                    support_phone = None
                    admin_full_name = None
                    if org_settings:
                        support_phone = org_settings.get("support_phone")
                    # Admin kullanıcının ismini al
                    try:
                        admin_user = await db.users.find_one(
                            {"organization_id": organization_id, "role": "admin"},
                            {"full_name": 1, "username": 1, "_id": 0}
                        )
                        if admin_user:
                            admin_full_name = admin_user.get("full_name")
                            if not customer_email and admin_user.get("username"):
                                purchase_user_data["em"] = admin_user["username"]
                    except Exception:
                        pass
                    if support_phone:
                        purchase_user_data["ph"] = support_phone
                    if admin_full_name:
                        from meta_capi_service import split_full_name
                        name_parts = split_full_name(admin_full_name)
                        if name_parts.get("fn"):
                            purchase_user_data["fn"] = name_parts["fn"]
                        if name_parts.get("ln"):
                            purchase_user_data["ln"] = name_parts["ln"]

                    capi = get_meta_capi_service()
                    if capi.enabled:
                        capi.send_event(
                            event_name="Purchase",
                            event_id=f"stripe-{session_id}",
                            event_source_url=session.get("success_url") or None,
                            action_source="website",
                            user_data=purchase_user_data,
                            custom_data={
                                "content_name": business_name or plan_id,
                                "content_ids": [plan_id],
                                "content_type": "subscription",
                                "value": value,
                                "currency": currency,
                                "order_id": session_id,
                            },
                            external_id=organization_id,
                        )
                except Exception as capi_err:
                    logger.warning(f"Meta CAPI Purchase event hatası: {capi_err}")
            else:
                logger.warning(f"Payment log bulunamadı: {session_id}")
        
        elif event_type == 'invoice.payment_succeeded':
            # Recurring payment başarılı
            invoice = event['data']['object']
            subscription_id = invoice['subscription']
            
            logger.info(f"Recurring payment başarılı: {subscription_id}")
            
            # Subscription'a göre organization'ı bul ve plan süresini uzat
            db = await get_db_from_request(request)
            org_plan = await _find_org_plan_by_subscription(db, subscription_id)

            if not org_plan:
                logger.warning(
                    f"invoice.payment_succeeded: subscription_id={subscription_id} "
                    f"için organization_plan bulunamadı, süre uzatma atlanıyor."
                )
            else:
                # Bir sonraki ödeme tarihini Stripe'ın faturalama döngüsünden al.
                # Python ile manuel timedelta EKLEME — DB ile Stripe periyodu
                # zamanla senkron dışı kalmasın diye doğrudan payload'daki
                # fatura kalemi period.end (Unix timestamp) kullanılır.
                period_end_ts = None
                try:
                    lines = (invoice.get('lines') or {}).get('data') or []
                    if lines:
                        period_end_ts = (lines[0].get('period') or {}).get('end')
                    # Fallback: invoice seviyesindeki period_end
                    if period_end_ts is None:
                        period_end_ts = invoice.get('period_end')
                except Exception:
                    period_end_ts = None

                if period_end_ts:
                    next_billing = datetime.fromtimestamp(period_end_ts, tz=timezone.utc)
                else:
                    # Güvenlik ağı: timestamp yoksa kullanıcıyı kilitlememek için
                    # 30 gün ekle ve uyarı logla.
                    logger.warning(
                        f"invoice.payment_succeeded: period.end bulunamadı, "
                        f"30 günlük fallback uygulanıyor. subscription_id={subscription_id}"
                    )
                    next_billing = datetime.now(timezone.utc) + timedelta(days=30)

                # organization_id üzerinden güncelle ve abonelik alanlarını
                # tutarlı hale getir (subscription_id geçmişte None kalmış olabilir).
                await db.organization_plans.update_one(
                    {"organization_id": org_plan.get("organization_id")},
                    {"$set": {
                        "status": "active",
                        "subscription_id": subscription_id,
                        "stripe_subscription_id": subscription_id,
                        "next_billing_date": next_billing.isoformat(),
                        "last_payment_date": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                logger.info(
                    f"Recurring payment işlendi: org={org_plan.get('organization_id')} "
                    f"subscription_id={subscription_id} - next_billing_date={next_billing.isoformat()}"
                )

                # Yenileme ödemesini payment_logs'a kaydet (SuperAdmin MRR/Toplam Ciro
                # bu koleksiyondan hesaplanır). Fatura ID ile idempotent — aynı webhook
                # iki kez gelirse çift kayıt oluşmaz.
                invoice_id = invoice.get('id')
                amount_paid_minor = invoice.get('amount_paid')
                if amount_paid_minor is None:
                    amount_paid_minor = invoice.get('amount_due') or 0
                renewal_amount = amount_paid_minor / 100
                renewal_currency = (invoice.get('currency') or 'try').upper()
                created_iso = datetime.now(timezone.utc).isoformat()
                if period_end_ts:
                    # Fatura döneminin başlangıcını created_at olarak kullan (doğru tarih)
                    line_period = (lines[0].get('period') or {}) if lines else {}
                    period_start_ts = line_period.get('start') or invoice.get('period_start')
                    if period_start_ts:
                        created_iso = datetime.fromtimestamp(period_start_ts, tz=timezone.utc).isoformat()

                existing_log = None
                if invoice_id:
                    existing_log = await db.payment_logs.find_one({"stripe_invoice_id": invoice_id})
                if existing_log:
                    logger.info(
                        f"invoice.payment_succeeded: invoice_id={invoice_id} için payment_log "
                        f"zaten mevcut, çift kayıt oluşturulmadı."
                    )
                else:
                    await db.payment_logs.insert_one({
                        "organization_id": org_plan.get("organization_id"),
                        "plan_id": org_plan.get("plan_id"),
                        "status": "active",
                        "amount": renewal_amount,
                        "currency": renewal_currency,
                        "billing_cycle": org_plan.get("billing_cycle", "monthly"),
                        "payment_provider": "stripe",
                        "payment_type": "renewal",
                        "stripe_subscription_id": subscription_id,
                        "stripe_invoice_id": invoice_id,
                        "created_at": created_iso,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    })
                    logger.info(
                        f"Yenileme payment_log kaydedildi: org={org_plan.get('organization_id')} "
                        f"amount={renewal_amount} {renewal_currency} invoice_id={invoice_id}"
                    )
        
        elif event_type == 'invoice.payment_failed':
            # Recurring payment başarısız — dunning bildirimi
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')

            logger.warning(f"Recurring payment başarısız: {subscription_id}")

            db = await get_db_from_request(request)

            # 1) Aboneliğe bağlı işletmeyi bul
            org_plan = await _find_org_plan_by_subscription(db, subscription_id)
            if not org_plan:
                logger.warning(
                    f"invoice.payment_failed: subscription_id={subscription_id} "
                    f"için organization_plan bulunamadı, dunning atlanıyor."
                )
            else:
                organization_id = org_plan.get("organization_id")

                # İşletme adını settings'ten çek
                org_settings = await db.settings.find_one({"organization_id": organization_id}) or {}
                company_name = (
                    org_settings.get("company_name")
                    or org_settings.get("business_name")
                    or "İşletmeniz"
                )

                # 2) Stripe payload'undan dinamik ödeme verilerini ayıkla
                amount_due_minor = invoice.get('amount_due') or 0
                amount_due = amount_due_minor / 100
                currency = (invoice.get('currency') or 'try').upper()
                hosted_invoice_url = invoice.get('hosted_invoice_url')
                customer_email = invoice.get('customer_email')

                # Fatura e-postası yoksa, işletmenin admin kullanıcısına düş
                if not customer_email:
                    admin_user = await db.users.find_one(
                        {"organization_id": organization_id, "role": "admin"}
                    )
                    if admin_user:
                        customer_email = admin_user.get("username")

                amount_str = f"{amount_due:,.2f}"
                now_iso = datetime.now(timezone.utc).isoformat()

                if hosted_invoice_url:
                    await db.organization_plans.update_one(
                        {"organization_id": organization_id},
                        {"$set": {
                            "hosted_invoice_url": hosted_invoice_url,
                            "dunning_updated_at": now_iso,
                        }},
                    )

                # 3a) SuperAdmin bildirimi — her fail'de (operasyonel)
                try:
                    sa_subject = f"[Kritik] Abonelik Yenileme Başarısız: {company_name}"
                    sa_html = f"""
<h2 style="color:#ef4444;margin-top:0;">Abonelik Yenileme Başarısız</h2>
<p><strong>{company_name}</strong> işletmesinin abonelik yenileme ödemesi başarısız oldu.</p>
<table style="border-collapse:collapse;font-size:14px;margin:16px 0;">
  <tr><td style="padding:4px 12px;"><strong>İşletme</strong></td><td>{company_name}</td></tr>
  <tr><td style="padding:4px 12px;"><strong>Organization ID</strong></td><td><code>{organization_id}</code></td></tr>
  <tr><td style="padding:4px 12px;"><strong>Kesilmesi gereken tutar</strong></td><td>{amount_str} {currency}</td></tr>
  <tr><td style="padding:4px 12px;"><strong>Subscription ID</strong></td><td><code>{subscription_id}</code></td></tr>
</table>
<p>Stripe otomatik retry işlemlerine devam ediyor.</p>
"""
                    await send_email(
                        to_email=SUPERADMIN_ALERT_EMAIL,
                        subject=sa_subject,
                        html_content=sa_html,
                        to_name="PLANN SuperAdmin",
                    )
                except Exception as e:
                    logger.error(f"invoice.payment_failed: SuperAdmin e-postası gönderilemedi: {e}")

                # 3b) İşletme sahibi — yalnızca ilk fail (Stripe dunning spam'ini kes)
                already_sent = org_plan.get("grace_email_sent") is True
                if customer_email and not already_sent:
                    try:
                        admin_user = await db.users.find_one(
                            {"organization_id": organization_id, "role": "admin"},
                            {"full_name": 1, "language": 1, "username": 1},
                        ) or {}
                        lang = (admin_user.get("language") or "").strip().lower()
                        if lang not in ("en", "tr"):
                            phone = (org_settings.get("support_phone") or "")
                            lang = "en" if phone.startswith("+44") else "tr"
                        pay_url = hosted_invoice_url or cta_for_lang(lang)
                        owner_name = admin_user.get("full_name") or company_name
                        owner_subject, owner_html = build_grace_period_email(
                            _brand_email, lang, owner_name, pay_url,
                        )
                        sent_ok = await send_email(
                            to_email=customer_email,
                            subject=owner_subject,
                            html_content=owner_html,
                            to_name=owner_name,
                        )
                        if sent_ok:
                            await db.organization_plans.update_one(
                                {"organization_id": organization_id},
                                {"$set": {
                                    "grace_email_sent": True,
                                    "grace_email_sent_at": now_iso,
                                    "grace_email_lang": lang,
                                }},
                            )
                    except Exception as e:
                        logger.error(f"invoice.payment_failed: İşletme sahibi e-postası gönderilemedi: {e}")
                elif already_sent:
                    logger.info(
                        f"invoice.payment_failed: grace e-postası zaten gitmiş, atlanıyor org={organization_id}"
                    )
                else:
                    logger.warning(
                        f"invoice.payment_failed: org={organization_id} için müşteri e-postası "
                        f"bulunamadı, işletme sahibi bilgilendirilemedi."
                    )

        elif event_type == 'customer.subscription.deleted':
            # Stripe tüm retry'leri tüketip aboneliği iptal etti — sessizce kapat
            subscription = event['data']['object']
            subscription_id = subscription.get('id')

            logger.info(f"Subscription iptal edildi (Stripe): {subscription_id}")

            db = await get_db_from_request(request)
            org_plan = await _find_org_plan_by_subscription(db, subscription_id)

            if not org_plan:
                logger.warning(
                    f"customer.subscription.deleted: subscription_id={subscription_id} "
                    f"için organization_plan bulunamadı, işlem atlanıyor."
                )
            else:
                organization_id = org_plan.get("organization_id")
                now_iso = datetime.now(timezone.utc).isoformat()

                # Dunning sonrası iptalse (grace maili gitmişse) suspended mailini
                # düşürmeden ÖNCE gönder; plan trial+canceled olunca scheduler yakalayamaz.
                if (
                    org_plan.get("grace_email_sent") is True
                    and org_plan.get("suspended_email_sent") is not True
                ):
                    try:
                        org_settings = await db.settings.find_one(
                            {"organization_id": organization_id}
                        ) or {}
                        admin_user = await db.users.find_one(
                            {"organization_id": organization_id, "role": "admin"},
                            {"username": 1, "full_name": 1, "language": 1},
                        ) or {}
                        to_email = (admin_user.get("username") or "").strip()
                        if "@" in to_email:
                            lang = (admin_user.get("language") or "").strip().lower()
                            if lang not in ("en", "tr"):
                                phone = (org_settings.get("support_phone") or "")
                                lang = "en" if phone.startswith("+44") else "tr"
                            pay_url = (
                                (org_plan.get("hosted_invoice_url") or "").strip()
                                or cta_for_lang(lang)
                            )
                            owner_name = admin_user.get("full_name") or org_settings.get("company_name") or ""
                            subj, html = build_suspended_email(_brand_email, lang, owner_name, pay_url)
                            sent_ok = await send_email(
                                to_email=to_email, subject=subj, html_content=html, to_name=owner_name,
                            )
                            if sent_ok:
                                await db.organization_plans.update_one(
                                    {"organization_id": organization_id},
                                    {"$set": {
                                        "suspended_email_sent": True,
                                        "suspended_email_sent_at": now_iso,
                                    }},
                                )
                    except Exception as e:
                        logger.error(
                            f"customer.subscription.deleted: suspended e-postası gönderilemedi: {e}"
                        )

                # Planı trial'a düşür, durumu canceled yap ve abonelik kalıntılarını temizle
                await db.organization_plans.update_one(
                    {"organization_id": organization_id},
                    {"$set": {
                        "plan_id": "tier_trial",
                        "status": "canceled",
                        "next_billing_date": None,
                        "next_payment_date": None,
                        "stripe_subscription_id": None,
                        "subscription_id": None,
                        "updated_at": now_iso,
                    }},
                )

                logger.info(
                    f"customer.subscription.deleted: org={organization_id} planı tier_trial'a "
                    f"düşürüldü, status=canceled, abonelik alanları temizlendi. "
                    f"subscription_id={subscription_id}"
                )

        return Response(content="OK", status_code=200)
        
    except Exception as e:
        logger.error(f"Stripe webhook işleme hatası: {e}", exc_info=True)
        return Response(content="ERROR", status_code=500)
