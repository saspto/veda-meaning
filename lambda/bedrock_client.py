"""
AWS Bedrock Claude Haiku fallback for verse retrieval and meaning generation.
"""
import json
import boto3

MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
REGION = "us-west-2"

_client = None


def _bedrock():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=REGION)
    return _client


def _invoke(messages, max_tokens=4096):
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": messages,
    })
    resp = _bedrock().invoke_model(modelId=MODEL_ID, body=body)
    result = json.loads(resp["body"].read())
    return result["content"][0]["text"]


# ---------------------------------------------------------------------------
# Verse / recitation
# ---------------------------------------------------------------------------

# Well-known hymn/suktam verse counts so the prompt can demand the exact number
_HYMN_VERSE_COUNTS = {
    "sri suktam":             15,
    "shri suktam":            15,
    "lakshmi suktam":         15,
    "purusha suktam":         16,
    "narayana suktam":        13,
    "durga suktam":           7,
    "medha suktam":           7,
    "vishnu suktam":          6,
    "rudram":                 None,  # long — just say "complete"
    "namakam":                None,
    "chamakam":               None,
    "arunam":                 None,
    "bhu suktam":             6,
    "nila suktam":            8,
    "manyu suktam":           8,
    "pavamana suktam":        None,
    "hiranyagarbha suktam":   10,
}


def _verse_count_hint(ref):
    r = ref.lower()
    for name, count in _HYMN_VERSE_COUNTS.items():
        if name in r:
            if count:
                return f"This hymn has exactly {count} verses — include ALL {count} verses, none missing."
            return "Include the complete hymn — do not truncate or summarise."
    return "Include all verses completely — do not truncate."


def get_verse_ai(ref, script):
    """Return the complete text in Devanagari (or Telugu) script."""
    script_name = (
        "Telugu script (Telugu Unicode characters)"
        if script == "telugu"
        else "Devanagari script (Sanskrit Unicode characters)"
    )
    count_hint = _verse_count_hint(ref)

    prompt = (
        f"You are a Vedic scripture expert with deep knowledge of all four Vedas "
        f"(Rig, Yajur, Sama, Atharva), Upanishads, Itihasas, and Puranas.\n\n"
        f"Task: Provide the COMPLETE authentic text for: **{ref}**\n\n"
        f"STRICT REQUIREMENTS:\n"
        f"1. Output ONLY in {script_name}.\n"
        f"2. {count_hint}\n"
        f"3. Number every verse (e.g. ॥ १॥ ॥ २॥ ...).\n"
        f"4. Use only authentic, traditional scriptural text — no paraphrase, "
        f"no modern rewording.\n"
        f"5. For Yajur Veda texts (Taittiriya Samhita / Vajasaneyi Samhita), "
        f"use the standard recension text.\n"
        f"6. Do NOT add English words, headings in English, or any commentary.\n"
        f"7. If this is Sri Suktam, it has 15 Richas (verses) — provide all 15 "
        f"plus the Phala Shruti at the end.\n\n"
        f"Return ONLY the scriptural text. Start directly with the first verse."
    )
    return _invoke([{"role": "user", "content": prompt}], max_tokens=8000)


# ---------------------------------------------------------------------------
# Meaning
# ---------------------------------------------------------------------------

def get_meaning_ai(ref, script):
    """Return structured word-by-word + sentence meaning in English."""
    prompt = (
        f"You are an expert Vedic scholar specialising in Sanskrit grammar (Panini), "
        f"Nirukta, and Vedic interpretation.\n\n"
        f"Task: Provide a complete meaning analysis for: **{ref}**\n\n"
        f"Return a JSON object with this EXACT structure:\n"
        "{\n"
        '  "word_for_word": [\n'
        '    {"word": "<Sanskrit/Telugu word in Devanagari or Telugu script>",\n'
        '     "transliteration": "<IAST transliteration>",\n'
        '     "meaning": "<English meaning with grammatical note where useful>"}\n'
        "  ],\n"
        '  "sentence": [\n'
        '    {"text": "<full line/sentence in source script>",\n'
        '     "transliteration": "<IAST>",\n'
        '     "meaning": "<complete English translation>"}\n'
        "  ],\n"
        '  "source": "AI knowledge base"\n'
        "}\n\n"
        "REQUIREMENTS:\n"
        "- word_for_word: analyse EVERY significant word — include sandhi splits where relevant.\n"
        "- sentence: every complete sentence or half-verse with full English translation.\n"
        "- For Yajur Veda / Vedic texts: use Sayana's commentary tradition for meanings.\n"
        "- For Sri Suktam: include all 15 richas — all words, all lines.\n"
        "- Sanskrit meanings → English only. Telugu meanings → English only.\n"
        "- Return ONLY valid JSON. No markdown fences, no commentary outside JSON."
    )
    raw = _invoke([{"role": "user", "content": prompt}], max_tokens=8000)

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("`").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to salvage partial JSON
        try:
            end = raw.rfind("}")
            if end > 0:
                return json.loads(raw[: end + 1])
        except Exception:
            pass
        return {
            "word_for_word": [],
            "sentence": [{"text": raw, "lang": "en", "meaning": ""}],
            "source": "AI knowledge base",
        }
