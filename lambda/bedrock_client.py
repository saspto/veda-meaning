"""
AWS Bedrock Claude Haiku fallback for verse retrieval and meaning generation.
"""
import json
import boto3

MODEL_ID = "anthropic.claude-haiku-4-5-20251001"
REGION = "us-east-1"

_client = None


def _bedrock():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=REGION)
    return _client


def _invoke(messages, max_tokens=2048):
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": messages,
    })
    resp = _bedrock().invoke_model(modelId=MODEL_ID, body=body)
    result = json.loads(resp["body"].read())
    return result["content"][0]["text"]


def get_verse_ai(ref, script):
    """Return the complete chapter/recitation in Devanagari (or Telugu if requested)."""
    script_name = "Telugu script (Telugu Unicode)" if script == "telugu" else "Devanagari script (Sanskrit Unicode)"
    prompt = (
        f"You are an expert in Vedic scriptures. "
        f"Provide the complete text for: {ref}\n\n"
        f"Requirements:\n"
        f"- Output in {script_name}\n"
        f"- Include the complete chapter or recitation, not just one verse\n"
        f"- If this is a chapter (e.g. Bhagavad Gita Chapter 2), include all verses\n"
        f"- If this is a specific verse reference, include that verse and the surrounding context\n"
        f"- For named mantras (Gayatri, Maha Mrityunjaya, etc.), include the full mantra with all repetitions\n"
        f"- Use only authentic scriptural text, no paraphrasing\n"
        f"- Number each verse\n"
        f"Return ONLY the scriptural text, no commentary."
    )
    return _invoke([{"role": "user", "content": prompt}], max_tokens=4096)


def get_meaning_ai(ref, script):
    """Return structured meaning: word-by-word and sentence-by-sentence in English."""
    prompt = (
        f"You are an expert Sanskrit/Telugu scholar. Provide a detailed meaning analysis for: {ref}\n\n"
        f"Return a JSON object with this exact structure:\n"
        f'{{"word_for_word": [{{"word": "Sanskrit/Telugu word", "transliteration": "IAST transliteration", "meaning": "English meaning"}}], '
        f'"sentence": [{{"text": "Full sentence in source script", "transliteration": "IAST", "meaning": "English translation"}}], '
        f'"source": "AI knowledge base"}}\n\n'
        f"Requirements:\n"
        f"- word_for_word: every significant word with individual English meaning\n"
        f"- sentence: each complete sentence/line with full English translation\n"
        f"- For Sanskrit words, use standard Panini grammar analysis where relevant\n"
        f"- For Telugu words, note Telugu-specific nuances vs Sanskrit roots\n"
        f"- English meanings should be scholarly but accessible\n"
        f"Return ONLY valid JSON, no markdown, no commentary."
    )
    raw = _invoke([{"role": "user", "content": prompt}], max_tokens=3000)

    # Strip markdown code blocks if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("`").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "word_for_word": [],
            "sentence": [{"text": raw, "lang": "en"}],
            "source": "AI knowledge base",
        }
