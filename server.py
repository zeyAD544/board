#!/usr/bin/env python3
"""
Viewing Room - Secure Backend Server
- Hosts static files (viewing_room.html, auth_phone.html)
- Protects YouTube & Groq API credentials (never exposed to frontend)
- Groq AI Scene Director using openai/gpt-oss-120b with 4-key fallback
- Local network detection for QR-code 2FA phone pairing
"""

import http.server
import socketserver
import urllib.request
import urllib.parse
import urllib.error
import json
import re
import os
import socket
import sys

PORT = 8000
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

# YouTube API Secret Key (Kept strictly on backend)
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

def get_local_ip():
    """Detect the local machine IP on the LAN for QR pairing."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def load_groq_keys():
    """Load and parse all Groq API keys from tokens.txt."""
    tokens_path = os.path.join(WORKSPACE_DIR, 'tokens.txt')
    keys = []
    if os.path.exists(tokens_path):
        try:
            with open(tokens_path, 'r', encoding='utf-8') as f:
                content = f.read()
                keys = re.findall(r'gsk_[A-Za-z0-9]+', content)
        except Exception as e:
            print(f"[AUTH ERROR] Failed reading tokens.txt: {e}")
    if not keys:
        # Allow keys from environment (comma-separated) as a fallback to tokens.txt
        env_keys = os.environ.get("GROQ_API_KEYS", "")
        if env_keys:
            keys = [k.strip() for k in env_keys.split(",") if k.strip()]
    return keys

GROQ_KEYS = load_groq_keys()
print(f"[GROQ] Loaded {len(GROQ_KEYS)} Groq API keys (1 Main, {len(GROQ_KEYS)-1} Fallbacks).")

class SecureViewingRoomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WORKSPACE_DIR, **kwargs)

    def end_headers(self):
        # Enable CORS for cross-device tablet/phone requests
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. Network Info Endpoint (Used by Tablet to construct Mobile QR URL)
        if path == '/api/network-info':
            local_ip = get_local_ip()
            host_header = self.headers.get('Host', '')
            host_ip = host_header.split(':')[0] if host_header else local_ip
            # If accessed via localhost, recommend the actual LAN IP for mobile scanning
            recommended_ip = local_ip if host_ip in ('localhost', '127.0.0.1') else host_ip

            data = {
                "localIp": local_ip,
                "port": PORT,
                "recommendedHost": f"{recommended_ip}:{PORT}",
                "authPhoneUrl": f"http://{recommended_ip}:{PORT}/auth_phone.html"
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
            return

        # 2. YouTube Search Proxy (API Key stays strictly hidden on backend)
        if path == '/api/youtube/search':
            q = query.get('q', [''])[0]
            page_token = query.get('pageToken', [''])[0]
            max_results = query.get('maxResults', ['24'])[0]

            if not q:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing search query parameter 'q'"}).encode('utf-8'))
                return

            yt_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&q={urllib.parse.quote(q)}&maxResults={max_results}&key={YOUTUBE_API_KEY}"
            if page_token:
                yt_url += f"&pageToken={urllib.parse.quote(page_token)}"

            try:
                req = urllib.request.Request(yt_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw = resp.read()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(raw)
                    return
            except urllib.error.HTTPError as he:
                err_content = he.read().decode('utf-8', errors='ignore')
                self.send_response(he.code)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(err_content.encode('utf-8'))
                return
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"YouTube proxy error: {str(e)}"}).encode('utf-8'))
                return

        # Fallback to static file server
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 3. Groq Scene Director AI using openai/gpt-oss-120b with 4-key fallback
        if path == '/api/groq/organize':
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len).decode('utf-8')
            try:
                req_data = json.loads(body) if body else {}
            except Exception:
                req_data = {}

            scene_ctx = req_data.get('sceneContext', {})
            current_film = scene_ctx.get('currentFilm', 'Atmospheric Ambient Projection')
            current_score = scene_ctx.get('currentScore', 'Ambient Drone')
            cue_queue = scene_ctx.get('cueQueue', [])
            ambient_state = scene_ctx.get('soundboard', {})
            lighting_mode = scene_ctx.get('lightingMode', 'normal')
            focus_mode = scene_ctx.get('focusMode', 'Standard Viewing')

            system_prompt = (
                "You are an avant-garde Cinema Director and Master Sound Engineer for a private high-end screening room. "
                "Analyze the user's current screening room setup and produce an intelligent, artistically cohesive scene arrangement. "
                "You MUST output valid JSON matching this schema:\n"
                "{\n"
                "  \"sceneMood\": \"Short 3-5 word evocative phrase (e.g. Rainy Neo-Noir Solitude, Ethereal Studio Ghibli Meadow)\",\n"
                "  \"directorNotes\": \"2-3 sentence cinematic analysis and rationale for the recommended ambiance.\",\n"
                "  \"recommendedFilm\": {\n"
                "    \"title\": \"Compelling film or projection title\",\n"
                "    \"searchQuery\": \"Specific search query for YouTube search\",\n"
                "    \"reason\": \"Why this film complements the current scene\"\n"
                "  },\n"
                "  \"recommendedSoundtrack\": {\n"
                "    \"title\": \"Acoustic score or ambient piece title\",\n"
                "    \"searchQuery\": \"Specific search query for YouTube audio search\",\n"
                "    \"tempo\": \"e.g. 55 BPM Slow Pulse / 40Hz Isochronic Flow\",\n"
                "    \"reason\": \"How it balances the visual frequencies\"\n"
                "  },\n"
                "  \"soundboardPresets\": {\n"
                "    \"projectorVolume\": 0 to 100 integer,\n"
                "    \"rainVolume\": 0 to 100 integer,\n"
                "    \"fireVolume\": 0 to 100 integer\n"
                "  },\n"
                "  \"recommendedLighting\": \"amber\" or \"candlelight\" or \"dimmer\",\n"
                "  \"djCrossfaderHint\": \"Recommended mix level (e.g. -3dB balanced score)\"\n"
                "}"
            )

            user_prompt = (
                f"CURRENT SCREENING ROOM TELEMETRY:\n"
                f"- Currently Playing Visual Film: {current_film}\n"
                f"- Currently Playing Acoustic Score: {current_score}\n"
                f"- Cue Queue Count: {len(cue_queue)} items (Current items: {[q.get('title') for q in cue_queue[:3]]})\n"
                f"- Ambient Soundboard Levels: Projector {ambient_state.get('projector', 0)}%, Rain {ambient_state.get('rain', 0)}%, Fire {ambient_state.get('fire', 0)}%\n"
                f"- Screen Lighting State: {lighting_mode}\n"
                f"- Focus / Frequency Mode: {focus_mode}\n\n"
                f"Curate the next master scene configuration."
            )

            # Try keys with fallback cascade (Key 1 -> Key 2 -> Key 3 -> Key 4)
            keys = load_groq_keys()
            last_err = None
            successful_res = None
            active_key_index = None

            for idx, key in enumerate(keys):
                print(f"[GROQ] Calling openai/gpt-oss-120b using Key #{idx+1} ({key[:10]}...)...")
                payload = {
                    "model": "openai/gpt-oss-120b",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.65,
                    "max_tokens": 600
                }
                
                try:
                    groq_req = urllib.request.Request(
                        "https://api.groq.com/openai/v1/chat/completions",
                        data=json.dumps(payload).encode('utf-8'),
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                        }
                    )
                    with urllib.request.urlopen(groq_req, timeout=15) as resp:
                        res_json = json.loads(resp.read().decode('utf-8'))
                        content = res_json['choices'][0]['message']['content']
                        parsed_content = json.loads(content)
                        successful_res = parsed_content
                        active_key_index = idx + 1
                        print(f"[GROQ] Success with Key #{active_key_index}!")
                        break
                except urllib.error.HTTPError as he:
                    err_msg = he.read().decode('utf-8', errors='ignore')
                    print(f"[GROQ WARN] Key #{idx+1} returned HTTP {he.code}: {err_msg[:120]}")
                    last_err = f"HTTP {he.code}: {err_msg[:100]}"
                    # Continue to next fallback key
                    continue
                except Exception as ex:
                    print(f"[GROQ WARN] Key #{idx+1} failed: {ex}")
                    last_err = str(ex)
                    continue

            if successful_res:
                response_obj = {
                    "success": True,
                    "model": "openai/gpt-oss-120b",
                    "keyIndex": active_key_index,
                    "totalKeys": len(keys),
                    "directorPlan": successful_res
                }
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response_obj).encode('utf-8'))
                return
            else:
                self.send_response(502)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": f"All Groq keys failed. Last error: {last_err}"
                }).encode('utf-8'))
                return

        self.send_response(404)
        self.end_headers()

def run_server():
    local_ip = get_local_ip()
    print("=" * 65)
    print(f"🎬 VIEWING ROOM - SECURE GATEWAY & BACKEND SERVER ACTIVE")
    print(f"   Local Access:     http://localhost:{PORT}/viewing_room.html")
    print(f"   Tablet/LAN:       http://{local_ip}:{PORT}/viewing_room.html")
    print(f"   Phone 2FA Portal: http://{local_ip}:{PORT}/auth_phone.html")
    print(f"   Protected APIs:   YouTube Search + Groq openai/gpt-oss-120b")
    print("=" * 65)

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), SecureViewingRoomHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
            httpd.server_close()

if __name__ == '__main__':
    run_server()
