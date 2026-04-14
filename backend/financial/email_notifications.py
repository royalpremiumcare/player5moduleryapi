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
SENDER_EMAIL = "noreply@plannapp.co"

LOGO_URL = "https://plannapp.co/api/static/logo.png"
DASHBOARD_URL = "https://plannapp.co"


def _wrap_branded(body_html: str) -> str:
    """Wrap inner body HTML with the branded PLANN email shell (logo, border, footer)."""
    return f"""\
<html>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; line-height: 1.6; background-color: #f4f4f4;">
    <table width="100%" border="0" cellpadding="0" cellspacing="0">
        <tr>
            <td align="center" style="padding: 20px 0;">
                <table width="600" border="0" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                    <tr>
                        <td align="center" style="padding: 30px 0; background-color: #f9f9f9; border-bottom: 1px solid #e0e0e0; border-top-left-radius: 8px; border-top-right-radius: 8px;">
                            <img src="{LOGO_URL}" alt="PLANN Logo" style="max-width: 150px; height: auto;">
                        </td>
                    </tr>
                    <tr style="background-color: #ffffff;">
                        <td style="padding: 40px 30px; color: #333333; font-size: 16px;">
                            {body_html}
                        </td>
                    </tr>
                    <tr style="background-color: #f9f9f9;">
                        <td align="center" style="padding: 20px 30px; font-size: 12px; color: #888888; border-top: 1px solid #e0e0e0; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">
                            <p style="margin: 0;">&copy; 2025 PLANN. T&uuml;m haklar&iacute; sakl&iacute;d&iacute;r.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


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
    rail_label = "BACS" if payout_rail == "bacs" else "Wise Transfer"

    subject = f"Ödemeniz gönderildi — {amount_display}"
    body = f"""\
<h1 style="font-size: 24px; color: #10b981; margin-top: 0; text-align: center;">&#10003; Ödemeniz Yolda</h1>
<p>Merhaba {merchant_name},</p>
<p>
    <strong>{amount_display}</strong> tutarındaki ödemeniz <strong>{rail_label}</strong>
    üzerinden banka hesabınıza gönderildi.
</p>
<p style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 12px 16px; border-radius: 4px; color: #166534; font-size: 14px;">
    İşlem genellikle 1-2 iş günü içinde hesabınıza yansır.
</p>
<p style="text-align: center; margin-top: 30px; margin-bottom: 10px;">
    <a href="{DASHBOARD_URL}" target="_blank" style="background-color: #007bff; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold; display: inline-block;">
        Panoya Git
    </a>
</p>"""
    return _send_email(to_email, merchant_name, subject, _wrap_branded(body))


def send_payout_failed_email(
    to_email: str,
    merchant_name: str,
    amount_minor: int,
    base_currency: str,
    error_message: str = "",
) -> bool:
    amount_display = format_display(amount_minor, base_currency)

    error_block = ""
    if error_message:
        error_block = f'<p style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 12px 16px; border-radius: 4px; color: #991b1b; font-size: 14px;">Hata: {error_message}</p>'

    subject = f"Ödeme başarısız — {amount_display}"
    body = f"""\
<h1 style="font-size: 24px; color: #ef4444; margin-top: 0; text-align: center;">&#10007; Ödeme Gönderilemedi</h1>
<p>Merhaba {merchant_name},</p>
<p>
    <strong>{amount_display}</strong> tutarındaki ödemeniz gönderilemedi.
    Tutar cüzdanınıza iade edildi.
</p>
{error_block}
<p>Lütfen banka bilgilerinizi kontrol edin veya destek ekibimizle iletişime geçin.</p>
<p style="text-align: center; margin-top: 30px; margin-bottom: 10px;">
    <a href="{DASHBOARD_URL}" target="_blank" style="background-color: #007bff; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold; display: inline-block;">
        Panoya Git
    </a>
</p>"""
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
    body = f"""\
<h1 style="font-size: 24px; color: #f59e0b; margin-top: 0; text-align: center;">&#9888; Ödeme İtirazı</h1>
<p>Merhaba {merchant_name},</p>
<p>
    <strong>{amount_display}</strong> tutarındaki bir ödeme için müşteriniz
    itiraz (dispute) başlattı. İlgili tutar geçici olarak dondurulmuştur.
</p>
<p style="background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 4px; color: #92400e; font-size: 14px;">
    Dispute ID: <strong>{dispute_id}</strong>
</p>
<p>İtiraz süreci otomatik olarak yönetilmektedir. Sonuç hakkında bilgilendirileceksiniz.</p>
<p style="text-align: center; margin-top: 30px; margin-bottom: 10px;">
    <a href="{DASHBOARD_URL}" target="_blank" style="background-color: #007bff; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold; display: inline-block;">
        Panoya Git
    </a>
</p>"""
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
