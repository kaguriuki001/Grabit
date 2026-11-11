from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
import yt_dlp, tempfile, os

app = FastAPI()

YDL_OPTS = {
    "quiet": True,
    "noplaylist": True,
    "no_warnings": True,
    "socket_timeout": 30,
    "extractor_args": {
        "youtube": {
            "player_client": ["tv", "web_embedded", "web"],
            "player_skip": ["webpage"]
        },
        "youtubepot-bgutilhttp": {
            "base_url": [os.environ.get("YT_DLP_POT_PROVIDER_URL", "http://127.0.0.1:4416")]
        }
    }
}

_cache = {}

@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse("index.html")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/info")
def info(url: str):
    if url in _cache:
        return _cache[url]
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            d = ydl.extract_info(url, download=False)

        fmts = [{"id": "best", "label": "⭐ Best quality (auto)"}]
        by_h = {}
        for f in d.get("formats", []):
            v = f.get("vcodec") or "none"
            a = f.get("acodec") or "none"
            h = f.get("height") or 0
            if v == "none" or not h:
                continue
            prog = a != "none"
            cur = by_h.get(h)
            if not cur or (prog and not cur["prog"]):
                by_h[h] = {"f": f, "prog": prog}

        for h in sorted(by_h, reverse=True)[:5]:
            e = by_h[h]
            f = e["f"]
            sz = f.get("filesize") or f.get("filesize_approx")
            size = f" · ~{round(sz/1048576,1)}MB" if sz else ""
            tag = "" if e["prog"] else " · video only"
            fmts.append({"id": f["format_id"],
                         "label": f"{h}p · {f.get('ext','mp4').upper()}{size}{tag}"})

        auds = [f for f in d.get("formats", [])
                if (f.get("vcodec") or "none") == "none"
                and (f.get("acodec") or "none") != "none"
                and f.get("ext") in ("m4a", "mp3")]
        if auds:
            a = auds[-1]
            sz = a.get("filesize") or a.get("filesize_approx")
            size = f" · ~{round(sz/1048576,1)}MB" if sz else ""
            fmts.append({"id": a["format_id"],
                         "label": f"🎵 Audio · {a.get('ext','m4a').upper()}{size}"})

        result = {"title": d["title"], "thumb": d.get("thumbnail", ""), "formats": fmts}
        _cache[url] = result
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/download")
def download(url: str, format_id: str):
    tmp = tempfile.mkdtemp()
    fmt = "best[ext=mp4]/best" if format_id == "best" else format_id
    with yt_dlp.YoutubeDL({**YDL_OPTS,
        "outtmpl": f"{tmp}/%(title)s.%(ext)s",
        "format": fmt}) as ydl:
        path = ydl.prepare_filename(ydl.extract_info(url, download=True))
    return FileResponse(path, filename=os.path.basename(path))