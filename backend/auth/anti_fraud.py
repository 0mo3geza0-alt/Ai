"""Anti multi-account utilities: disposable-email blocking, client IP
extraction, and per-IP / per-device account limits."""
import os
from fastapi import Request

MAX_ACCOUNTS_PER_IP = int(os.environ.get("MAX_ACCOUNTS_PER_IP", "3"))
MAX_ACCOUNTS_PER_DEVICE = int(os.environ.get("MAX_ACCOUNTS_PER_DEVICE", "2"))

# Common disposable / temporary email domains to block.
DISPOSABLE_DOMAINS = {
    "mailinator.com", "10minutemail.com", "guerrillamail.com", "guerrillamail.info",
    "guerrillamail.biz", "guerrillamail.net", "guerrillamail.org", "sharklasers.com",
    "grr.la", "temp-mail.org", "tempmail.com", "tempmailo.com", "tempmail.net",
    "tempr.email", "throwawaymail.com", "getnada.com", "nada.email", "maildrop.cc",
    "dispostable.com", "yopmail.com", "yopmail.net", "yopmail.fr", "trashmail.com",
    "trashmail.de", "mailnesia.com", "mytemp.email", "fakeinbox.com", "mohmal.com",
    "emailondeck.com", "tempinbox.com", "spam4.me", "mailcatch.com", "33mail.com",
    "anonbox.net", "burnermail.io", "tempmailaddress.com", "discard.email",
    "discardmail.com", "mailsac.com", "inboxkitten.com", "1secmail.com",
    "1secmail.org", "1secmail.net", "tempail.com", "vomoto.com", "minuteinbox.com",
    "moakt.com", "tmail.ws", "mailtemp.net", "luxusmail.org", "cs.email",
    "emlpro.com", "emltmp.com", "tempmail.plus", "fakemail.net", "getairmail.com",
    "instantemail.net", "trbvm.com", "dropmail.me", "10mail.org", "mail-temp.com",
}


def is_disposable_email(email: str) -> bool:
    domain = email.split("@")[-1].strip().lower()
    return domain in DISPOSABLE_DOMAINS


def get_client_ip(request: Request) -> str:
    """Extract the real client IP behind the Kubernetes ingress / proxy."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return request.client.host if request.client else "unknown"


def get_device_fingerprint(request: Request) -> str:
    return (request.headers.get("x-device-fingerprint") or "").strip()[:128]


async def check_account_limits(db, ip: str, device: str) -> None:
    """Raise HTTPException if IP/device already own too many verified accounts."""
    from fastapi import HTTPException
    if ip and ip != "unknown":
        ip_count = await db.users.count_documents({"signup_ip": ip, "email_verified": True})
        if ip_count >= MAX_ACCOUNTS_PER_IP:
            raise HTTPException(
                status_code=429,
                detail="تم إنشاء الحد الأقصى من الحسابات من هذه الشبكة. يرجى التواصل مع الدعم.",
            )
    if device:
        dev_count = await db.users.count_documents({"signup_device": device, "email_verified": True})
        if dev_count >= MAX_ACCOUNTS_PER_DEVICE:
            raise HTTPException(
                status_code=429,
                detail="تم إنشاء الحد الأقصى من الحسابات من هذا الجهاز. يرجى التواصل مع الدعم.",
            )
