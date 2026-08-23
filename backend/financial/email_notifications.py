"""
PLANN Financial Engine — Email Notifications

Uses Brevo (SendinBlue) API for transactional emails.
Covers: payout success, payout failure, dispute alerts,
reconciliation alerts, and KYC status updates.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

import requests

from .money import format_display

logger = logging.getLogger(__name__)

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "fatihsenyuz12@gmail.com")
SUPERADMIN_ALERT_EMAIL = "fatihsenyuz12@gmail.com"
SENDER_NAME = "PLANN"
SENDER_EMAIL = "info@plannapp.co"

LOGO_URL = "https://plannapp.co/api/static/logo.png"
DASHBOARD_URL = "https://plannapp.co"

# Premium marka tipografisi (server.py _brand_shell ile aynı dil).
_BRAND_FONT_SERIF = "Georgia, 'Times New Roman', Times, serif"
_BRAND_FONT_SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"


def _wrap_branded(body_html: str) -> str:
    """Gövde HTML'ini PLANN premium e-posta kabuğuna sarar (krem zemin, beyaz kart,
    tipografik 'P L A N N' başlık, minimalist alt bilgi). Tüm stiller inline."""
    year = datetime.now(timezone.utc).year
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#fbfbfa;color:#1a1a1a;-webkit-font-smoothing:antialiased;font-family:{_BRAND_FONT_SERIF};">
  <center style="width:100%;background-color:#fbfbfa;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;background-color:#fbfbfa;">
      <tr>
        <td align="center" style="padding:60px 16px;">
          <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:600px;margin:0 auto;background-color:#ffffff;border:1px solid #e5e5e3;box-shadow:0 4px 20px rgba(0,0,0,0.02);">
            <tr>
              <td style="padding:60px 50px 40px 50px;text-align:center;border-bottom:1px solid #f2f2f0;">
                <h1 style="margin:0;font-family:{_BRAND_FONT_SERIF};font-size:30px;font-weight:300;letter-spacing:10px;color:#1a1a1a;text-transform:uppercase;">P L A N N</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:50px 50px 40px 50px;">
                {body_html}
              </td>
            </tr>
            <tr>
              <td style="padding:40px 50px;text-align:center;font-family:{_BRAND_FONT_SANS};font-size:10px;letter-spacing:2px;color:#a3a3a0;text-transform:uppercase;border-top:1px solid #f2f2f0;">
                PLANNAPP LTD. ALL RIGHTS RESERVED. &copy; {year}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </center>
</body>
</html>"""


def _fin_body(*, badge="", statement="", paragraphs=None, meta_rows=None, button=None, note="", extra_html=""):
    """server.py _brand_body ile aynı premium gövde (financial modülü için bağımsız kopya)."""
    parts = []
    if badge:
        parts.append(
            f'<div style="font-family:{_BRAND_FONT_SANS};font-size:10px;letter-spacing:3px;'
            f'text-transform:uppercase;color:#8c8c88;margin:0 0 30px 0;text-align:center;font-weight:500;">{badge}</div>'
        )
    if statement:
        parts.append(
            f'<div style="font-family:{_BRAND_FONT_SERIF};font-size:23px;line-height:1.6;color:#1a1a1a;'
            f'text-align:center;margin:0 0 45px 0;font-weight:400;font-style:italic;">{statement}</div>'
        )
    for p in (paragraphs or []):
        parts.append(
            f'<p style="font-family:{_BRAND_FONT_SERIF};font-size:17px;line-height:1.75;color:#3a3a3a;margin:0 0 20px 0;">{p}</p>'
        )
    if meta_rows:
        rows = ""
        n = len(meta_rows)
        for i, (label, value) in enumerate(meta_rows):
            border = "" if i == n - 1 else "border-bottom:1px solid #f2f2f0;"
            rows += (
                f'<tr><td style="padding:18px 24px;{border}font-family:{_BRAND_FONT_SANS};font-size:11px;'
                f'text-transform:uppercase;letter-spacing:2px;color:#8c8c88;font-weight:500;width:30%;vertical-align:top;">{label}</td>'
                f'<td style="padding:18px 24px 18px 0;{border}font-family:{_BRAND_FONT_SERIF};font-size:16px;color:#1a1a1a;vertical-align:top;">{value}</td></tr>'
            )
        parts.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="width:100%;margin:12px 0 45px 0;border:1px solid #e5e5e3;border-collapse:collapse;">{rows}</table>'
        )
    if extra_html:
        parts.append(extra_html)
    if note:
        parts.append(
            f'<p style="font-family:{_BRAND_FONT_SANS};font-size:13px;line-height:1.6;color:#8c8c88;'
            f'margin:28px 0 0 0;padding-top:20px;border-top:1px solid #f2f2f0;">{note}</p>'
        )
    if button and button.get("url") and button.get("label"):
        parts.append(
            f'<div style="text-align:center;margin-top:40px;">'
            f'<a href="{button["url"]}" target="_blank" style="border:1px solid #1a1a1a;color:#1a1a1a;'
            f'text-decoration:none;padding:16px 42px;font-family:{_BRAND_FONT_SANS};font-size:11px;'
            f'font-weight:600;text-transform:uppercase;letter-spacing:3px;display:inline-block;">{button["label"]}</a></div>'
        )
    return "\n".join(parts)


def _send_email(
    to_email: str,
    to_name: str,
    subject: str,
    html_content: str,
) -> bool:
    """Send a transactional email via Brevo API."""
    if not BREVO_API_KEY:
        logger.warning("BREVO_API_KEY not set, skipping email to %s", to_email)
        return False

    payload = {
        "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject,
        "htmlContent": html_content,
    }

    try:
        resp = requests.post(
            BREVO_API_URL,
            json=payload,
            headers={
                "api-key": BREVO_API_KEY,
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        return False


# ---------------------------------------------------------------------------
# Merchant Notifications
# ---------------------------------------------------------------------------

def send_payout_success_email(
    to_email: str,
    merchant_name: str,
    amount_minor: int,
    base_currency: str,
    payout_rail: str,
) -> bool:
    amount_display = format_display(amount_minor, base_currency)
    rail_label = "BACS" if payout_rail == "bacs" else "Banka Transferi"

    subject = f"Ödemeniz gönderildi — {amount_display}"
    body = _fin_body(
        badge="Ödeme",
        statement="Ödemeniz yolda.",
        paragraphs=[
            f"Merhaba {merchant_name},",
            f"<strong>{amount_display}</strong> tutarındaki ödemeniz <strong>{rail_label}</strong> üzerinden banka hesabınıza gönderildi.",
            "İşlem aynı gün içinde hesabınıza yansır.",
        ],
        meta_rows=[
            ("Tutar", amount_display),
            ("Yöntem", rail_label),
        ],
        button={"label": "Panoya Git", "url": DASHBOARD_URL},
    )
    return _send_email(to_email, merchant_name, subject, _wrap_branded(body))


def send_payout_failed_email(
    to_email: str,
    merchant_name: str,
    amount_minor: int,
    base_currency: str,
    error_message: str = "",
) -> bool:
    amount_display = format_display(amount_minor, base_currency)

    meta = [("Tutar", amount_display)]
    if error_message:
        meta.append(("Hata", error_message))

    subject = f"Ödeme başarısız — {amount_display}"
    body = _fin_body(
        badge="Ödeme",
        statement="Ödeme gönderilemedi.",
        paragraphs=[
            f"Merhaba {merchant_name},",
            f"<strong>{amount_display}</strong> tutarındaki ödemeniz gönderilemedi. Tutar cüzdanınıza iade edildi.",
            "Lütfen banka bilgilerinizi kontrol edin veya destek ekibimizle iletişime geçin.",
        ],
        meta_rows=meta,
        button={"label": "Panoya Git", "url": DASHBOARD_URL},
    )
    return _send_email(to_email, merchant_name, subject, _wrap_branded(body))


def send_dispute_alert_email(
    to_email: str,
    merchant_name: str,
    amount_minor: int,
    base_currency: str,
    dispute_id: str,
) -> bool:
    amount_display = format_display(amount_minor, base_currency)

    subject = f"İtiraz (Dispute) bildirimi — {amount_display}"
    body = _fin_body(
        badge="İtiraz",
        statement="Bir ödeme için itiraz başlatıldı.",
        paragraphs=[
            f"Merhaba {merchant_name},",
            f"<strong>{amount_display}</strong> tutarındaki bir ödeme için müşteriniz itiraz (dispute) başlattı. İlgili tutar geçici olarak dondurulmuştur.",
            "İtiraz süreci otomatik olarak yönetilmektedir. Sonuç hakkında bilgilendirileceksiniz.",
        ],
        meta_rows=[
            ("Tutar", amount_display),
            ("Dispute ID", dispute_id),
        ],
        button={"label": "Panoya Git", "url": DASHBOARD_URL},
    )
    return _send_email(to_email, merchant_name, subject, _wrap_branded(body))


# ---------------------------------------------------------------------------
# SuperAdmin Alerts
# ---------------------------------------------------------------------------

def send_reconciliation_alert(
    discrepancies: List[Dict[str, Any]],
    report_date: str,
) -> bool:
    """
    Send daily reconciliation mismatch alert to SuperAdmin.
    Called by daily_reconciliation_job when any discrepancy is found.
    """
    if not discrepancies:
        return False

    rows = ""
    for d in discrepancies:
        rows += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #e5e7eb;">{d.get('organization_id', 'N/A')}</td>
            <td style="padding: 8px; border: 1px solid #e5e7eb;">{d.get('source', 'N/A')}</td>
            <td style="padding: 8px; border: 1px solid #e5e7eb;">{d.get('expected', 'N/A')}</td>
            <td style="padding: 8px; border: 1px solid #e5e7eb;">{d.get('actual', 'N/A')}</td>
            <td style="padding: 8px; border: 1px solid #e5e7eb; color: #ef4444; font-weight: bold;">{d.get('diff', 'N/A')}</td>
        </tr>
        """

    subject = f"PLANN Mutabakat Uyuşmazlığı — {report_date}"
    body = f"""\
<h1 style="font-size: 24px; color: #ef4444; margin-top: 0; text-align: center;">Günlük Mutabakat Uyuşmazlığı</h1>
<p>Tarih: <strong>{report_date}</strong></p>
<p>{len(discrepancies)} adet uyuşmazlık bulundu. 1 kuruş/pence bile olsa raporlanır.</p>
<table style="border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 14px;">
    <thead>
        <tr style="background: #f3f4f6;">
            <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: left;">Org ID</th>
            <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: left;">Kaynak</th>
            <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: left;">Beklenen</th>
            <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: left;">Gerçek</th>
            <th style="padding: 8px; border: 1px solid #e5e7eb; text-align: left;">Fark</th>
        </tr>
    </thead>
    <tbody>{rows}</tbody>
</table>
<p style="color: #6b7280;">Bu uyuşmazlıkları SuperAdmin panelinden inceleyebilirsiniz.</p>"""
    return _send_email(SUPERADMIN_ALERT_EMAIL, "PLANN SuperAdmin", subject, _wrap_branded(body))


def send_rate_spike_alert(
    old_rate: str,
    new_rate: str,
    change_pct: float,
    direction: str,
) -> bool:
    """Alert SuperAdmin about significant GBP/TRY rate change."""
    arrow = "&#x1F4C8;" if direction == "up" else "&#x1F4C9;"

    subject = f"GBP/TRY Kur Sıçraması — %{change_pct}"
    body = f"""\
<h1 style="font-size: 24px; color: #f59e0b; margin-top: 0; text-align: center;">{arrow} Kur Sıçraması Tespit Edildi</h1>
<p>GBP/TRY kurunda <strong>%{change_pct}</strong> {direction} yönlü değişim:</p>
<ul>
    <li>Önceki kur: <strong>{old_rate}</strong></li>
    <li>Yeni kur: <strong>{new_rate}</strong></li>
</ul>
<p style="background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 4px; color: #92400e; font-size: 14px;">
    TRY tier limitleri otomatik olarak güncellenmiştir (Currency Shield).
</p>"""
    return _send_email(SUPERADMIN_ALERT_EMAIL, "PLANN SuperAdmin", subject, _wrap_branded(body))


def send_kyc_pending_alert(
    organization_id: str,
    merchant_name: str,
) -> bool:
    """Alert SuperAdmin about new merchant pending KYC verification."""
    subject = f"Yeni KYC Onayı Bekliyor — {merchant_name}"
    body = f"""\
<h1 style="font-size: 24px; color: #f59e0b; margin-top: 0; text-align: center;">KYC Onayı Bekleyen İşletme</h1>
<p>Aşağıdaki işletme ödeme ayarlarını kaydetti ve KYC doğrulaması bekliyor:</p>
<ul>
    <li>İşletme: <strong>{merchant_name}</strong></li>
    <li>Org ID: <strong>{organization_id}</strong></li>
</ul>
<p style="text-align: center; margin-top: 30px; margin-bottom: 10px;">
    <a href="{DASHBOARD_URL}" target="_blank" style="background-color: #007bff; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold; display: inline-block;">
        SuperAdmin Paneli
    </a>
</p>"""
    return _send_email(SUPERADMIN_ALERT_EMAIL, "PLANN SuperAdmin", subject, _wrap_branded(body))


def send_aml_review_alert(
    organization_id: str,
    merchant_name: str,
    amount_minor: int,
    base_currency: str,
    flags: List[str],
) -> bool:
    """Alert SuperAdmin about AML-flagged payout."""
    amount_display = format_display(amount_minor, base_currency)
    flags_str = ", ".join(flags)

    subject = f"AML İnceleme Gerekli — {merchant_name} — {amount_display}"
    body = f"""\
<h1 style="font-size: 24px; color: #f59e0b; margin-top: 0; text-align: center;">AML İnceleme Gerekli</h1>
<p>Aşağıdaki payout talebi manuel inceleme gerektiriyor:</p>
<ul>
    <li>İşletme: <strong>{merchant_name}</strong> ({organization_id})</li>
    <li>Tutar: <strong>{amount_display}</strong></li>
    <li>Bayraklar: <strong>{flags_str}</strong></li>
</ul>
<p style="text-align: center; margin-top: 30px; margin-bottom: 10px;">
    <a href="{DASHBOARD_URL}" target="_blank" style="background-color: #007bff; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold; display: inline-block;">
        SuperAdmin Paneli
    </a>
</p>"""
    return _send_email(SUPERADMIN_ALERT_EMAIL, "PLANN SuperAdmin", subject, _wrap_branded(body))
