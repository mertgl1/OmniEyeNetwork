import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.vault import vault
from app.models.device import Device
from app.models.port import Port
from app.services.automation_engine import automation_engine

_INTERFACE_PATTERN = re.compile(
    r"^(?:"
    r"(?:GigabitEthernet|FastEthernet|TenGigabitEthernet|TwentyFiveGigE|"
    r"FortyGigabitEthernet|HundredGigE|Ethernet|Loopback|Port-channel|"
    r"Po|Gi|Fa|Te|Eth|Et|GE|XGE|FE|"
    r"ge-|xe-|et-|ae\d|vlan|Vlan|bridge|ether\d)"
    r")[\w./:-]*$",
    re.IGNORECASE,
)
_MAC_PATTERN = re.compile(
    r"^(?:[0-9a-f]{4}\.){2}[0-9a-f]{4}$|"
    r"^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$|"
    r"^(?:[0-9a-f]{2}-){5}[0-9a-f]{2}$",
    re.IGNORECASE,
)
_UP_STATES = {"up", "connected", "forwarding"}
_DOWN_STATES = {"down", "disabled", "notconnect", "not-connected", "administratively"}


def parse_port_inventory(outputs: Dict[str, str]) -> List[Dict[str, Any]]:
    """Parse common multi-vendor interface, VLAN and MAC table formats."""
    ports: Dict[str, Dict[str, Any]] = {}
    for line in outputs.get("interfaces", "").splitlines():
        fields = line.split()
        if not fields or not _INTERFACE_PATTERN.match(fields[0].strip("*,:")):
            continue
        name = fields[0].strip("*,:")
        states = [field.lower().strip("(),") for field in fields[1:]]
        matching_states = [state for state in states if state in _UP_STATES | _DOWN_STATES]
        if not matching_states:
            continue
        operational = "up" if matching_states[-1] in _UP_STATES else "down"
        admin = "down" if matching_states[0] in _DOWN_STATES else "up"
        ports[name.casefold()] = {
            "name": name,
            "status": operational,
            "admin_status": admin,
            "description": None,
            "vlan": None,
            "mac_address": None,
            "speed": None,
            "duplex": None,
        }

    for line in outputs.get("vlans", "").splitlines():
        fields = line.split()
        if not fields or not fields[0].isdigit():
            continue
        vlan = int(fields[0])
        if vlan < 1 or vlan > 4094:
            continue
        for field in fields[1:]:
            for candidate in field.strip("[],").split(","):
                normalized = candidate.strip()
                if _INTERFACE_PATTERN.match(normalized):
                    port = ports.get(normalized.casefold())
                    if port:
                        port["vlan"] = vlan

    for line in outputs.get("macs", "").splitlines():
        fields = line.split()
        if not fields or not fields[0].isdigit():
            continue
        vlan = int(fields[0])
        mac = next((field for field in fields[1:] if _MAC_PATTERN.match(field)), None)
        interface = next(
            (field.strip("*,") for field in reversed(fields) if _INTERFACE_PATTERN.match(field.strip("*,"))),
            None,
        )
        if interface:
            port = ports.get(interface.casefold())
            if port:
                if mac:
                    port["mac_address"] = mac
                if port["vlan"] is None and 1 <= vlan <= 4094:
                    port["vlan"] = vlan

    return list(ports.values())


async def discover_device_ports(device: Device) -> List[Dict[str, Any]]:
    credentials = vault.decrypt_credentials(device.encrypted_credentials) or {}
    outputs = await automation_engine.fetch_inventory_outputs(device, credentials)
    return parse_port_inventory(outputs)


async def sync_device_ports(db: AsyncSession, device: Device) -> int:
    discovered = await discover_device_ports(device)
    if not discovered:
        return 0

    result = await db.execute(select(Port).where(Port.device_id == device.id))
    existing_ports = {port.name.casefold(): port for port in result.scalars().all()}
    _merge_discovered_ports(db, device, discovered, existing_ports)
    await db.commit()
    return len(discovered)


def sync_device_ports_sync(db: Session, device: Device) -> int:
    import asyncio

    discovered = asyncio.run(discover_device_ports(device))
    if not discovered:
        return 0
    result = db.execute(select(Port).where(Port.device_id == device.id))
    existing_ports = {port.name.casefold(): port for port in result.scalars().all()}
    _merge_discovered_ports(db, device, discovered, existing_ports)
    db.commit()
    return len(discovered)


def _merge_discovered_ports(
    db: Any,
    device: Device,
    discovered: List[Dict[str, Any]],
    existing_ports: Dict[str, Port],
) -> None:
    now = datetime.now(timezone.utc)

    for item in discovered:
        existing = existing_ports.get(item["name"].casefold())
        if existing is None:
            db.add(Port(device_id=device.id, **item, last_change=now))
            continue
        if existing.status != item["status"] or existing.admin_status != item["admin_status"]:
            existing.last_change = now
        for field, value in item.items():
            setattr(existing, field, value)
