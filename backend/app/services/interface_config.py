import re


class UnsupportedInterfaceConfig(ValueError):
    """Raised when a configuration cannot be safely isolated to one interface."""


_SAFE_INTERFACE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9./:_-]{0,63}$")
_BLOCK_PROFILES = {
    "cisco_ios",
    "cisco_nxos",
    "cisco_xr",
    "huawei_vrp",
    "aruba_os",
    "hp_procurve",
    "hp_comware",
    "dell_os10",
}
SUPPORTED_INTERFACE_CONFIG_PROFILES = _BLOCK_PROFILES | {"juniper_junos"}
_DELL_HEADER = re.compile(
    r"^\s*interface\s+ethernet\s+(\S+)\s*$",
    re.IGNORECASE,
)


def extract_interface_config(config_text: str, port_name: str, vendor_key: str) -> str:
    """Return only a safely delimited stanza for the requested known interface."""
    if not _SAFE_INTERFACE_NAME.fullmatch(port_name):
        raise UnsupportedInterfaceConfig("The stored interface name is not supported.")

    if vendor_key in _BLOCK_PROFILES:
        return _extract_block_config(config_text, port_name, vendor_key)
    if vendor_key == "juniper_junos":
        return _extract_juniper_config(config_text, port_name)
    raise UnsupportedInterfaceConfig(
        f"Port-level configuration is not supported for vendor profile {vendor_key}."
    )


def supports_interface_config(vendor_key: str) -> bool:
    return vendor_key in SUPPORTED_INTERFACE_CONFIG_PROFILES


def _interface_key(name: str) -> str:
    normalized = name.casefold()
    prefixes = (
        ("gigabitethernet", "gigabitethernet"),
        ("tengigabitethernet", "tengigabitethernet"),
        ("fastethernet", "fastethernet"),
        ("port-channel", "port-channel"),
        ("ethernet", "ethernet"),
        ("gi", "gigabitethernet"),
        ("ge", "gigabitethernet"),
        ("te", "tengigabitethernet"),
        ("fa", "fastethernet"),
        ("po", "port-channel"),
        ("eth", "ethernet"),
    )
    for full, short in prefixes:
        if normalized.startswith(full):
            normalized = short + normalized[len(full):]
            break
    return normalized


def _extract_block_config(
    config_text: str,
    port_name: str,
    vendor_key: str,
) -> str:
    target = _interface_key(port_name)
    lines = config_text.splitlines()
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if _interface_key(_block_interface_name(line, vendor_key) or "") == target
        ),
        None,
    )
    if start is None:
        raise UnsupportedInterfaceConfig(
            "The requested interface stanza was not found in the device configuration."
        )

    block = [lines[start]]
    terminated = False
    for line in lines[start + 1:]:
        stripped = line.strip()
        if stripped in {"!", "#", "exit", "end"}:
            terminated = True
            break
        if re.match(r"^\s*interface\s+\S+\s*$", line, re.IGNORECASE):
            terminated = True
            break
        if line and not line[0].isspace():
            raise UnsupportedInterfaceConfig(
                "The interface stanza boundary is ambiguous in the device configuration."
            )
        block.append(line)
    if not terminated:
        raise UnsupportedInterfaceConfig(
            "The interface stanza has no safe ending boundary."
        )
    return "\n".join(block).strip()


def _block_interface_name(line: str, vendor_key: str) -> str | None:
    if vendor_key == "dell_os10":
        dell_match = _DELL_HEADER.match(line)
        if dell_match:
            return f"Ethernet{dell_match.group(1)}"
    match = re.match(r"^\s*interface\s+(\S+)\s*$", line, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_juniper_config(config_text: str, port_name: str) -> str:
    escaped_name = re.escape(port_name)
    header = re.compile(rf"^\s*{escaped_name}\s*\{{\s*$", re.IGNORECASE)
    lines = config_text.splitlines()
    start = next((index for index, line in enumerate(lines) if header.match(line)), None)
    if start is None:
        raise UnsupportedInterfaceConfig(
            "The requested interface stanza was not found in the device configuration."
        )

    block = []
    depth = 0
    for line in lines[start:]:
        block.append(line)
        depth += _brace_delta(line)
        if depth == 0:
            return "\n".join(block).strip()
    raise UnsupportedInterfaceConfig(
        "The requested interface stanza has unbalanced configuration braces."
    )


def _brace_delta(line: str) -> int:
    delta = 0
    for token in re.findall(r'"(?:\\.|[^"\\])*"|[{}]', line):
        if token == "{":
            delta += 1
        elif token == "}":
            delta -= 1
    return delta
