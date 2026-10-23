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
from app.services.vendor_profiles import get_vendor_profile

_INTERFACE_PATTERN = re.compile(
    r"^(?:GigabitEthernet|FastEthernet|TenGigabitEthernet|TwentyFiveGigE|"
    r"FortyGigabitEthernet|HundredGigE|Ethernet|Loopback|Port-channel|"
    r"Po|Gi|Fa|Te|Eth|Et|GE|XGE|FE|"
    r"ge-|xe-|et-|ae\d+|vlan|Vlan|bridge|ether\d+|port\d+)"
    r"[\w./:-]+$",
    re.IGNORECASE,
)
_MAC_PATTERN = re.compile(
    r"^(?:[0-9a-f]{4}\.){2}[0-9a-f]{4}$|"
    r"^(?:[0-9a-f]{4}-){2}[0-9a-f]{4}$|"
    r"^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$|"
    r"^(?:[0-9a-f]{2}-){5}[0-9a-f]{2}$",
    re.IGNORECASE,
)
_UP_STATES = {"up", "connected", "forwarding"}
_DOWN_STATES = {"down", "disabled", "notconnect", "not-connected", "administratively"}
_PARSER_FAMILIES = {
    "cisco_ios": "tabular",
    "cisco_nxos": "tabular",
    "cisco_xr": "tabular",
    "huawei_vrp": "tabular",
    "aruba_os": "numeric_tabular",
    "hp_procurve": "procurve",
    "hp_comware": "tabular",
    "juniper_junos": "tabular",
    "dell_os10": "dell",
    "extreme_exos": "extreme",
    "mikrotik_routeros": "mikrotik",
    "fortinet": "fortinet",
}


def parse_port_inventory(
    outputs: Dict[str, str],
    vendor_key: str | None = None,
) -> List[Dict[str, Any]]:
    """Parse supported vendor CLI outputs into normalized port records."""
    family = _PARSER_FAMILIES.get(vendor_key or "", "tabular")
    ports: Dict[str, Dict[str, Any]] = {}
    _parse_interface_output(outputs.get("interfaces", ""), family, ports)

    for line in outputs.get("vlans", "").splitlines():
        if family == "mikrotik":
            _parse_mikrotik_vlan_line(line, ports)
            continue
        fields = line.split()
        if not fields:
            continue
        port_fields = fields[1:]
        if fields[0].isdigit():
            vlan = int(fields[0])
        elif (
            family == "tabular"
            and vendor_key == "juniper_junos"
            and len(fields) > 1
            and fields[1].isdigit()
        ):
            vlan = int(fields[1])
            port_fields = fields[2:]
        else:
            continue
        if vlan < 1 or vlan > 4094:
            continue
        for field in port_fields:
            for candidate in field.strip("[],").split(","):
                normalized = candidate.strip()
                if _is_known_port(ports, normalized):
                    port = _find_port(ports, normalized)
                    if port:
                        port["vlan"] = vlan

    for line in outputs.get("macs", "").splitlines():
        if family == "mikrotik":
            _parse_mikrotik_mac_line(line, ports)
            continue
        if family == "fortinet":
            _parse_fortinet_mac_line(line, ports)
            continue
        fields = line.split()
        if not fields or not fields[0].isdigit():
            continue
        vlan = int(fields[0])
        mac = next((field for field in fields[1:] if _MAC_PATTERN.match(field)), None)
        interface = next(
            (
                field.strip("*,")
                for field in reversed(fields)
                if _is_known_port(ports, field.strip("*,"))
            ),
            None,
        )
        if interface:
            port = _find_port(ports, interface)
            if port:
                if mac:
                    port["mac_address"] = mac
                if port["vlan"] is None and 1 <= vlan <= 4094:
                    port["vlan"] = vlan

    if not ports:
        raise UnsupportedInventoryOutput(
            f"No interfaces could be parsed for vendor profile {vendor_key or 'generic'}."
        )
    return list(ports.values())


class UnsupportedInventoryOutput(ValueError):
    """Raised when device output does not match a supported inventory format."""


def _parse_interface_output(
    output: str,
    family: str,
    ports: Dict[str, Dict[str, Any]],
) -> None:
    if family == "mikrotik":
        for line in output.splitlines():
            values = dict(re.findall(r"([\w-]+)=([^\s]+)", line))
            name = values.get("name")
            if not name or not name.casefold().startswith(
                ("ether", "sfp", "wlan", "bridge")
            ):
                continue
            disabled = values.get("disabled", "no").lower() == "yes"
            running = values.get("running", "no").lower() == "yes"
            _store_port(ports, name, "up" if running else "down", "down" if disabled else "up")
        return

    if family == "fortinet":
        current_name = None
        for line in output.splitlines():
            block = re.search(r"==\s*\[\s*([^\]]+)\s*\]", line)
            named = re.match(r"\s*name\s*:\s*([\w./:-]+)", line, re.IGNORECASE)
            if block:
                current_name = block.group(1).strip()
            elif named:
                current_name = named.group(1)
            if not current_name:
                continue
            state = re.search(
                r"\b(?:link|status)\s*:\s*(up|down)\b", line, re.IGNORECASE
            )
            if state:
                normalized = state.group(1).lower()
                _store_port(ports, current_name, normalized, normalized)
        return

    for line in output.splitlines():
        fields = line.split()
        if not fields:
            continue
        name, state_fields = _interface_name_and_fields(fields, family)
        if not name:
            continue
        matching_states = [
            _normalize_state(field)
            for field in state_fields
            if _normalize_state(field) in _UP_STATES | _DOWN_STATES
        ]
        if not matching_states:
            continue
        operational = "up" if matching_states[-1] in _UP_STATES else "down"
        admin = "down" if matching_states[0] in _DOWN_STATES else "up"
        _store_port(ports, name, operational, admin)


def _interface_name_and_fields(
    fields: List[str],
    family: str,
) -> tuple[str | None, List[str]]:
    first = fields[0].strip("*,:")
    if family == "dell" and first.casefold() in {"eth", "ethernet"} and len(fields) > 1:
        return f"{first}{fields[1].strip('*:,')}", fields[2:]
    if family == "procurve" and first.isdigit():
        return first, fields[1:]
    if family == "numeric_tabular" and re.fullmatch(r"\d+(?:/\d+)+", first):
        return first, fields[1:]
    if family == "extreme" and re.fullmatch(r"\d+:\d+", first):
        return first, fields[1:]
    if _is_interface_name(first):
        return first, fields[1:]
    return None, []


def _store_port(
    ports: Dict[str, Dict[str, Any]],
    name: str,
    operational: str,
    admin: str,
) -> None:
    ports[_interface_key(name)] = {
        "name": name,
        "status": operational,
        "admin_status": admin,
        "description": None,
        "vlan": None,
        "mac_address": None,
        "speed": None,
        "duplex": None,
    }


def _is_interface_name(value: str) -> bool:
    return bool(
        _INTERFACE_PATTERN.match(value)
        or re.fullmatch(r"\d+(?:/\d+)+", value)
        or re.fullmatch(r"\d+:\d+", value)
    )


def _interface_key(name: str) -> str:
    normalized = name.casefold()
    for full, short in (
        ("gigabitethernet", "gi"),
        ("fastethernet", "fa"),
        ("tengigabitethernet", "te"),
        ("ethernet", "eth"),
        ("port-channel", "po"),
    ):
        if normalized.startswith(full):
            return short + normalized[len(full):]
    return normalized


def _find_port(
    ports: Dict[str, Dict[str, Any]],
    name: str,
) -> Dict[str, Any] | None:
    return ports.get(_interface_key(name))


def _is_known_port(ports: Dict[str, Dict[str, Any]], value: str) -> bool:
    return _is_interface_name(value) or _interface_key(value) in ports


def _normalize_state(value: str) -> str:
    return value.lower().strip("*(),:")


def _parse_mikrotik_vlan_line(
    line: str,
    ports: Dict[str, Dict[str, Any]],
) -> None:
    values = dict(re.findall(r"([\w-]+)=([^\s]+)", line))
    vlan_match = re.search(r"\d+", values.get("vlan-ids", ""))
    if not vlan_match:
        return
    vlan = int(vlan_match.group())
    for field in ("tagged", "untagged"):
        for name in values.get(field, "").split(","):
            port = _find_port(ports, name)
            if port and port["vlan"] is None:
                port["vlan"] = vlan


def _parse_mikrotik_mac_line(
    line: str,
    ports: Dict[str, Dict[str, Any]],
) -> None:
    values = dict(re.findall(r"([\w-]+)=([^\s]+)", line))
    name = values.get("on-interface")
    mac = values.get("mac-address")
    port = _find_port(ports, name) if name else None
    if port and mac and _MAC_PATTERN.match(mac):
        port["mac_address"] = mac
        vlan = values.get("vid") or values.get("vlan-id")
        if vlan and vlan.isdigit() and 1 <= int(vlan) <= 4094:
            port["vlan"] = int(vlan)


def _parse_fortinet_mac_line(
    line: str,
    ports: Dict[str, Dict[str, Any]],
) -> None:
    fields = line.split()
    mac = next((field for field in fields if _MAC_PATTERN.match(field)), None)
    interface = next(
        (field for field in fields if field.casefold().startswith("port")),
        None,
    )
    port = _find_port(ports, interface) if interface else None
    if port and mac:
        port["mac_address"] = mac


async def discover_device_ports(device: Device) -> List[Dict[str, Any]]:
    credentials = vault.decrypt_credentials(device.encrypted_credentials) or {}
    outputs = await automation_engine.fetch_inventory_outputs(device, credentials)
    profile = get_vendor_profile(device.vendor, device.os_type, device.model)
    return parse_port_inventory(outputs, profile.vendor_key)


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


def sync_devices_ports_sync(db: Session, devices: List[Device]) -> Dict[int, int]:
    """Discover multiple devices concurrently and persist successful results."""
    import asyncio

    device_inputs = {
        str(device.id): (
            device,
            vault.decrypt_credentials(device.encrypted_credentials) or {},
        )
        for device in devices
    }
    outputs_by_device = asyncio.run(
        automation_engine.fetch_inventory_outputs_batch(device_inputs)
    )
    discovered_counts: Dict[int, int] = {}
    for key, (device, _credentials) in device_inputs.items():
        outputs = outputs_by_device.get(key)
        if outputs is None:
            continue
        profile = get_vendor_profile(device.vendor, device.os_type, device.model)
        try:
            discovered = parse_port_inventory(outputs, profile.vendor_key)
        except UnsupportedInventoryOutput:
            continue
        existing_result = db.execute(
            select(Port).where(Port.device_id == device.id)
        )
        existing_ports = {
            port.name.casefold(): port
            for port in existing_result.scalars().all()
        }
        _merge_discovered_ports(db, device, discovered, existing_ports)
        discovered_counts[device.id] = len(discovered)
    db.commit()
    return discovered_counts


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
            db.add(
                Port(
                    device_id=device.id,
                    **item,
                    last_change=now,
                    last_discovered_at=now,
                )
            )
            continue
        if existing.status != item["status"] or existing.admin_status != item["admin_status"]:
            existing.last_change = now
        for field, value in item.items():
            setattr(existing, field, value)
        existing.last_discovered_at = now
