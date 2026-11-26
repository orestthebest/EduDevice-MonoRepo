"""
Mailversand (Ziel-M-1). Die API spricht nur mit dem Postfix auf demselben Server
(localhost:25, ohne Login - Postfix nimmt nur von localhost an). Postfix signiert mit DKIM
und stellt die Mail direkt beim Empfaenger zu.

Mit EDUDEVICE_MAIL_ENABLED=0 wird nichts verschickt: die Mail kommt nur in OUTBOX
(fuer Tests und lokale Entwicklung).
"""

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from app.core import config

log = logging.getLogger("edudevice.mail")
OUTBOX: list[EmailMessage] = []          # nur bei MAIL_ENABLED=0 benutzt


def _domain(address: str) -> str:
    return address.rsplit("@", 1)[-1].strip().lower()


def build(to: str, subject: str, text: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = config.MAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=_domain(config.MAIL_FROM.strip("<> ")))
    msg.set_content(text)                # text/plain, UTF-8 (Umlaute gehen)
    return msg


def send_mail(to: str, subject: str, text: str) -> bool:
    """Verschickt eine Mail. Gibt False zurueck, wenn sie nicht verschickt wurde.
    Fehler werden nur geloggt, nie an den Client weitergegeben (keine Infos nach aussen)."""
    if config.MAIL_ALLOWED_DOMAINS and _domain(to) not in config.MAIL_ALLOWED_DOMAINS:
        log.warning("Mail an Domain %s nicht erlaubt, nicht verschickt", _domain(to))
        return False
    msg = build(to, subject, text)
    if not config.MAIL_ENABLED:
        OUTBOX.append(msg)
        return True
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as smtp:
            smtp.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as e:
        log.error("Mail an %s fehlgeschlagen: %s", _domain(to), e)
        return False
