import os
import json
import logging
import argparse
import requests
from datetime import datetime
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
load_dotenv()

def get_podbean_token(client_id, client_secret):
    url = "https://api.podbean.com/v1/oauth/token"
    auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
    data = {"grant_type": "client_credentials"}
    
    try:
        res = requests.post(url, auth=auth, data=data)
        res.raise_for_status()
        return res.json().get('access_token')
    except Exception as e:
        logging.error(f"Failed to authenticate with Podbean OAuth natively: {e}")
        return None

def authorize_upload(token, filename, filesize, content_type="audio/mpeg"):
    url = "https://api.podbean.com/v1/files/uploadAuthorize"
    params = {"access_token": token, "filename": filename, "filesize": filesize, "content_type": content_type}
    
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        # Natively returns dict with presigned_url and file_key
        return res.json()
    except Exception as e:
        logging.error(f"Failed to authorize generic AWS upload slot: {e}")
        return None

def upload_to_podbean(date_str):
    client_id = os.getenv("PODBEAN_CLIENT_ID")
    client_secret = os.getenv("PODBEAN_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        logging.error("PODBEAN_CLIENT_ID or PODBEAN_CLIENT_SECRET completely missing from environment.")
        return False
        
    token = get_podbean_token(client_id, client_secret)
    if not token: 
        return False
    
    output_dir = os.path.join("output", date_str)
    audio_path = os.path.join(output_dir, "final_video.mp4")
    metadata_dir = os.path.join("output", date_str)
    metadata_path = os.path.join(metadata_dir, "metadata.json")
    script_path = os.path.join(metadata_dir, "script_english.txt")
    
    if not os.path.exists(audio_path):
        logging.error(f"Target Delivery Video strictly abandoned: {audio_path}")
        return False

    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    with open(script_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.read().split('\n') if line.strip()]

    title = meta.get("title", 'A Legend Beyond Time')
    desc_lines = lines[:3]
    description = "\n".join(desc_lines)
    
    filesize = os.path.getsize(audio_path)
    filename = os.path.basename(audio_path)
    
    # 1. Authorize file payload securely
    logging.info("Requesting remote Podbean Direct Video Storage Allocation natively...")
    auth_data = authorize_upload(token, filename, filesize, content_type="video/mp4")
    if not auth_data: 
        return False
    
    presigned_url = auth_data.get("presigned_url")
    file_key = auth_data.get("file_key")
    
    # 2. Seamlessly Upload file stream
    logging.info(f"Injecting natively chunked Video File ({filesize} bytes)...")
    try:
        with open(audio_path, "rb") as f:
            upload_res = requests.put(presigned_url, data=f, headers={"Content-Type": "video/mp4"})
            upload_res.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to cleanly proxy upload to Podbean securely: {e}")
        return False
        
    # 3. Publish Episode out securely into RSS ecosystem
    logging.info("Broadcasting Episode organically directly to Spotify Feed structure...")
    publish_url = "https://api.podbean.com/v1/episodes"
    publish_data = {
        "access_token": token,
        "title": title,
        "content": description,
        "status": "publish",
        "type": "public",
        "media_key": file_key
    }
    
    try:
        pub_res = requests.post(publish_url, data=publish_data)
        pub_res.raise_for_status()
        episode = pub_res.json()
        logging.info(f"SUCCESS: Episode published safely perfectly!")
        logging.info(f"Podcast Live Player Link: {episode.get('player_url')}")
        return True
    except Exception as e:
        logging.error(f"Episode final API structural submission heavily halted: {e}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    
    if not upload_to_podbean(args.date):
        exit(1)

if __name__ == "__main__":
    main()
