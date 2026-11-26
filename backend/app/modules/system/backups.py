"""Encrypted restic backup configuration, validation and subprocess execution."""

import asyncio
import shutil
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret
from app.modules.system.models import BackupConfig, BackupSnapshot

BackupProvider = Literal["local", "s3"]
_FORBIDDEN_REPO_CHARS = set(";&|`$><\n\r\t\0'\"")


def validate_backup_repository(provider: BackupProvider, repository: str) -> str:
    """Validate and sanitize a restic repository location without allowing shell injection."""
    cleaned = repository.strip()
    if not cleaned:
        raise ValueError("La ruta o URI del repositorio de respaldo es obligatoria.")
    if any(ch in _FORBIDDEN_REPO_CHARS for ch in cleaned) or any(ch.isspace() for ch in cleaned):
        raise ValueError("El repositorio contiene caracteres inválidos o espacios.")

    if provider == "local":
        if not cleaned.startswith("/"):
            raise ValueError("El repositorio local debe ser una ruta absoluta (ej. /var/backups).")
        return cleaned

    if not (cleaned.startswith("s3:https://") or cleaned.startswith("s3:http://")):
        raise ValueError("El repositorio S3 debe iniciar con s3:https:// o s3:http://")
    return cleaned


def build_restic_env(
    *,
    repository: str,
    password: str,
    s3_access_key: str | None = None,
    s3_secret_key: str | None = None,
) -> dict[str, str]:
    """Build non-persistent subprocess env injecting restic credentials safely."""
    env = {
        "RESTIC_REPOSITORY": repository,
        "RESTIC_PASSWORD": password,
    }
    if s3_access_key:
        env["AWS_ACCESS_KEY_ID"] = s3_access_key
    if s3_secret_key:
        env["AWS_SECRET_ACCESS_KEY"] = s3_secret_key
    return env


async def run_restic_backup(
    db: AsyncSession,
    config: BackupConfig,
    *,
    trigger: str = "manual",
) -> BackupSnapshot:
    """Execute an encrypted restic backup without shell=True and record snapshot history."""
    now = datetime.now(UTC)
    snapshot = BackupSnapshot(
        status="running",
        trigger=trigger,
        repository=config.repository,
        summary="",
        started_at=now,
    )
    db.add(snapshot)
    await db.flush()

    if not config.repository or not config.encrypted_password:
        snapshot.status = "failed"
        snapshot.summary = "Configura repositorio y contraseña de cifrado antes de respaldar."
        snapshot.completed_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(snapshot)
        return snapshot

    restic_bin = shutil.which("restic")
    if restic_bin is None:
        snapshot.status = "failed"
        snapshot.summary = (
            "Binario 'restic' no encontrado en este contenedor. "
            "Instala restic en el entorno de ejecución para completar backups reales."
        )
        snapshot.completed_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(snapshot)
        return snapshot

    password = decrypt_secret(config.encrypted_password)
    s3_key = (
        decrypt_secret(config.encrypted_s3_access_key) if config.encrypted_s3_access_key else None
    )
    s3_secret = (
        decrypt_secret(config.encrypted_s3_secret_key) if config.encrypted_s3_secret_key else None
    )
    env = build_restic_env(
        repository=config.repository,
        password=password,
        s3_access_key=s3_key,
        s3_secret_key=s3_secret,
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            restic_bin,
            "backup",
            "/app",
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace").strip()
        if proc.returncode == 0:
            snapshot.status = "success"
            snapshot.summary = output[-400:] or "Respaldo completado correctamente."
        else:
            snapshot.status = "failed"
            snapshot.summary = (output[-400:] or f"restic salió con código {proc.returncode}")
    except OSError as exc:
        snapshot.status = "failed"
        snapshot.summary = f"No se pudo ejecutar restic: {exc}"

    config.last_backup_at = datetime.now(UTC)
    snapshot.completed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot
