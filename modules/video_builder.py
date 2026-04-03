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


def download_unsplash_images(title, tradition, sin_tag, save_dir, count=8):
    api_key = os.getenv("UNSPLASH_API_KEY")
    if not api_key:
        logging.error("UNSPLASH_API_KEY not found.")
        return []
        
    query = f"{title} {sin_tag} {tradition}".strip()
    logging.info(f"Unsplash Search dynamically querying: '{query}'")
    
    url = f"https://api.unsplash.com/photos/random"
    params = {"query": query, "orientation": "portrait", "count": count, "client_id": api_key}
    
    downloaded_paths = []
    try:
        res = requests.get(url, params=params)
        if res.status_code == 200:
            photos = res.json()
            for i, photo in enumerate(photos):
                img_url = photo["urls"]["regular"]
                save_path = os.path.join(save_dir, f"unsplash_{i}.jpg")
                with open(save_path, "wb") as f:
                    f.write(requests.get(img_url).content)
                downloaded_paths.append(save_path)
            logging.info(f"Successfully downloaded {len(downloaded_paths)} specific images from Unsplash.")
        else:
            logging.error(f"Unsplash API returned {res.status_code}: {res.text}")
    except Exception as e:
        logging.error(f"Unsplash query failed natively: {e}")
    
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
    FONT_SIZE = 80
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

    img_paths = download_unsplash_images(title_text, tradition, sin_tag, output_dir, count=8)
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
        logging.info(f"Injecting explicit 0.18 volume background track: {music_path}")
        music = AudioFileClip(music_path)
        music = afx.audio_loop(music, duration=voice_dur).volumex(0.18)
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
    
    logging.info(f"Writing single-layer massive payload to {final_video_path}... (MoviePy takes slightly longer natively due to frame filtering, be patient!)")
    final_video.write_videofile(final_video_path, fps=24, codec="libx264", audio_codec="aac", threads=4, logger=None)
    
    voice_audio.close()
    final_video.close()
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    build_video(args.date, args.force)

if __name__ == "__main__":
    main()
