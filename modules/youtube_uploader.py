import os
import json
import logging
import argparse
from datetime import datetime
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
load_dotenv()

def get_youtube_service():
    # Read the token payload dynamically from the system environment natively
    token_json = os.getenv("YOUTUBE_AUTH_TOKEN")
    
    if not token_json:
        # Fallback reading strictly for initial local testing before GitHub Secret implementation
        if os.path.exists("token.json"):
            with open("token.json", "r") as f:
                token_json = f.read()
        else:
            logging.error("No YOUTUBE_AUTH_TOKEN found in environment natively or token.json file.")
            return None
            
    try:
        token_dict = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(token_dict)
        youtube = build('youtube', 'v3', credentials=creds)
        return youtube
    except Exception as e:
        logging.error(f"Failed to build YouTube service securely: {e}")
        return None

def upload_to_youtube(date_str):
    youtube = get_youtube_service()
    if not youtube:
        return False
        
    output_dir = os.path.join("output", date_str)
    video_path = os.path.join(output_dir, "final_video.mp4")
    metadata_path = os.path.join(output_dir, "metadata.json")
    script_path = os.path.join(output_dir, "script_english.txt")
    
    if not os.path.exists(video_path):
        logging.error(f"Target Delivery Video explicitly not found: {video_path}")
        return False
        
    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    with open(script_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.read().split('\n') if line.strip()]
        
    title = meta.get("title", "A Legend Beyond Time")
    sin_tag = meta.get("sin_tag", "Pride")
    
    # 1. Title format natively explicitly matched
    fmt_title = f"{title} — {sin_tag} | #Shorts #Mythology #Wisdom"
    
    # 2. Description natively pulling top 3 sentences 
    desc_lines = lines[:3]
    description = "\n".join(desc_lines) + "\n\n#Shorts #Mythology #Wisdom #History #Education"

    logging.info(f"Target YouTube Assembly:")
    logging.info(f"Title: {fmt_title}")
    
    body = {
        'snippet': {
            'title': fmt_title,
            'description': description,
            'categoryId': '27', # 27 = Education identically
            'tags': ['mythology', 'wisdom', 'legend', 'shorts', 'history']
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
    }
    
    # 3. Secure direct uploading payload
    logging.info(f"Executing massive MP4 stream delivery natively to YouTube API... hold tightly.")
    try:
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        
        response = request.execute()
        video_id = response.get('id')
        logging.info(f"SUCCESS: Eternal Record Uploaded flawlessly natively!")
        logging.info(f"Access Output Payload: https://youtu.be/{video_id}")
        return True
    except Exception as e:
        logging.error(f"Google APIs failed aggressively: {e}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    
    if not upload_to_youtube(args.date):
        exit(1)

if __name__ == "__main__":
    main()
