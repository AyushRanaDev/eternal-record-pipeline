import os
import json
import logging
import argparse
import time
from datetime import datetime
from dotenv import load_dotenv

# Try importing the clients
try:
    from groq import Groq
except ImportError:
    Groq = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

load_dotenv()

PROMPT = """You are an elite cinematic scriptwriter. Your task is to generate a vertical video script about a historical or mythological story.

STRICT CONSTRAINTS:
1. Length: The English text MUST be strictly between 250 and 300 words. This provides richer storytelling.
2. Source: Pick a highly engaging story from ONLY ONE of these: Greek/Roman mythology, Bible, Bhagavad Gita, Mahabharata, Ramayana, Rigveda, Yajurveda, Atharvaveda, Samaveda, Garuda Purana, Upanishads, or great leaders.
3. Theme: It must explicitly deal with the conquest or consequence of one of the 7 Deadly Sins (Pride, Greed, Lust, Envy, Gluttony, Wrath, Sloth).
4. Cinematic Opening Hook (MANDATORY): You MUST start the script verbatim with ONE of these exact phrases (choose one):
   - "Today's story will change how you see everything..."
   - "You think you know this story. You don't."
   - "Today we go back to a time when..."
   - "This myth has survived thousands of years. Here's why."
   - "Today's legend is about the one sin that destroyed an empire."
5. Story Structure: You MUST follow this exact structure:
   - HOOK (15-20 words) — stops the scroll (using one of the phrases above).
   - SETUP (40-50 words) — who, where, when, stakes.
   - CONFLICT (80-100 words) — the struggle, the sin taking hold, cinematic present tense.
   - THE TURN (40-50 words) — the moment everything changes.
   - THE SIN NAMED (20-25 words) — explicitly name the sin and its consequence.
   - REFLECTION (20-25 words) — one line that hits hard for modern life.
6. Anti-Hallucination: Never invent stories, do not mix traditions.

OUTPUT FORMAT:
Return ONLY a valid, parseable JSON object. No markdown wrapping, no extra text.
{
  "title": "A captivating title",
  "tradition": "Source tradition (e.g. Mahabharata)",
  "sin_tag": "The specific sin (e.g. Sloth)",
  "script_english": "The full English script, matching the 250-300 word limit exactly."
}
"""

def generate_script_groq(api_key):
    if not Groq:
        raise ImportError("groq is not installed.")
    logging.info("Calling Groq API (llama-3.3-70b-versatile)...")
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": PROMPT}],
        model="llama-3.3-70b-versatile",
        temperature=0.7,
        response_format={"type": "json_object"}
    )
    return response.choices[0].message.content

def generate_script_gemini(api_key):
    if not genai:
        raise ImportError("google-generativeai is not installed.")
    logging.info("Calling Gemini API (gemini-1.5-pro) as fallback...")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-pro")
    response = model.generate_content(
        PROMPT,
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.7,
        )
    )
    return response.text

def parse_and_validate(raw_json):
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse LLM Output as JSON: {e}")
        return None

    required_keys = ["title", "tradition", "sin_tag", "script_english"]
    if not all(k in data for k in required_keys):
        logging.error("JSON is missing one or more required keys.")
        return None
        
    word_count = len(data["script_english"].split())
    logging.info(f"Generated script word count: {word_count}")
    
    if word_count < 80:
        logging.warning(f"Script rejected: Word count ({word_count}) is critically below 80 words.")
        return None

    return data

def main():
    parser = argparse.ArgumentParser(description="Generate daily Eternal Record script.")
    parser.add_argument("--date", type=str, help="Specific date folder (YYYY-MM-DD)", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--force", action="store_true", help="Overwrite existing script for today.")
    args = parser.parse_args()

    output_dir = os.path.join("output", args.date)
    metadata_path = os.path.join(output_dir, "metadata.json")

    # If force is not passed, simply check if script_english.txt already exists
    if os.path.exists(os.path.join(output_dir, "script_english.txt")) and not args.force:
        logging.info(f"Script already generated for {args.date} in {output_dir}. Skipping. Use --force to overwrite. ")
        return

    groq_api_key = os.getenv("GROQ_API_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    
    data = None
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        logging.info(f"--- Generation Attempt {attempt}/{max_retries} ---")
        raw_json = None
        
        if groq_api_key:
            try:
                raw_json = generate_script_groq(groq_api_key)
            except Exception as e:
                logging.error(f"Groq generation failed: {e}")
        
        if not raw_json and gemini_api_key:
            try:
                raw_json = generate_script_gemini(gemini_api_key)
            except Exception as e:
                logging.error(f"Gemini generation failed: {e}")
                
        if not raw_json:
            logging.error("Both LLM requests failed or no API keys configured.")
            break
            
        data = parse_and_validate(raw_json)
        if data:
            break
            
        logging.info("Retrying...")
        time.sleep(2)

    if not data:
        logging.error("Failed to generate a valid script after all retries.")
        exit(1)

    # Save outputs
    os.makedirs(output_dir, exist_ok=True)
    
    with open(os.path.join(output_dir, "script_english.txt"), "w", encoding="utf-8") as f:
        f.write(data["script_english"].strip())
        
    metadata = {
        "title": data["title"],
        "tradition": data["tradition"],
        "sin_tag": data["sin_tag"],
        "date": args.date,
        "word_count": len(data["script_english"].split())
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
        
    logging.info(f"SUCCESS: Script components saved to {output_dir}/")

if __name__ == "__main__":
    main()
