# Viewing Room

A tablet/phone projection & sound console with QR-code 2FA pairing, YouTube archive search, ambient soundboard, and an AI scene director (Groq).

## Run locally

```bash
python server.py
```

Then open:

- Tablet: http://localhost:8000/viewing_room.html
- Phone 2FA portal: http://<LAN-IP>:8000/auth_phone.html

## Configuration

Set these environment variables (or create a local `tokens.txt` with your `gsk_...` keys — never commit it):

- `YOUTUBE_API_KEY` — YouTube Data API v3 key
- `GROQ_API_KEYS` — comma-separated Groq API keys

## Notes

- `tokens.txt` is gitignored; keep secrets out of the repo.
- For a hosted static preview (GitHub Pages) only the UI loads; backend features (search, AI director, network info) require the Python server.
