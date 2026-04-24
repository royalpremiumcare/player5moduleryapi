"""
PLANN v2 — Extended Notification Templates (Brevo email + Slack).

Covers failure / status templates introduced in plan Bölüm 17:
  - payment_failed, threshold_not_met, payout_delayed, payout_failed,
    refund_approved, refund_rejected, dispute_opened, dispute_resolved,
    wallet_payout_stopped.

Also: Slack webhook helpers (SLACK_WEBHOOK_URL + SLACK_WEBHOOK_CRITICAL_URL).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests

from .email_notifications import _send_email, _wrap_branded, format_display

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SLACK_WEBHOOK_CRITICAL_URL = os.getenv("SLACK_WEBHOOK_CRITICAL_URL", "")

DASHBOARD_URL = "https://plannapp.co"


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------

def send_slack(message: str, *, critical: bool = False, fields: Optional[Dict[str, Any]] = None) -> bool:
    url = SLACK_WEBHOOK_CRITICAL_URL if critical else SLACK_WEBHOOK_URL
    if not url:
        logger.debug("slack webhook not configured (critical=%s), skipping", critical)
        return False
    prefix = ":rotating_light: *KRİTİK*\n" if critical else ""
    text = f"{prefix}{message}"
    if fields:
        field_lines = "\n".join([f"• *{k}*: {v}" for k, v in fields.items()])
        text = f"{text}\n{field_lines}"
    try:
        resp = requests.post(url, json={"text": text}, timeout=5)
        return resp.ok
    except Exception as e:
        logger.error("slack send failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Email templates — failure / status
# ---------------------------------------------------------------------------

def send_payment_failed_email(
    to_email: str, recipient_name: str, amount_minor: int, currency: str,
    service_name: str = "", retry_url: str = "",
) -> bool:
    subject = "Ödeme alınamadı / Payment could not be processed"
    amount = format_display(amount_minor, currency)
    body = f"""
<p>Merhaba <strong>{recipient_name}</strong>,</p>
<p>{service_name or 'Hizmetiniz'} için <strong>{amount}</strong> tutarındaki ödeme başarısız oldu.</p>
<p>Kartınızı kontrol edip tekrar deneyebilirsiniz:</p>
<p><a href="{retry_url or DASHBOARD_URL}" style="background:#111;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;">Yeniden Dene</a></p>
<hr><p style="color:#888">Hello <strong>{recipient_name}</strong>, the payment of {amount} for {service_name or 'your service'} failed. Please retry.</p>
"""
    return _send_email(to_email, recipient_name, subject, _wrap_branded(body))


def send_threshold_not_met_email(
    to_email: str, merchant_name: str, remaining_minor: int,
    currency: str, next_batch_date: str,
) -> bool:
    subject = "Ödeme eşiğine ulaşılmadı / Payout threshold not met"
    remaining = format_display(remaining_minor, currency)
    body = f"""
<p>Merhaba <strong>{merchant_name}</strong>,</p>
<p>Bu haftaki ödeme aktarımı için eşiğe ulaşmanıza <strong>{remaining}</strong> kaldı.</p>
<p>Eşiği aştığınızda bir sonraki Çarşamba ({next_batch_date}) ödemeniz hazırlanır.</p>
<hr><p style="color:#888">This week's payout threshold not met — {remaining} remaining.</p>
"""
    return _send_email(to_email, merchant_name, subject, _wrap_branded(body))


def send_payout_delayed_email(
    to_email: str, merchant_name: str, amount_minor: int, currency: str, batch_id: str,
) -> bool:
    subject = "Ödemeniz ertelendi / Your payout is delayed"
    amount = format_display(amount_minor, currency)
    body = f"""
<p>Merhaba <strong>{merchant_name}</strong>,</p>
<p><strong>{amount}</strong> tutarındaki ödemeniz ({batch_id}) sistem onayı bekliyor. En kısa sürede işleme alınacaktır.</p>
<hr><p style="color:#888">Your payout of {amount} is awaiting admin approval.</p>
"""
    return _send_email(to_email, merchant_name, subject, _wrap_branded(body))


def send_payout_failed_v2_email(
    to_email: str, merchant_name: str, amount_minor: int, currency: str,
    batch_id: str, error_code: str = "",
) -> bool:
    subject = "Ödeme başarısız / Payout failed"
    amount = format_display(amount_minor, currency)
    body = f"""
<p>Merhaba <strong>{merchant_name}</strong>,</p>
<p><strong>{amount}</strong> tutarındaki ödemeniz ({batch_id}) teknik bir sorun nedeniyle yapılamadı.</p>
<p>Ekibimiz durumu inceleyip en kısa sürede tekrar deneyecektir.</p>
<p style="color:#888">Hata kodu: <code>{error_code or 'unknown'}</code></p>
<hr><p style="color:#888">Payout of {amount} failed.</p>
"""
    return _send_email(to_email, merchant_name, subject, _wrap_branded(body))


def send_refund_approved_email(
    to_email: str, recipient_name: str, amount_minor: int, currency: str,
    reason: str = "",
) -> bool:
    subject = "İade onaylandı / Refund approved"
    amount = format_display(amount_minor, currency)
    body = f"""
<p>Merhaba <strong>{recipient_name}</strong>,</p>
<p><strong>{amount}</strong> tutarındaki iade talebiniz onaylandı ve işleme alındı.</p>
<p>Tutar 5-10 iş günü içinde kartınıza geri yatırılacaktır.</p>
{f'<p>Not: {reason}</p>' if reason else ''}
<hr><p style="color:#888">Refund of {amount} approved and processed.</p>
"""
    return _send_email(to_email, recipient_name, subject, _wrap_branded(body))


def send_refund_rejected_email(
    to_email: str, recipient_name: str, amount_minor: int, currency: str, reason: str,
) -> bool:
    subject = "İade talebi reddedildi / Refund request rejected"
    amount = format_display(amount_minor, currency)
    body = f"""
<p>Merhaba <strong>{recipient_name}</strong>,</p>
<p><strong>{amount}</strong> tutarındaki iade talebiniz reddedildi.</p>
<p><strong>Sebep:</strong> {reason}</p>
<hr><p style="color:#888">Refund request of {amount} rejected.</p>
"""
    return _send_email(to_email, recipient_name, subject, _wrap_branded(body))


def send_dispute_opened_email(
    to_email: str, merchant_name: str, amount_minor: int, currency: str,
    dispute_id: str, reason: str = "",
) -> bool:
    subject = "İtiraz açıldı / Dispute opened"
    amount = format_display(amount_minor, currency)
    body = f"""
<p>Merhaba <strong>{merchant_name}</strong>,</p>
<p>Bir müşteriniz <strong>{amount}</strong> tutarındaki ödemeye itiraz etti (dispute: {dispute_id}).</p>
<p>Bu tutar geçici olarak dondurulmuştur ve sonuçlanana kadar cüzdanınızdan kullanılamaz.</p>
{f'<p>Sebep: {reason}</p>' if reason else ''}
<hr><p style="color:#888">Dispute opened for {amount}.</p>
"""
    # Also alert SuperAdmin
    send_slack(
        f":warning: İtiraz (dispute) açıldı: {merchant_name}",
        critical=True,
        fields={"Tutar": amount, "Dispute ID": dispute_id, "Sebep": reason},
    )
    return _send_email(to_email, merchant_name, subject, _wrap_branded(body))


def send_dispute_resolved_email(
    to_email: str, merchant_name: str, amount_minor: int, currency: str,
    won: bool,
) -> bool:
    subject = (
        "İtiraz lehinize sonuçlandı / Dispute resolved (won)"
        if won else
        "İtiraz aleyhinize sonuçlandı / Dispute resolved (lost)"
    )
    amount = format_display(amount_minor, currency)
    body = f"""
<p>Merhaba <strong>{merchant_name}</strong>,</p>
<p><strong>{amount}</strong> tutarındaki itiraz <strong>{'lehinize' if won else 'aleyhinize'}</strong> sonuçlandı.</p>
<p>{'Tutar cüzdanınıza geri aktarıldı.' if won else 'Tutar cüzdanınızdan düşüldü.'}</p>
<hr><p style="color:#888">Dispute {('won' if won else 'lost')} — amount {amount}.</p>
"""
    return _send_email(to_email, merchant_name, subject, _wrap_branded(body))


def send_wallet_payout_stopped_email(
    to_email: str, merchant_name: str, debt_minor: int, currency: str, reason: str,
) -> bool:
    subject = "Ödemeleriniz durduruldu / Payouts suspended"
    debt = format_display(debt_minor, currency)
    body = f"""
<p>Merhaba <strong>{merchant_name}</strong>,</p>
<p>Cüzdanınızda <strong>{debt}</strong> tutarında bekleyen borç oluştu. Ödemeleriniz bu borç kapanana kadar durdurulmuştur.</p>
<p><strong>Sebep:</strong> {reason}</p>
<p>Gelecek tahsilatlarınız önce bu borcu kapatacaktır.</p>
<hr><p style="color:#888">Payouts suspended due to pending debt {debt}.</p>
"""
    return _send_email(to_email, merchant_name, subject, _wrap_branded(body))
