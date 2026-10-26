"""
Reading LiveSplit splits (.lss), the parts that aren't the splits' names: a segment's icon.
"""
import base64
import binascii

PNG_START = b"\x89PNG\r\n\x1a\n"
PNG_END = b"IEND\xaeB`\x82"


def icon_png(text):
    """
    The PNG in a segment's <Icon>, or None where there's none. LiveSplit saves a serialized .NET bitmap in base64, which
    has the picture as a PNG in the middle of it.
    """
    try:
        data = base64.b64decode(text or "")
    except (binascii.Error, ValueError):
        return None
    start = data.find(PNG_START)
    end = data.find(PNG_END, start) if start >= 0 else -1
    return data[start:end + len(PNG_END)] if end >= 0 else None
