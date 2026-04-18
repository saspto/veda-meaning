import json
import os
from scraper import fetch_verse, fetch_meaning
from transliterator import to_telugu
from bedrock_client import get_verse_ai, get_meaning_ai

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
    "Content-Type": "application/json",
}


def response(status, body):
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(body)}


def lambda_handler(event, context):
    method = event.get("httpMethod", "GET")
    path = event.get("path", "")
    qs = event.get("queryStringParameters") or {}

    if method == "OPTIONS":
        return response(200, {})

    ref = qs.get("ref", "").strip()
    script = qs.get("script", "devanagari").lower()

    if not ref:
        return response(400, {"error": "ref query parameter is required"})

    if path.endswith("/verse"):
        return handle_verse(ref, script)
    elif path.endswith("/meaning"):
        return handle_meaning(ref, script)
    else:
        return response(404, {"error": "Not found"})


def handle_verse(ref, script):
    try:
        text = fetch_verse(ref, script)
    except Exception:
        text = None

    if not text:
        try:
            text = get_verse_ai(ref, script)
        except Exception as e:
            return response(500, {"error": str(e)})

    if script == "telugu" and text:
        try:
            text = to_telugu(text)
        except Exception:
            pass

    return response(200, {"ref": ref, "script": script, "verse": text})


def handle_meaning(ref, script):
    try:
        meaning = fetch_meaning(ref, script)
    except Exception:
        meaning = None

    if not meaning:
        try:
            meaning = get_meaning_ai(ref, script)
        except Exception as e:
            return response(500, {"error": str(e)})

    return response(200, {"ref": ref, "script": script, "meaning": meaning})
