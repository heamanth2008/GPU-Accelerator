from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from ytmusicapi import YTMusic
import uvicorn
import os
import time

app = FastAPI(title="Neuro Music API", version="2.0.0")

# Allow all origins for local dev / Render deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ytmusic = YTMusic()

# Simple in-memory search cache {query: (timestamp, results)}
_search_cache: dict = {}
CACHE_TTL = 300  # 5 minutes

# Path to frontend directory
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")


# --- Health endpoint (used by UptimeRobot every 5 min to prevent cold starts) ---
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Neuro Music", "timestamp": int(time.time())}


# --- Search ---------------------------------------------------------------
@app.get("/api/search")
def search_music(q: str):
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Search query is required")

    # Check cache
    cached = _search_cache.get(q.lower())
    if cached and (time.time() - cached[0]) < CACHE_TTL:
        return {"results": cached[1], "cached": True}

    print(f"Searching YouTube Music for: {q}")
    try:
        results = ytmusic.search(q, filter="songs", limit=20)
    except Exception as exc:
        print(f"YouTube Music search failed: {exc}")
        raise HTTPException(status_code=502, detail="YouTube Music search is unavailable") from exc

    formatted_results = []
    for idx, item in enumerate(results):
        try:
            vid = item.get("videoId")
            if not vid:
                continue

            hash_val = sum(ord(c) for c in vid)
            hue1 = hash_val % 360
            hue2 = (hue1 + 45) % 360
            grad = f"linear-gradient(135deg, hsl({hue1}, 80%, 25%), hsl({hue2}, 80%, 40%))"

            artist_name = item["artists"][0]["name"] if item.get("artists") else "Unknown Artist"
            album_name = item["album"]["name"] if item.get("album") else "Single"
            dur = item.get("duration_seconds", 0) or 0

            formatted_results.append({
                "id": hash_val + idx,
                "ytId": vid,
                "title": item.get("title", "Unknown Title"),
                "artist": artist_name,
                "album": album_name,
                "dur": dur,
                "icon": "music",
                "grad": grad,
                "genre": "YouTube Music",
            })
        except Exception as e:
            print(f"Error parsing search result item: {e}")

    # Store in cache
    _search_cache[q.lower()] = (time.time(), formatted_results)

    return {"results": formatted_results, "cached": False}


# --- Static pages ---------------------------------------------------------
@app.get("/login")
def serve_login():
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))


@app.get("/")
def serve_index():
    # Serve the glass UI home page as the default landing page
    return FileResponse(os.path.join(FRONTEND_DIR, "glass_home.html"))


# Mount all other static assets (CSS, JS, images, etc.)
app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="frontend")


if __name__ == "__main__":
    print("Starting Neuro Music Backend on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)

