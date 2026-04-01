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
    # Attempt to grab GITHUB_REPOSITORY automatically during Action run dynamically
    repo = os.getenv("GITHUB_REPOSITORY")
    if repo:
        username = repo.split('/')[0]
        reponame = repo.split('/')[1]
        return f"https://{username}.github.io/{reponame}"
    return "https://USERNAME.github.io/REPO_NAME" # Fallback local

def generate_or_update_rss(date_str):
    docs_dir = "docs"
    episodes_dir = os.path.join(docs_dir, "episodes")
    rss_path = os.path.join(docs_dir, "rss.xml")
    
    os.makedirs(episodes_dir, exist_ok=True)
    
    output_dir = os.path.join("output", date_str)
    video_path = os.path.join(output_dir, "final_video.mp4")
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
    
    # Securely copy Payload directly to public Docs directory naturally
    file_name = f"{date_str}_episode.mp4"
    public_target = os.path.join(episodes_dir, file_name)
    shutil.copy2(video_path, public_target)
    
    filesize = os.path.getsize(public_target)
    
    base_url = get_repo_url()
    safe_file_name = quote(file_name)
    file_url = f"{base_url}/episodes/{safe_file_name}"
    
    pub_date = email.utils.format_datetime(datetime.now().astimezone())
    
    # 1. Setup base RSS architecture if it completely doesn't exist natively
    if not os.path.exists(rss_path):
        logging.info("Initializing brand new Podcast RSS feed exactly at docs/rss.xml...")
        rss = ET.Element("rss", {"version": "2.0", "xmlns:itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd", "xmlns:content": "http://purl.org/rss/1.0/modules/content/"})
        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text = "Eternal Record"
        ET.SubElement(channel, "description").text = "Automated Cinematic Mythology Pipeline."
        ET.SubElement(channel, "link").text = base_url
        ET.SubElement(channel, "language").text = "en-us"
        ET.SubElement(channel, "itunes:explicit").text = "no"
        itunes_image = ET.SubElement(channel, "itunes:image")
        itunes_image.set("href", f"{base_url}/cover.jpg") # Optional cover art
    else:
        logging.info("Loading existing Podcast RSS feed securely...")
        tree = ET.parse(rss_path)
        rss = tree.getroot()
        channel = rss.find("channel")

    # 2. Construct the identical XML Item for Spotify
    item = ET.Element("item")
    ET.SubElement(item, "title").text = title_text
    ET.SubElement(item, "description").text = desc_text
    ET.SubElement(item, "pubDate").text = pub_date
    ET.SubElement(item, "guid", isPermaLink="false").text = file_url
    
    enclosure = ET.SubElement(item, "enclosure")
    enclosure.set("url", file_url)
    enclosure.set("length", str(filesize))
    enclosure.set("type", "video/mp4")
    
    # Prepend precisely to exactly remain the newest episode organically
    insert_index = list(channel).index(channel.find("item")) if channel.find("item") is not None else len(channel)
    channel.insert(insert_index, item)
    
    # 3. Prettify the XML natively safely
    xml_str = ET.tostring(rss, encoding='utf-8')
    parsed_xml = minidom.parseString(xml_str)
    pretty_xml = parsed_xml.toprettyxml(indent="  ")
    pretty_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])
    
    with open(rss_path, "w", encoding="utf-8") as f:
        f.write(pretty_xml)
        
    logging.info(f"SUCCESS: Exported {file_name} securely into RSS Feed struct.")
    logging.info(f"Spotify Ingestion Feed Location: {base_url}/rss.xml")
    
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    
    if not generate_or_update_rss(args.date):
        exit(1)

if __name__ == "__main__":
    main()
