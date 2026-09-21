# Stable addresses and legacy identity migration, independent of Home Assistant.
import ipaddress
import re


def normalize_host(value: str) -> str:
    """Accept a hostname or IP, never credentials, URLs, ports or paths."""
    host = value.strip().lower().rstrip(".")
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    try:
        return ipaddress.ip_address(host).compressed
    except ValueError:
        pass
    if len(host) > 253 or not host or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
        for part in host.split(".")
    ):
        raise ValueError("Invalid host")
    return host


def legacy_id(host: str) -> str:
    """Keep existing card and button references during YAML import."""
    return host.replace(".", "_").replace(":", "_")


def http_host(host: str) -> str:
    """Bracket IPv6 literals in HTTP URLs."""
    return f"[{host}]" if ":" in host else host
