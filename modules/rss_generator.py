"""
rss_generator.py
────────────────
Builds docs/feed.xml COMPLETELY FROM SCRATCH every run using plain string
building — no parsing of any existing XML file, ever.

Strategy:
  1. Copy the current episode's audio/video into docs/episodes/<date>/
  2. Scan ALL subdirectories of docs/episodes/ to discover every episode.
  3. For each episode folder, try to load title/description from the
     matching output/<date>/metadata.json + script_english.txt.
     If those files are missing, fall back to sensible defaults.
  4. Write a brand-new feed.xml with the exact root tag that declares
     both itunes and content namespaces so no prefix is ever unbound.
"""

import os
import json
import logging
import argparse
import shutil
from datetime import datetime, timezone
import email.utils

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ── Constants ─────────────────────────────────────────────────────────────────
BASE_URL      = "https://ayushranadev.github.io/eternal-record-pipeline"
CHANNEL_TITLE = "Eternal Record"
CHANNEL_DESC  = "Daily cinematic mythology stories — 90-second vertical videos."
AUTHOR_NAME   = "Ayush Rana"
AUTHOR_EMAIL  = "ranaayush6983@gmail.com"
COVER_URL     = f"{BASE_URL}/cover.jpg"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _xml_escape(text: str) -> str:
    """Minimal XML character escaping for text nodes."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
    )


def _load_episode_meta(date_str: str) -> tuple[str, str, str]:
    """
    Returns (title, description, pub_date_rfc2822) for a given date_str.
    Reads from output/<date>/metadata.json and script_english.txt if available.
    Falls back to generic values when files are missing.
    """
    output_dir    = os.path.join("output", date_str)
    meta_path     = os.path.join(output_dir, "metadata.json")
    script_path   = os.path.join(output_dir, "script_english.txt")

    title = f"Eternal Record – {date_str}"
    desc  = "A cinematic mythology story."

    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            title = meta.get("title", title)
        except Exception as exc:
            logging.warning(f"Could not read {meta_path}: {exc}")

    if os.path.exists(script_path):
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f.read().splitlines() if l.strip()]
            if lines:
                desc = " ".join(lines[:3])
        except Exception as exc:
            logging.warning(f"Could not read {script_path}: {exc}")

    # Try to derive a stable pub_date — handle both YYYY-MM-DD and YYYY-MM-DD-HH.
    pub_date = None
    for fmt in ("%Y-%m-%d-%H", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            pub_date = email.utils.format_datetime(dt)
            break
        except ValueError:
            continue
    if pub_date is None:
        pub_date = email.utils.format_datetime(datetime.now(tz=timezone.utc))

    return title, desc, pub_date


def _discover_episodes(episodes_root: str) -> list[str]:
    """
    Return all date-named subdirectories inside eps_root, sorted newest-first.
    A valid episode folder must contain both mixed_audio.mp3 and final_video.mp4.
    """
    if not os.path.isdir(episodes_root):
        return []

    valid = []
    for name in os.listdir(episodes_root):
        folder = os.path.join(episodes_root, name)
        if not os.path.isdir(folder):
            continue
        has_audio = os.path.exists(os.path.join(folder, "mixed_audio.mp3"))
        has_video = os.path.exists(os.path.join(folder, "final_video.mp4"))
        if has_audio and has_video:
            valid.append(name)
        else:
            logging.warning(
                f"Episode folder '{name}' skipped — missing audio or video."
            )

    valid.sort(reverse=True)   # newest date first
    return valid


def _build_item_xml(date_str: str, episodes_root: str) -> str:
    """Build a single <item> XML block for one episode."""
    folder      = os.path.join(episodes_root, date_str)
    aud_path    = os.path.join(folder, "mixed_audio.mp3")
    vid_path    = os.path.join(folder, "final_video.mp4")
    filesize_aud = os.path.getsize(aud_path)
    filesize_vid = os.path.getsize(vid_path)

    aud_url = f"{BASE_URL}/episodes/{date_str}/mixed_audio.mp3"
    vid_url = f"{BASE_URL}/episodes/{date_str}/final_video.mp4"

    title, desc, pub_date = _load_episode_meta(date_str)

    return f"""\
    <item>
      <title>{_xml_escape(title)}</title>
      <description>{_xml_escape(desc)}</description>
      <pubDate>{pub_date}</pubDate>
      <guid isPermaLink="false">{aud_url}</guid>
      <enclosure url="{aud_url}" length="{filesize_aud}" type="audio/mpeg"/>
      <enclosure url="{vid_url}" length="{filesize_vid}" type="video/mp4"/>
    </item>"""


def _build_feed_xml(item_blocks: list[str]) -> str:
    """Assemble the complete feed.xml string from scratch."""
    items_xml = "\n".join(item_blocks)
    now_rfc   = email.utils.format_datetime(datetime.now(tz=timezone.utc))

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"'
        ' xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"'
        ' xmlns:content="http://purl.org/rss/1.0/modules/content/">\n'
        "  <channel>\n"
        f"    <title>{_xml_escape(CHANNEL_TITLE)}</title>\n"
        f"    <description>{_xml_escape(CHANNEL_DESC)}</description>\n"
        f"    <link>{BASE_URL}</link>\n"
        "    <language>en-us</language>\n"
        f"    <lastBuildDate>{now_rfc}</lastBuildDate>\n"
        f"    <managingEditor>{AUTHOR_EMAIL} ({AUTHOR_NAME})</managingEditor>\n"
        f"    <itunes:author>{_xml_escape(AUTHOR_NAME)}</itunes:author>\n"
        "    <itunes:explicit>no</itunes:explicit>\n"
        f'    <itunes:image href="{COVER_URL}"/>\n'
        "    <itunes:owner>\n"
        f"      <itunes:name>{_xml_escape(AUTHOR_NAME)}</itunes:name>\n"
        f"      <itunes:email>{AUTHOR_EMAIL}</itunes:email>\n"
        "    </itunes:owner>\n"
        f"{items_xml}\n"
        "  </channel>\n"
        "</rss>\n"
    )


# ── Public API ────────────────────────────────────────────────────────────────

def generate_or_update_rss(date_str: str) -> bool:
    """
    Main entry point.

    1. Copies today's audio/video into docs/episodes/<date_str>/.
    2. Scans ALL episode folders under docs/episodes/.
    3. Builds a brand-new feed.xml from scratch — never reads the old one.
    """
    docs_dir     = "docs"
    episodes_root = os.path.join(docs_dir, "episodes")
    episode_dir  = os.path.join(episodes_root, date_str)
    rss_path     = os.path.join(docs_dir, "feed.xml")

    os.makedirs(episode_dir, exist_ok=True)

    # ── Locate today's source files ───────────────────────────────────────────
    output_dir = os.path.join("output", date_str)
    video_src  = os.path.join(output_dir, "final_video.mp4")
    audio_src  = os.path.join("ready-for-spotify", f"{date_str}_mixed_audio.mp3")

    if not os.path.exists(video_src):
        logging.error(f"Video missing: {video_src}")
        return False

    if not os.path.exists(audio_src):
        # Fallback: plain audio.mp3 produced by audio_generator
        audio_src = os.path.join(output_dir, "audio.mp3")
        if not os.path.exists(audio_src):
            logging.error(f"Audio missing (tried both ready-for-spotify and output dir)")
            return False
        logging.warning("Mixed audio not found — using plain audio.mp3 as fallback.")

    # ── Copy into episode folder ──────────────────────────────────────────────
    vid_dest = os.path.join(episode_dir, "final_video.mp4")
    aud_dest = os.path.join(episode_dir, "mixed_audio.mp3")

    shutil.copy2(video_src, vid_dest)
    shutil.copy2(audio_src, aud_dest)
    logging.info(f"Copied video → {vid_dest}")
    logging.info(f"Copied audio → {aud_dest}")

    # ── Discover all episodes and build feed from scratch ─────────────────────
    all_dates = _discover_episodes(episodes_root)
    if not all_dates:
        logging.error("No valid episode folders found under docs/episodes/")
        return False

    logging.info(f"Building feed.xml from scratch with {len(all_dates)} episode(s): {all_dates}")

    item_blocks = []
    for ep_date in all_dates:
        try:
            item_blocks.append(_build_item_xml(ep_date, episodes_root))
        except Exception as exc:
            logging.warning(f"Skipping episode {ep_date}: {exc}")

    feed_xml = _build_feed_xml(item_blocks)

    with open(rss_path, "w", encoding="utf-8") as f:
        f.write(feed_xml)

    logging.info("SUCCESS: docs/feed.xml rebuilt from scratch.")
    logging.info(f"RSS live at : {BASE_URL}/feed.xml")
    logging.info(f"Episodes    : {len(item_blocks)}")
    return True


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build Eternal Record RSS feed from scratch.")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Episode date (YYYY-MM-DD). Defaults to today.",
    )
    args = parser.parse_args()
    if not generate_or_update_rss(args.date):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
