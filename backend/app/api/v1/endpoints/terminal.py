import asyncio
import logging
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import decode_access_token
from app.core.vault import vault
from app.models.device import Device
from app.models.user import User
from app.services.automation_engine import automation_engine
from app.services.vendor_profiles import get_vendor_profile

router = APIRouter()
logger = logging.getLogger(__name__)
_MAX_OUTPUT_CHARS = 100_000


@router.websocket("/devices/{device_id}")
async def read_only_terminal(websocket: WebSocket, device_id: int) -> None:
    """Provide an authenticated, allowlisted read-only command console for an enrolled device."""
    origin = websocket.headers.get("origin")
    if origin and origin not in settings.ALLOWED_ORIGINS:
        await websocket.close(code=4403, reason="Origin is not allowed.")
        return

    await websocket.accept()
    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        token = auth_message.get("token") if isinstance(auth_message, dict) else None
        if not isinstance(token, str) or not token:
            await websocket.close(code=4401, reason="Authentication is required.")
            return
        try:
            payload = decode_access_token(token)
        except Exception:
            await websocket.close(code=4401, reason="Invalid or expired token.")
            return

        username = payload.get("sub")
        async with AsyncSessionLocal() as db:
            user_result = await db.execute(select(User).where(User.username == username))
            user = user_result.scalar_one_or_none()
            if user is None or not user.is_active:
                await websocket.close(code=4401, reason="User is not active.")
                return
            if payload.get("role") != user.role or user.role not in ("admin", "operator"):
                await websocket.close(code=4403, reason="Role is not permitted.")
                return
            device = await db.get(Device, device_id)
            if device is None or not device.is_active:
                await websocket.close(code=4404, reason="Active inventory device not found.")
                return
            device_data: Dict[str, Any] = {
                "id": device.id,
                "hostname": device.hostname,
                "ip_address": device.ip_address,
                "vendor": device.vendor,
                "model": device.model,
                "os_type": device.os_type,
                "ssh_port": device.ssh_port,
                "encrypted_credentials": device.encrypted_credentials,
            }

        try:
            credentials = vault.decrypt_credentials(device_data["encrypted_credentials"]) or {}
            profile = get_vendor_profile(
                vendor=device_data["vendor"],
                os_type=device_data["os_type"],
                model=device_data["model"],
            )
        except Exception:
            logger.exception("Terminal setup failed for device id %s.", device_id)
            await websocket.close(code=1011, reason="Terminal setup failed.")
            return
        allowed_commands = list(dict.fromkeys((
            profile.interface_command,
            profile.vlan_command,
            profile.mac_command,
            profile.version_command,
        )))
        logger.info("Read-only terminal opened by %s for device %s.", username, device_data["hostname"])
        await websocket.send_json({
            "type": "ready",
            "hostname": device_data["hostname"],
            "allowed_commands": allowed_commands,
            "message": "Only the listed read-only commands are permitted.",
        })

        while True:
            message = await websocket.receive_json()
            command = message.get("command") if isinstance(message, dict) else None
            if message == {"type": "close"}:
                await websocket.close(code=1000)
                return
            if not isinstance(command, str) or command not in allowed_commands:
                await websocket.send_json({"type": "error", "message": "Command is not permitted."})
                continue
            logger.info(
                "Read-only device command requested by %s for %s: %s",
                username,
                device_data["hostname"],
                command,
            )
            try:
                output = await automation_engine.send_readonly_command(
                    _TerminalDevice(device_data),
                    credentials,
                    command,
                )
            except Exception:
                logger.exception("Read-only command failed for device %s.", device_data["hostname"])
                await websocket.send_json({"type": "error", "message": "Device command failed."})
                await websocket.close(code=1011)
                return
            await websocket.send_json({
                "type": "output",
                "command": command,
                "content": output[:_MAX_OUTPUT_CHARS],
                "truncated": len(output) > _MAX_OUTPUT_CHARS,
            })
    except asyncio.TimeoutError:
        await websocket.close(code=4401, reason="Authentication timed out.")
    except WebSocketDisconnect:
        logger.info("Read-only terminal disconnected for device id %s.", device_id)


class _TerminalDevice:
    def __init__(self, values: Dict[str, Any]):
        self.__dict__.update(values)
