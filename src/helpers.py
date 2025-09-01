import base64
import binascii
import struct

def _wkb_point_to_lonlat(wkb_input):
    """
    Returns (lon, lat) tuple or None if it can't decode.
    Accepts Base64 string, HEX string, or bytes.
    Handles optional 4-byte 0x00000000 prefix.
    Only supports WKB Point (type=1).
    Prefers coordinates that fall in Europe; may swap (x,y) -> (y,x) if appropriate.
    """

    def in_global(lon, lat):
        return (-180.0 <= lon <= 180.0) and (-90.0 <= lat <= 90.0)

    # A generous Europe bounding box
    # (covers Canary Islands to western Russia, Mediterranean to Scandinavia)
    def in_europe(lon, lat):
        return (-31.0 <= lon <= 60.0) and (30.0 <= lat <= 75.0)

    if wkb_input is None:
        return None

    # Decode to bytes
    if isinstance(wkb_input, (bytes, bytearray)):
        b = bytes(wkb_input)
    elif isinstance(wkb_input, str):
        s = wkb_input.strip()
        b = None
        # try Base64 first
        try:
            b = base64.b64decode(s, validate=True)
        except (binascii.Error, ValueError):
            b = None
        if b is None:
            # then HEX
            try:
                b = bytes.fromhex(s)
            except ValueError:
                return None
    else:
        return None

    # Optional 4-byte prefix 00 00 00 00 before endian flag
    if len(b) >= 9 and b[:4] == b"\x00\x00\x00\x00" and b[4] in (0, 1):
        b = b[4:]

    if len(b) < 1 + 4 + 16:
        return None

    byte_order = b[0]
    if byte_order not in (0, 1):
        return None
    endian = "<" if byte_order == 1 else ">"
    gtype = struct.unpack(endian + "I", b[1:5])[0]
    if gtype != 1:  # only WKB Point
        return None

    try:
        x, y = struct.unpack(endian + "dd", b[5:5+16])
    except struct.error:
        return None

    # WKB point convention here: x=lon, y=lat
    lon, lat = x, y
    lon_sw, lat_sw = y, x

    orig_valid = in_global(lon, lat)
    swap_valid = in_global(lon_sw, lat_sw)

    # Prefer the orientation that is inside Europe
    if orig_valid and in_europe(lon, lat):
        return (lon, lat)
    if swap_valid and in_europe(lon_sw, lat_sw):
        return (lon_sw, lat_sw)

    # If original is valid but not in Europe, and swapped is valid, follow your rule: swap
    if orig_valid and not in_europe(lon, lat) and swap_valid:
        return (lon_sw, lat_sw)

    # Otherwise fall back to any globally valid orientation
    if orig_valid:
        return (lon, lat)
    if swap_valid:
        return (lon_sw, lat_sw)

    return None