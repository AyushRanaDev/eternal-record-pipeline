import os
import argparse
import logging
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv

try:
    import edge_tts
except ImportError:
    edge_tts = None

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
load_dotenv()

def format_time_srt(offset_100ns):
    # offset is in 100-nanosecond units. 10_000_000 = 1 second
    seconds = offset_100ns / 10_000_000
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

async def async_generate_tts(text, output_path, srt_path):
    # Fix 1 — Switch voice
    communicate = edge_tts.Communicate(text, "en-US-GuyNeural")
    
    with open(output_path, "wb") as audio_file, open(srt_path, "w", encoding="utf-8") as srt_file:
        index = 1
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                offset = chunk["offset"]
                duration = chunk["duration"]
                text_word = chunk["text"]
                
                start_time_str = format_time_srt(offset)
                end_time_str = format_time_srt(offset + duration)
                
                srt_file.write(f"{index}\n")
                srt_file.write(f"{start_time_str} --> {end_time_str}\n")
                srt_file.write(f"{text_word}\n\n")
                index += 1

def get_most_recent_folder():
    """Fallback to find the most recent folder in output/."""
    output_base = "output"
    if not os.path.exists(output_base):
        return None
    
    try:
        folders = [f for f in os.listdir(output_base) if os.path.isdir(os.path.join(output_base, f))]
    except Exception as e:
        logging.error(f"Error reading {output_base}: {e}")
        return None
        
    # Filter folders that match YYYY-MM-DD
    valid_folders = []
    for f in folders:
        try:
            datetime.strptime(f, "%Y-%m-%d")
            valid_folders.append(f)
        except ValueError:
            pass
            
    if not valid_folders:
        return None
        
    valid_folders.sort(reverse=True)
    return valid_folders[0]

def generate_audio(date_str, force=False):
    output_dir = os.path.join("output", date_str)
    script_path = os.path.join(output_dir, "script_english.txt")
    
    if not os.path.exists(script_path):
        logging.warning(f"Script not found at {script_path}. Looking for the most recent folder...")
        recent_date = get_most_recent_folder()
        if not recent_date:
            logging.error("No valid recent folders found in output/.")
            return False
            
        logging.info(f"Fallback to most recent folder: {recent_date}")
        output_dir = os.path.join("output", recent_date)
        script_path = os.path.join(output_dir, "script_english.txt")
        
        if not os.path.exists(script_path):
            logging.error(f"Fallback failed. Script not found in {output_dir}.")
            return False
            
    final_audio_path = os.path.join(output_dir, "audio.mp3")
    srt_path = os.path.join(output_dir, "subtitles.srt")

    if os.path.exists(final_audio_path) and os.path.exists(srt_path) and not force:
        logging.info(f"Audio and SRT already generated in {output_dir}.")
        return True

    with open(script_path, "r", encoding="utf-8") as f:
        script_text = f.read().strip()

    if not edge_tts:
        logging.error("edge-tts is not installed. Please pip install edge-tts.")
        return False
        
    logging.info("Generating audio using edge-tts (en-US-GuyNeural)...")
    
    # Fix 2 & Fix 4 - Retry logic and fallback
    for attempt in range(3):
        try:
            asyncio.run(async_generate_tts(script_text, final_audio_path, srt_path))
            logging.info(f"SUCCESS: Audio and SRT generated and saved to {output_dir}")
            return True
        except Exception as e:
            if attempt < 2:
                logging.warning(f"edge-tts attempt {attempt+1} failed, retrying in 10s...")
                time.sleep(10)
            else:
                logging.warning(f"edge-tts failed after 3 attempts. Attempting gTTS fallback...")
                try:
                    from gtts import gTTS
                    tts = gTTS(text=script_text, lang='en', slow=False)
                    tts.save(final_audio_path)
                    
                    # Create dummy SRT to satisfy downstream pipeline dependencies
                    with open(srt_path, "w", encoding="utf-8") as srt_file:
                        srt_file.write("1\n00:00:00,000 --> 00:00:10,000\n[gTTS Fallback Active]\n\n")
                        
                    logging.info("Used gTTS fallback successfully")
                    return True
                except Exception as fallback_e:
                    logging.error(f"gTTS fallback failed: {fallback_e}")
                    raise e
                    
    return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not generate_audio(args.date, args.force):
        exit(1)

if __name__ == "__main__":
    main()
