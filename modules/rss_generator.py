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

def get_repo_url():
    return "https://ayushranadev.github.io/eternal-record-pipeline"

def generate_or_update_rss(date_str):
    docs_dir = "docs"
    episodes_dir = os.path.join(docs_dir, "episodes")
    rss_path = os.path.join(docs_dir, "feed.xml")
    
    os.makedirs(episodes_dir, exist_ok=True)
    
    output_dir = os.path.join("output", date_str)
    video_path = os.path.join(output_dir, "final_video.mp4")
    audio_path = os.path.join(output_dir, "audio.mp3")
    metadata_path = os.path.join(output_dir, "metadata.json")
    script_path = os.path.join(output_dir, "script_english.txt")
    
    if not os.path.exists(video_path):
        logging.error(f"Target Video strictly completely missing: {video_path}")
        return False
        
    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    with open(script_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.read().split('\n') if line.strip()]
        
    title_text = meta.get("title", 'A Cinematic Legend')
    desc_text = "\n".join(lines[:3])
    
    # 1) Video
    file_name_vid = f"{date_str}_episode.mp4"
    public_target_vid = os.path.join(episodes_dir, file_name_vid)
    shutil.copy2(video_path, public_target_vid)
    filesize_vid = os.path.getsize(public_target_vid)
    
    # 2) Audio
    file_name_aud = f"{date_str}_episode.mp3"
    public_target_aud = os.path.join(episodes_dir, file_name_aud)
    shutil.copy2(audio_path, public_target_aud)
    filesize_aud = os.path.getsize(public_target_aud)
    
    base_url = get_repo_url()
    safe_file_name_vid = quote(file_name_vid)
    file_url_vid = f"{base_url}/episodes/{safe_file_name_vid}"
    
    safe_file_name_aud = quote(file_name_aud)
    file_url_aud = f"{base_url}/episodes/{safe_file_name_aud}"
    
    pub_date = email.utils.format_datetime(datetime.now().astimezone())
    
    if not os.path.exists(rss_path):
        logging.info("Initializing brand new Podcast RSS feed exactly at docs/feed.xml...")
        rss = ET.Element("rss", {"version": "2.0", "xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd", "xmlns:content": "http://purl.org/rss/1.0/modules/content/"})
        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text = "Eternal Record"
        ET.SubElement(channel, "description").text = "Automated Cinematic Mythology Pipeline."
        ET.SubElement(channel, "link").text = base_url
        ET.SubElement(channel, "language").text = "en-us"
        ET.SubElement(channel, "itunes:explicit").text = "no"
        itunes_image = ET.SubElement(channel, "itunes:image")
        itunes_image.set("href", f"{base_url}/cover.jpg") 
    else:
        logging.info("Loading existing Podcast RSS feed securely...")
        tree = ET.parse(rss_path)
        rss = tree.getroot()
        channel = rss.find("channel")

    item = ET.Element("item")
    ET.SubElement(item, "title").text = title_text
    ET.SubElement(item, "description").text = desc_text
    ET.SubElement(item, "pubDate").text = pub_date
    ET.SubElement(item, "guid", isPermaLink="false").text = file_url_vid
    
    enclosure_vid = ET.SubElement(item, "enclosure")
    enclosure_vid.set("url", file_url_vid)
    enclosure_vid.set("length", str(filesize_vid))
    enclosure_vid.set("type", "video/mp4")
    
    enclosure_aud = ET.SubElement(item, "enclosure")
    enclosure_aud.set("url", file_url_aud)
    enclosure_aud.set("length", str(filesize_aud))
    enclosure_aud.set("type", "audio/mpeg")
    
    insert_index = list(channel).index(channel.find("item")) if channel.find("item") is not None else len(channel)
    channel.insert(insert_index, item)
    
    xml_str = ET.tostring(rss, encoding='utf-8')
    parsed_xml = minidom.parseString(xml_str)
    pretty_xml = parsed_xml.toprettyxml(indent="  ")
    pretty_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])
    
    with open(rss_path, "w", encoding="utf-8") as f:
        f.write(pretty_xml)
        
    logging.info(f"SUCCESS: Exported {file_name_vid} and audio securely into RSS Feed struct.")
    logging.info(f"Spotify Ingestion Feed Location: {base_url}/feed.xml")
    
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    
    if not generate_or_update_rss(args.date):
        exit(1)

if __name__ == "__main__":
    main()
