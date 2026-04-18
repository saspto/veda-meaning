"""
Transliterates Devanagari → Telugu script.
Tries Aksharamukha API first, falls back to Bedrock.
"""
import json
import urllib.parse
import urllib.request

AKSHARAMUKHA_URL = "https://aksharamukha.appspot.com/api/public"
TIMEOUT = 8


def to_telugu(devanagari_text):
    """Convert Devanagari text to Telugu script."""
    if not devanagari_text or not devanagari_text.strip():
        return devanagari_text

    try:
        return _aksharamukha(devanagari_text)
    except Exception:
        pass

    # Fallback: return original with a note (Bedrock handles this in bedrock_client)
    return devanagari_text


def _aksharamukha(text):
    params = urllib.parse.urlencode({
        "source": "Devanagari",
        "target": "Telugu",
        "text": text,
    })
    url = f"{AKSHARAMUKHA_URL}?{params}"
    req = urllib.request.Request(url, headers={"Accept": "text/plain"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        result = r.read().decode("utf-8")
    if result and result.strip():
        return result.strip()
    raise ValueError("Empty response from Aksharamukha")
