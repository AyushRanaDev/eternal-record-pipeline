import os
import json
import logging
import argparse
import shutil
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import email.utils
from urllib.parse import quote

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

BASE_URL = "https://ayushranadev.github.io/eternal-record-pipeline"

def generate_or_update_rss(date_str):
    docs_dir = "docs"
    # Each episode gets its OWN dated subfolder for clean public URLs
    episode_dir = os.path.join(docs_dir, "episodes", date_str)
    rss_path = os.path.join(docs_dir, "feed.xml")

    os.makedirs(episode_dir, exist_ok=True)

    output_dir = os.path.join("output", date_str)
    video_src  = os.path.join(output_dir, "final_video.mp4")
    # Mixed audio lives in ready-for-spotify/ (produced by video_builder.py)
    audio_src  = os.path.join("ready-for-spotify", f"{date_str}_mixed_audio.mp3")
    metadata_path = os.path.join(output_dir, "metadata.json")
    script_path   = os.path.join(output_dir, "script_english.txt")

    # ── Validate sources ──────────────────────────────────────────────────────
    if not os.path.exists(video_src):
        logging.error(f"Video missing: {video_src}")
        return False
    if not os.path.exists(audio_src):
        # Fallback: try plain audio.mp3 produced by audio_generator
        audio_src = os.path.join(output_dir, "audio.mp3")
        if not os.path.exists(audio_src):
            logging.error(f"Audio missing: {audio_src}")
            return False
        logging.warning("Mixed audio not found — using plain audio.mp3 as fallback.")

    # ── Load metadata ─────────────────────────────────────────────────────────
    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    with open(script_path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.read().split('\n') if l.strip()]

    title_text = meta.get("title", "A Cinematic Legend")
    desc_text  = " ".join(lines[:3])

    # ── Copy files to docs/episodes/YYYY-MM-DD/ with clean names ─────────────
    vid_dest = os.path.join(episode_dir, "final_video.mp4")
    aud_dest = os.path.join(episode_dir, "mixed_audio.mp3")

    shutil.copy2(video_src, vid_dest)
    shutil.copy2(audio_src, aud_dest)
    logging.info(f"Copied video → {vid_dest}")
    logging.info(f"Copied audio → {aud_dest}")

    filesize_vid = os.path.getsize(vid_dest)
    filesize_aud = os.path.getsize(aud_dest)

    # ── Build public URLs ─────────────────────────────────────────────────────
    # https://ayushranadev.github.io/eternal-record-pipeline/episodes/YYYY-MM-DD/final_video.mp4
    # https://ayushranadev.github.io/eternal-record-pipeline/episodes/YYYY-MM-DD/mixed_audio.mp3
    file_url_vid = f"{BASE_URL}/episodes/{date_str}/final_video.mp4"
    file_url_aud = f"{BASE_URL}/episodes/{date_str}/mixed_audio.mp3"

    pub_date = email.utils.format_datetime(datetime.now().astimezone())

    # ── Build / update RSS XML ────────────────────────────────────────────────
    if not os.path.exists(rss_path):
        logging.info("Creating new docs/feed.xml ...")
        rss = ET.Element("rss", {
            "version": "2.0",
            "xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
            "xmlns:content": "http://purl.org/rss/1.0/modules/content/"
        })
        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text       = "Eternal Record"
        ET.SubElement(channel, "description").text = "Daily cinematic mythology stories — 90-second vertical videos."
        ET.SubElement(channel, "link").text        = BASE_URL
        ET.SubElement(channel, "language").text    = "en-us"
        ET.SubElement(channel, "itunes:explicit").text = "no"
        itunes_img = ET.SubElement(channel, "itunes:image")
        itunes_img.set("href", f"{BASE_URL}/cover.jpg")
    else:
        logging.info("Updating existing docs/feed.xml ...")
        tree    = ET.parse(rss_path)
        rss     = tree.getroot()
        channel = rss.find("channel")

    # Build the <item> — Spotify uses the FIRST <enclosure> (audio/mpeg)
    item = ET.Element("item")
    ET.SubElement(item, "title").text                  = title_text
    ET.SubElement(item, "description").text            = desc_text
    ET.SubElement(item, "pubDate").text                = pub_date
    ET.SubElement(item, "guid", isPermaLink="false").text = file_url_aud

    # Primary enclosure: audio (Spotify/Anchor reads this)
    enc_aud = ET.SubElement(item, "enclosure")
    enc_aud.set("url",    file_url_aud)
    enc_aud.set("length", str(filesize_aud))
    enc_aud.set("type",   "audio/mpeg")

    # Secondary enclosure: video
    enc_vid = ET.SubElement(item, "enclosure")
    enc_vid.set("url",    file_url_vid)
    enc_vid.set("length", str(filesize_vid))
    enc_vid.set("type",   "video/mp4")

    # Prepend so newest episode appears first
    insert_at = (list(channel).index(channel.find("item"))
                 if channel.find("item") is not None
                 else len(channel))
    channel.insert(insert_at, item)

    # ── Serialise ─────────────────────────────────────────────────────────────
    xml_str    = ET.tostring(rss, encoding="utf-8")
    parsed_xml = minidom.parseString(xml_str)
    pretty_xml = parsed_xml.toprettyxml(indent="  ")
    pretty_xml = "\n".join(l for l in pretty_xml.split("\n") if l.strip())

    with open(rss_path, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    logging.info(f"SUCCESS: Episode added to docs/feed.xml")
    logging.info(f"RSS live at: {BASE_URL}/feed.xml")
    logging.info(f"Audio URL:   {file_url_aud}")
    logging.info(f"Video URL:   {file_url_vid}")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    if not generate_or_update_rss(args.date):
        exit(1)

if __name__ == "__main__":
    main()
