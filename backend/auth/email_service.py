"""Brevo SMTP transactional email sender for VibeVerse email verification.

Uses Brevo SMTP relay (smtp-relay.brevo.com:587 with STARTTLS) per the
Brevo SMTP integration playbook. The xsmtpsib-... key is the SMTP password;
the SMTP login (e.g. xxxxxx@smtp-brevo.com) is the username.
"""
import os
import ssl
import smtplib
import asyncio
from email.message import EmailMessage

from core.logging import logger

SMTP_HOST = os.environ.get("SMTP_HOST") or os.environ.get("BREVO_SMTP_HOST", "smtp-relay.brevo.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT") or os.environ.get("BREVO_SMTP_PORT", "587"))
SMTP_LOGIN = os.environ.get("SMTP_LOGIN") or os.environ.get("BREVO_SMTP_LOGIN", "")
SMTP_KEY = os.environ.get("SMTP_KEY") or os.environ.get("BREVO_SMTP_KEY", "")
FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL") or os.environ.get("BREVO_FROM_EMAIL", "")
FROM_NAME = os.environ.get("SMTP_FROM_NAME") or os.environ.get("BREVO_FROM_NAME", "VibeVerse")


def _is_configured() -> bool:
    return bool(SMTP_LOGIN and SMTP_KEY and FROM_EMAIL)


def _verification_html(name: str, code: str) -> str:
    safe_name = (name or "there").replace("<", "").replace(">", "")
    return f"""<!doctype html>
<html dir="rtl" lang="ar">
  <body style="margin:0;background:#07070d;font-family:'Segoe UI',Tahoma,Arial,sans-serif;">
    <div style="max-width:520px;margin:0 auto;padding:32px 20px;">
      <div style="text-align:center;margin-bottom:28px;">
        <span style="font-size:26px;font-weight:800;color:#ffffff;letter-spacing:-.5px;">
          Vibe<span style="background:linear-gradient(90deg,#6366F1,#A855F7);-webkit-background-clip:text;background-clip:text;color:transparent;">Verse</span>
        </span>
      </div>
      <div style="background:#0C0C14;border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:32px 28px;color:#E2E8F0;">
        <h1 style="font-size:20px;margin:0 0 8px;color:#fff;">أهلاً {safe_name} 👋</h1>
        <p style="font-size:14px;line-height:1.7;color:#94A3B8;margin:0 0 24px;">
          شكراً لتسجيلك في VibeVerse. استخدم الكود التالي لتفعيل حسابك. الكود صالح لمدة 15 دقيقة.
        </p>
        <div style="text-align:center;margin:0 0 24px;">
          <div style="display:inline-block;background:linear-gradient(90deg,rgba(99,102,241,.15),rgba(168,85,247,.15));border:1px solid rgba(168,85,247,.35);border-radius:14px;padding:18px 34px;">
            <span style="font-size:38px;font-weight:800;letter-spacing:12px;color:#fff;">{code}</span>
          </div>
        </div>
        <p style="font-size:12px;line-height:1.7;color:#64748B;margin:0;">
          إذا لم تقم بإنشاء هذا الحساب، يمكنك تجاهل هذه الرسالة بأمان.
        </p>
      </div>
      <p style="text-align:center;font-size:11px;color:#475569;margin-top:22px;">© VibeVerse — منصة الإبداع بالذكاء الاصطناعي</p>
    </div>
  </body>
</html>"""


def _send_sync(to_email: str, subject: str, text_body: str, html_body: str) -> None:
    if not _is_configured():
        raise RuntimeError("Brevo SMTP is not configured (missing env vars)")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(SMTP_LOGIN, SMTP_KEY)
        smtp.send_message(msg)


async def send_verification_email(to_email: str, name: str, code: str) -> None:
    """Send the 6-digit verification code. Runs blocking SMTP in a thread."""
    subject = "كود تفعيل حسابك في VibeVerse"
    text = (f"أهلاً {name},\n\nكود تفعيل حسابك هو: {code}\n"
            f"الكود صالح لمدة 15 دقيقة.\n\nVibeVerse")
    html = _verification_html(name, code)
    await asyncio.to_thread(_send_sync, to_email, subject, text, html)
    logger.info(f"Verification email sent to {to_email}")
