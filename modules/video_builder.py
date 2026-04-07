import os
import json
import logging
import argparse
import random
import glob
import requests
import math
import subprocess
from itertools import cycle
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
load_dotenv()

ffmpeg_cmd = os.getenv("FFMPEG_PATH", "ffmpeg")
if os.getenv("FFMPEG_PATH"):
    os.environ["IMAGEIO_FFMPEG_EXE"] = os.getenv("FFMPEG_PATH")

from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips, CompositeAudioClip
import moviepy.audio.fx.all as afx


def download_images(title, tradition, sin_tag, save_dir, count=8):
    """
    Priority 1: Wikipedia Page Images (up to 4)
    Priority 2: Wikimedia Commons Search (historical artwork)
    Priority 3: Unsplash Story Title Keywords
    Priority 4: Fallback (Tradition/Sin theme)
    """
    downloaded_paths = []
    
    # --- ART STYLE MAPPING ---
    style_keywords = ""
    lower_tradition = tradition.lower().strip()
    if any(x in lower_tradition for x in ["mahabharata", "ramayana", "purana", "veda", "bhagavad gita", "upanishad", "hindu"]):
        style_keywords = "Indian Miniature Painting Pahari Kangra Basohli Art or Art related to the Stories Script"
    elif any(x in lower_tradition for x in ["greek", "olympus"]):
        style_keywords = "Ancient Greek Painting Art andancient  structures and art realted to the story "
    elif any(x in lower_tradition for x in ["roman", "classical"]):
        style_keywords = "Roman Fresco Pompeii Art Classical Sculpture and Roman painting structures or art related to the story"
    elif any(x in lower_tradition for x in ["norse", "viking", "odin"]):
        style_keywords = "Norse Wood Carving Viking Age Illustration or art related to the story"
    elif "bible" in lower_tradition or "testament" in lower_tradition:
        style_keywords = "Renaissance Biblical Art Classic Illustration or  museums art related to story and theme and structures"

    query = f"{title} {tradition} {style_keywords}".strip()
    
    headers = {"User-Agent": "EternalRecord/1.0 (ranaayush6983@gmail.com)"}
    
    # --- Priority 1: Wikipedia API (Story specific artwork) ---
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "origin": "*"
        }
        res = requests.get(search_url, params=search_params, headers=headers, timeout=10)
        if res.status_code == 200:
            search_results = res.json().get("query", {}).get("search", [])
            if search_results:
                page_title = search_results[0]["title"]
                logging.info(f"Priority 1: Wikipedia page found: '{page_title}'")
                
                img_query_params = {
                    "action": "query",
                    "titles": page_title,
                    "generator": "images",
                    "gimlmt": 12,
                    "prop": "imageinfo",
                    "iiprop": "url",
                    "format": "json",
                    "origin": "*"
                }
                img_res = requests.get(search_url, params=img_query_params, headers=headers, timeout=10)
                if img_res.status_code == 200:
                    pages = img_res.json().get("query", {}).get("pages", {})
                    wiki_imgs = []
                    for page_id, page_data in pages.items():
                        img_info = page_data.get("imageinfo", [{}])[0]
                        img_url = img_info.get("url")
                        if img_url:
                            ext = img_url.split(".")[-1].lower()
                            if ext in ["jpg", "jpeg", "png"] and "icon" not in img_url.lower() and "logo" not in img_url.lower():
                                wiki_imgs.append(img_url)
                    
                    for i, img_url in enumerate(wiki_imgs[:4]):
                        try:
                            img_data = requests.get(img_url, headers=headers, timeout=15).content
                            save_path = os.path.join(save_dir, f"wiki_{len(downloaded_paths)}.jpg")
                            with open(save_path, "wb") as f:
                                f.write(img_data)
                            downloaded_paths.append(save_path)
                            if len(downloaded_paths) >= count: break
                        except: continue
                    if wiki_imgs:
                        logging.info(f"Priority 1: Downloaded {len(downloaded_paths)} images from Wikipedia.")
    except Exception as e:
        logging.warning(f"Priority 1 (Wikipedia) failed: {e}")

    if len(downloaded_paths) >= count: return downloaded_paths

    # --- Priority 2: Wikimedia Commons Search ---
    try:
        commons_url = "https://commons.wikimedia.org/w/api.php"
        commons_params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "prop": "imageinfo",
            "iiprop": "url",
            "gsrlimit": 10,
            "format": "json",
            "origin": "*"
        }
        res = requests.get(commons_url, params=commons_params, headers=headers, timeout=10)
        if res.status_code == 200:
            pages = res.json().get("query", {}).get("pages", {})
            found_commons = 0
            for page_id, page_data in pages.items():
                img_info = page_data.get("imageinfo", [{}])[0]
                img_url = img_info.get("url")
                if img_url:
                    try:
                        ext = img_url.split(".")[-1].lower()
                        if ext not in ["jpg", "jpeg", "png"]: continue
                        img_data = requests.get(img_url, headers=headers, timeout=15).content
                        save_path = os.path.join(save_dir, f"commons_{len(downloaded_paths)}.jpg")
                        with open(save_path, "wb") as f:
                            f.write(img_data)
                        downloaded_paths.append(save_path)
                        found_commons += 1
                        if len(downloaded_paths) >= count: break
                    except: continue
            if found_commons > 0:
                logging.info(f"Priority 2: Downloaded {found_commons} images from Wikimedia Commons. Total now: {len(downloaded_paths)}")
    except Exception as e:

        logging.warning(f"Priority 2 (Commons) failed: {e}")

    if len(downloaded_paths) >= count: return downloaded_paths

    # --- Priority 3: Unsplash with specific keywords ---
    api_key = os.getenv("UNSPLASH_API_KEY")
    if api_key:
        title_keywords = " ".join(title.split()[:3])
        unsplash_query = f"{title_keywords} {tradition} {style_keywords}".strip()
        logging.info(f"Priority 3: Querying Unsplash with '{unsplash_query}'")
        url = "https://api.unsplash.com/photos/random"
        params = {"query": unsplash_query, "orientation": "portrait",
                  "count": count - len(downloaded_paths), "client_id": api_key}
        try:
            res = requests.get(url, params=params, timeout=15)
            if res.status_code == 200:
                photos = res.json()
                if isinstance(photos, list):
                    for photo in photos:
                        img_url = photo["urls"]["regular"]
                        save_path = os.path.join(save_dir, f"unsplash_p3_{len(downloaded_paths)}.jpg")
                        with open(save_path, "wb") as f:
                            f.write(requests.get(img_url, timeout=15).content)
                        downloaded_paths.append(save_path)
                    logging.info(f"Priority 3: Downloaded images from Unsplash Keywords. Total now: {len(downloaded_paths)}")
        except Exception as e:
            logging.warning(f"Priority 3 (Unsplash Keywords) failed: {e}")

    if len(downloaded_paths) >= count: return downloaded_paths

    # --- Priority 4: Tradition/Sin theme Fallback ---
    tradition_queries = {
        "mahabharata":   "Indian Miniature Painting Mahabharata Kurukshetra Warrior", 
        "ramayana":      "Indian Miniature Painting Ramayana Temple Ancient India",
        "greek":         "Ancient Greek Mythology Vase Painting Olympian God", 
        "roman":         "Ancient Roman Fresco Classical Sculpture",
        "bible":         "Renaissance Biblical Painting Classical Art", 
        "upanishad":     "Cosmos Cosmic Indian Art Meditation",
        "upanishads":    "Cosmos Cosmic Indian Art Meditation", 
        "rigveda":       "Sacred Ritual Fire Ancient Indian Art",
        "yajurveda":     "Sacred Ritual Ancient India Art", 
        "atharvaveda":   "Mystical Ancient Indian Tantra Art",
        "samaveda":      "Sacred Chant Indian Art Ancient", 
        "garuda purana": "Cosmology Afterlife Indian Miniature Painting",
        "norse":         "Norse Wood Carving Viking Age Illustration Mythology", 
        "king":          "Medieval Illustration Manuscript Throne",
    }
    sin_queries = {
        "pride": "golden crown glory", "wrath": "storm fire dramatic",
        "envy": "shadow dark mirror", "greed": "gold treasure ancient",
        "lust": "rose petals dramatic", "sloth": "misty abandoned ruins",
        "gluttony": "feast abundance ancient",
    }

    trad_phrase = tradition_queries.get(tradition.lower().strip(), "ancient mythology")
    sin_phrase  = sin_queries.get(sin_tag.lower().strip(), "dramatic cinematic")

    query_attempts = [f"{trad_phrase} {sin_phrase}", trad_phrase, sin_phrase, "ancient mythology dramatic"]

    if api_key:
        for q in query_attempts:
            if len(downloaded_paths) >= count: break
            logging.info(f"Priority 4: Fallback querying Unsplash: '{q}'")
            params = {"query": q, "orientation": "portrait", "count": count - len(downloaded_paths), "client_id": api_key}
            try:
                res = requests.get(url, params=params, timeout=15)
                if res.status_code == 200:
                    photos = res.json()
                    if isinstance(photos, list):
                        for photo in photos:
                            img_url = photo["urls"]["regular"]
                            save_path = os.path.join(save_dir, f"unsplash_p4_{len(downloaded_paths)}.jpg")
                            with open(save_path, "wb") as f:
                                f.write(requests.get(img_url, timeout=15).content)
                            downloaded_paths.append(save_path)
            except: continue

    return downloaded_paths



def bake_image_with_pillow(input_path, output_path, title_text):
    img = Image.open(input_path).convert("RGBA")
    
    target_ratio = 1080 / 1920
    img_ratio = img.width / img.height
    
    if img_ratio > target_ratio:
        new_w = int(img.height * target_ratio)
        off = (img.width - new_w) // 2
        img = img.crop((off, 0, off + new_w, img.height))
    else:
        new_h = int(img.width / target_ratio)
        off = (img.height - new_h) // 2
        img = img.crop((0, off, img.width, off + new_h))
        
    img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
    
    # Dark overlay to make text clearly readable
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 130))
    img = Image.alpha_composite(img, overlay)
    
    draw = ImageDraw.Draw(img)
    FONT_SIZE = 65
    _font_candidates = [
        "arialbd.ttf",                                                          # Windows
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",                # Ubuntu/Debian (GitHub Actions)
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",        # CentOS/RHEL
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",                 # Fallback Linux
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",                    # Noto
    ]
    font_title = None
    for _fp in _font_candidates:
        try:
            font_title = ImageFont.truetype(_fp, FONT_SIZE)
            logging.info(f"Title font loaded: {_fp} @ {FONT_SIZE}px")
            break
        except Exception:
            continue
    if font_title is None:
        try:
            font_title = ImageFont.load_default(size=FONT_SIZE)  # Pillow >= 10.1
        except TypeError:
            font_title = ImageFont.load_default()
        logging.warning("No TrueType font found — using Pillow default font (may appear small)")
            
    # Logic to wrap Title organically at the top
    y = 60
    def chunk_text(text, font, max_width):
        words = text.split()
        chunks = []
        current_chunk = []
        for word in words:
            current_chunk.append(word)
            test_line = " ".join(current_chunk)
            w = draw.textlength(test_line, font=font) if hasattr(draw, 'textlength') else draw.textsize(test_line, font=font)[0]
            if w > max_width:
                current_chunk.pop()
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        return chunks

    title_lines = chunk_text(title_text, font_title, 900)[:2]

    for line in title_lines:
        if hasattr(draw, 'textbbox'):
            bbox = draw.textbbox((0, 0), line, font=font_title)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        else:
            w, h = draw.textsize(line, font=font_title)
            
        x = (1080 - w) // 2
        draw.text((x+5, y+5), line, font=font_title, fill="black") # deep shadow
        draw.text((x, y), line, font=font_title, fill="#FFD700") # Gold explicit text
        y += h + 15

    img.convert("RGB").save(output_path, "JPEG", quality=95)

def get_random_music():
    music_files = glob.glob("assets/music/*.mpeg") + glob.glob("assets/music/*.mp3")
    if not music_files:
        return None
    return random.choice(music_files)

# ------------- NATIVE SUBTITLES (PILLOW) -------------
def parse_and_group_srt(srt_path, max_words=6):
    import re
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.+?)(?=\n\n|\Z)', re.DOTALL)
    
    def time_to_sec(t):
        if not t: return 0
        h, m, s_ms = t.split(':')
        s, ms = s_ms.split(',')
        return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0

    raw_words = []
    for match in pattern.finditer(content):
        start = time_to_sec(match.group(2))
        end = time_to_sec(match.group(3))
        text = match.group(4).strip().replace('\n', ' ')
        raw_words.append({"start": start, "end": end, "text": text})

    grouped = []
    current_chunk = []
    current_start = 0

    for idx, w in enumerate(raw_words):
        if not current_chunk:
            current_start = w["start"]
        current_chunk.append(w["text"])
        
        flush = False
        if len(current_chunk) >= max_words:
            flush = True
        elif idx < len(raw_words) - 1:
            next_start = raw_words[idx+1]["start"]
            if next_start - w["end"] > 0.4:  # long pause
                flush = True
        else:
            flush = True
            
        if flush:
            grouped.append((current_start, w["end"], " ".join(current_chunk)))
            current_chunk = []

    return grouped

def draw_subtitles_on_frame(frame, t, subs, font_sub):
    import numpy as np
    from PIL import Image, ImageDraw
    
    active_text = ""
    for (start, end, text) in subs:
        if start <= t <= end + 0.15: # 150ms trailing buffer 
            active_text = text
            break
            
    if not active_text:
        return frame
        
    img = Image.fromarray(frame)
    draw = ImageDraw.Draw(img)
    
    y = 1920 - 200 # 200px strictly from bottom
    
    if hasattr(draw, 'textbbox'):
        bbox = draw.textbbox((0, 0), active_text, font=font_sub)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
    else:
        w, h = draw.textsize(active_text, font=font_sub)
        
    x = (1080 - w) // 2
    
    # Very thin black shadow/outline (Bold if font natively is bold)
    thickness = 2
    outline_color = "black"
    for dx in range(-thickness, thickness+1):
        for dy in range(-thickness, thickness+1):
            if dx*dx + dy*dy <= thickness*thickness:
                 draw.text((x+dx, y+dy), active_text, font=font_sub, fill=outline_color)
                 
    # Primary Text fill white natively, no background box
    draw.text((x, y), active_text, font=font_sub, fill="white")
    
    return np.array(img)
# -----------------------------------------------------

def build_video(date_str, force=False):
    output_dir = os.path.join("output", date_str)
    audio_path = os.path.join(output_dir, "audio.mp3")
    metadata_path = os.path.join(output_dir, "metadata.json")
    srt_path = os.path.join(output_dir, "subtitles.srt")
    final_video_path = os.path.join(output_dir, "final_video.mp4")

    if not os.path.exists(audio_path):
        logging.error(f"Voice audio completely missing at {audio_path}.")
        return False
        
    if not os.path.exists(metadata_path):
        logging.error(f"Metadata missing at {metadata_path}.")
        return False

    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    title_text = meta.get('title', 'Historical Legend')
    tradition = meta.get('tradition', '')
    sin_tag = meta.get('sin_tag', '')

    img_paths = download_images(title_text, tradition, sin_tag, output_dir, count=8)
    if not img_paths:
        logging.error("UNSPLASH_API_KEY missing or quota exceeded — using gradient fallback.")
        dumb_img = os.path.join(output_dir, "unsplash_0.jpg")
        os.makedirs(output_dir, exist_ok=True)
        # Dark cinematic gradient fallback (navy → black) instead of solid black
        import numpy as np
        h, w = 1920, 1080
        gradient = np.zeros((h, w, 3), dtype=np.uint8)
        for row in range(h):
            t = row / h
            r = int(10 + (20 - 10) * t)
            g = int(10 + (15 - 10) * t)
            b = int(40 + (10 - 40) * t)
            gradient[row, :] = [r, g, b]
        Image.fromarray(gradient, "RGB").save(dumb_img)
        img_paths = [dumb_img]

    baked_paths = []
    for i, path in enumerate(img_paths):
        baked = os.path.join(output_dir, f"baked_{i}.jpg")
        bake_image_with_pillow(path, baked, title_text)
        baked_paths.append(baked)

    logging.info("Building cinematic Audio/Visual blocks in MoviePy...")
    voice_audio = AudioFileClip(audio_path)
    voice_dur = voice_audio.duration
    
    final_audio = voice_audio
    music_path = get_random_music()
    if music_path:
        logging.info(f"Injecting explicit 0.22 volume background track: {music_path}")
        music = AudioFileClip(music_path)
        music = afx.audio_loop(music, duration=voice_dur).volumex(0.22)
        final_audio = CompositeAudioClip([voice_audio, music])
        
        spotify_dir = "ready-for-spotify"
        os.makedirs(spotify_dir, exist_ok=True)
        spotify_mixed_path = os.path.join(spotify_dir, f"{date_str}_mixed_audio.mp3")
        logging.info(f"Pushing seamless Mixed Audio file format to {spotify_mixed_path} natively...")
        final_audio.write_audiofile(spotify_mixed_path, fps=44100, logger=None)

    clip_dur = 10.0
    fade_duration = 1.0
    N = int(max(len(baked_paths), math.ceil((voice_dur - fade_duration) / (clip_dur - fade_duration))))
    
    baked_cycle = cycle(baked_paths)
    clips = []
    
    logging.info(f"Instantiating exactly {N} looping visually stacked 10-second Ken-Burns zooms.")
    for i in range(N):
        b_path = next(baked_cycle)
        img_clip = ImageClip(b_path).set_duration(clip_dur)
        zoomed = img_clip.resize(lambda t: 1 + 0.05 * (t / clip_dur)).set_position(("center", "center"))
        zoomed = zoomed.on_color(size=(1080, 1920), color=(0,0,0))
        
        if i > 0:
            zoomed = zoomed.crossfadein(fade_duration)
        clips.append(zoomed)
        
    final_video = concatenate_videoclips(clips, padding=-fade_duration, method="compose")
    
    # Subtitles bypassed as completely requested!
    logging.info("Subtitles bypassed. Moving to final encoding layer...")
    
    final_video = final_video.set_audio(final_audio).set_duration(voice_dur)
    
    try:
        logging.info(f"Writing single-layer massive payload to {final_video_path}... (MoviePy takes slightly longer natively due to frame filtering, be patient!)")
        final_video.write_videofile(final_video_path, fps=24, codec="libx264", audio_codec="aac", threads=4, logger=None)
    finally:
        # EXPLICIT CLEANUP to avoid [WinError 6] The handle is invalid on Windows
        import gc
        try:
            voice_audio.close()
        except: pass
        try:
            if 'music' in locals():
                music.close()
        except: pass
        try:
            if 'final_audio' in locals() and final_audio != voice_audio:
                final_audio.close()
        except: pass
        try:
            final_video.close()
        except: pass
        
        for c in clips:
            try:
                c.close()
            except: pass
        
        # Force garbage collection to ensure FFMPEG handles are released before script ends
        gc.collect()

    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    build_video(args.date, args.force)

if __name__ == "__main__":
    main()
