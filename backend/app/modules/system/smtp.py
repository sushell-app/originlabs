"""Encrypted SMTP client configuration, validation and outbound notification delivery."""

import asyncio
import smtplib
import ssl
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret
from app.modules.identity.models import User
from app.modules.system.models import SmtpConfig, SystemNotification

_FORBIDDEN_HOST_CHARS = set(";&|`$><\n\r\t\0'\" /\\")


def validate_smtp_host(host: str) -> str:
    """Validate an SMTP hostname without spaces or shell/header control characters."""
    cleaned = host.strip()
    if not cleaned:
        raise ValueError("El servidor SMTP (host) es obligatorio.")
    if any(ch in _FORBIDDEN_HOST_CHARS for ch in cleaned):
        raise ValueError("El host SMTP contiene caracteres inválidos.")
    return cleaned


def sanitize_header_value(value: str, label: str) -> str:
    """Reject CR/LF sequences to prevent SMTP header injection."""
    cleaned = value.strip()
    if "\r" in cleaned or "\n" in cleaned or "\0" in cleaned:
        raise ValueError(f"El campo {label} contiene saltos de línea inválidos.")
    return cleaned


def build_email_message(
    *,
    from_name: str,
    from_email: str,
    to_email: str,
    subject: str,
    body_text: str,
) -> EmailMessage:
    """Construct a sanitized UTF-8 EmailMessage ready for SMTP delivery."""
    safe_from_email = sanitize_header_value(from_email, "from_email")
    safe_from_name = sanitize_header_value(from_name, "from_name")
    safe_to = sanitize_header_value(to_email, "to_email")
    safe_subject = sanitize_header_value(subject, "subject")

    msg = EmailMessage()
    msg["From"] = f"{safe_from_name} <{safe_from_email}>" if safe_from_name else safe_from_email
    msg["To"] = safe_to
    msg["Subject"] = safe_subject
    msg.set_content(body_text, subtype="plain", charset="utf-8")
    return msg


def send_smtp_email_sync(
    config: SmtpConfig,
    *,
    to_email: str,
    subject: str,
    body_text: str,
) -> None:
    """Deliver a single email synchronously using configured SMTP/TLS settings."""
    host = validate_smtp_host(config.host)
    if not config.from_email.strip():
        raise ValueError("El correo remitente (From) es obligatorio.")
    if config.use_tls and config.use_ssl:
        raise ValueError("No puedes activar STARTTLS y SSL directo simultáneamente.")

    msg = build_email_message(
        from_name=config.from_name,
        from_email=config.from_email,
        to_email=to_email,
        subject=subject,
        body_text=body_text,
    )
    password = decrypt_secret(config.encrypted_password) if config.encrypted_password else ""
    tls_context = ssl.create_default_context()

    if config.use_ssl:
        with smtplib.SMTP_SSL(host, config.port, timeout=12, context=tls_context) as server:
            if config.username and password:
                server.login(config.username, password)
            server.send_message(msg)
        return

    with smtplib.SMTP(host, config.port, timeout=12) as server:
        server.ehlo()
        if config.use_tls:
            server.starttls(context=tls_context)
            server.ehlo()
        if config.username and password:
            server.login(config.username, password)
        server.send_message(msg)


async def get_or_create_smtp_config(db: AsyncSession) -> SmtpConfig:
    """Load singleton SmtpConfig row, creating defaults if missing."""
    config = (
        await db.execute(select(SmtpConfig).where(SmtpConfig.id == 1))
    ).scalar_one_or_none()
    if config is None:
        config = SmtpConfig(id=1)
        db.add(config)
        await db.flush()
    return config


async def send_update_notification_emails(
    db: AsyncSession,
    notification: SystemNotification,
) -> None:
    """Best-effort send release update alert emails to all active instance admins."""
    config = await get_or_create_smtp_config(db)
    if (
        not config.enabled
        or not config.notify_updates
        or not config.host.strip()
        or not config.from_email.strip()
    ):
        return

    admins = (
        await db.execute(
            select(User.email).where(User.is_instance_admin.is_(True), User.is_active.is_(True))
        )
    ).scalars().all()

    notes_line = (
        f"\nNotas de versión: {notification.release_notes_url}"
        if notification.release_notes_url
        else ""
    )
    body = (
        f"{notification.title}\n\n"
        f"{notification.message}{notes_line}\n\n"
        "Puedes revisar y aplicar la actualización desde Notificaciones en OriginLabs."
    )

    for admin_email in admins:
        try:
            await asyncio.to_thread(
                send_smtp_email_sync,
                config,
                to_email=admin_email,
                subject=f"[OriginLabs] {notification.title}",
                body_text=body,
            )
        except (OSError, smtplib.SMTPException, ValueError):
            continue
