# Veda Meaning

Web app for Vedic scripture lookup — Sanskrit/Telugu script with word-by-word English meaning.

## Architecture

```
CloudFront
  /api/*  →  API Gateway  →  Lambda (Python 3.12)
               /verse           scraper.py → vedabase.io, IIT-K, valmikiramayan.net, sacred-texts.com
               /meaning         scraper.py → vedabase.io, wisdomlib.org
                                fallback → Bedrock Claude Haiku (anthropic.claude-haiku-4-5-20251001)
                                telugu → Aksharamukha API
  /*      →  S3 (static frontend, OAC)
```

**FedRAMP services only. No Cognito.**

## Features

- Input verse reference: `BG 2.47`, `BG 2` (full chapter), `Gayatri Mantra`, `RV 1.1.1`, `VR 1.1.1`
- Fetch complete chapter or full mantra recitation
- Sanskrit (Devanagari) or Telugu script output
- Meaning: word-by-word (with transliteration) + sentence-by-sentence, all in English
- CloudFront caches API responses 24 hours per ref+script key → minimises Bedrock cost

## Supported References

| Format | Example | Text |
|--------|---------|------|
| `BG <ch>.<v>` | `BG 2.47` | Bhagavad Gita verse |
| `BG <ch>` | `BG 2` | Bhagavad Gita chapter |
| `RV <m>.<s>.<v>` | `RV 1.1.1` | Rig Veda |
| `VR <k>.<s>.<v>` | `VR 1.1.1` | Valmiki Ramayana |
| Named mantra | `Gayatri Mantra` | Built-in + AI |

## Cost (estimated monthly)

| Service | Cost |
|---------|------|
| CloudFront | ~$0.01 |
| S3 | ~$0.01 |
| API Gateway | ~$0.05 |
| Lambda | ~$0.05 |
| Bedrock Claude Haiku | ~$1–3 (cached by CF) |
| **Total** | **~$1–4/month** |

## Deploy

```bash
# Prerequisites: AWS CLI configured, SAM CLI installed, Python 3.12+
cd /path/to/vd-meaning
./scripts/deploy.sh
```

## Local Development

```bash
cd lambda
pip install -r requirements.txt
sam local start-api --template infrastructure/template.yaml
# Open frontend/index.html in browser, or:
python3 -m http.server 8080 --directory frontend
```
