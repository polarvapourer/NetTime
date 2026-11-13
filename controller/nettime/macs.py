import re

_MAC = re.compile(r"^[0-9A-Fa-f]{2}([:-]?)[0-9A-Fa-f]{2}(\1[0-9A-Fa-f]{2}){4}$")


def canonical_mac(v):
    """'aa-bb-cc-dd-ee-ff' -> 'AA:BB:CC:DD:EE:FF'; None if not a MAC."""
    if not isinstance(v, str) or not _MAC.match(v.strip()):
        return None
    h = re.sub(r"[:-]", "", v.strip()).upper()
    return ":".join(h[i:i + 2] for i in range(0, 12, 2))


def is_unicast(mac):
    """Unicast and not all-zero. Locally administered (iPad private) addresses are allowed."""
    if mac is None:
        return False
    first = int(mac[:2], 16)
    return not (first & 1) and mac != "00:00:00:00:00:00"
