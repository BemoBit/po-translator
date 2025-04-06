#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PO File Translator
This script automatically detects the source language of PO files and translates them to the specified target language.
It can handle large files by processing entries in batches and saves progress periodically.
"""

import os
import sys
import argparse
import time
import json
import urllib.request
import urllib.parse
import urllib.error
import http.client
import signal
import datetime
import shutil
import re

# Try to import optional dependencies
try:
    import polib
except ImportError:
    print("Warning: polib module not found. Installing it...")
    print("Run: pip install polib")
    sys.exit(1)

try:
    from tqdm import tqdm
    use_tqdm = True
except ImportError:
    use_tqdm = False
    print("Warning: tqdm module not found. Progress bar will be disabled.")
    print("For progress bar, install tqdm: pip install tqdm")

# Translation service options
TRANSLATION_SERVICE = "google"  # Options: "google", "libretranslate", "mymemory"

# Default target language
DEFAULT_TARGET_LANG = "fa"  # Persian/Farsi

# Language code mapping
LANGUAGE_CODES = {
    # Common language codes
    "en": "English",
    "fa": "Persian/Farsi",
    "ar": "Arabic",
    "zh": "Chinese",
    "fr": "French",
    "de": "German",
    "hi": "Hindi",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "ru": "Russian",
    "es": "Spanish",
    "tr": "Turkish",
    # Add more languages as needed
}

# Global variables for handling interruptions
interrupted = False
last_saved_file = None
backup_file = None
save_interval = 50  # Save after every 50 translations

def signal_handler(sig, frame):
    """Handle interrupt signals to save progress before exiting."""
    global interrupted
    print("\nInterrupt received. Saving progress before exiting...")
    interrupted = True
    # The actual save will happen in the main loop

def detect_language_from_po(po_file):
    """
    Detect the source language from the PO file.
    
    Args:
        po_file: polib.POFile object
    
    Returns:
        str: Detected language code or 'auto' if detection fails
    """
    # Try to get language from PO file metadata
    if hasattr(po_file, 'metadata') and po_file.metadata:
        # Check Language field
        if 'Language' in po_file.metadata:
            lang_code = po_file.metadata['Language'].split('_')[0].lower()
            if lang_code in LANGUAGE_CODES:
                return lang_code
        
        # Check Language-Team field
        if 'Language-Team' in po_file.metadata:
            lang_team = po_file.metadata['Language-Team'].lower()
            for code in LANGUAGE_CODES:
                if LANGUAGE_CODES[code].lower() in lang_team:
                    return code
    
    # If we can't detect from metadata, try to detect from content
    # This is a simple heuristic - for better results, use a language detection library
    if len(po_file) > 0:
        # Get some sample text from the PO file
        sample_texts = []
        for entry in po_file[:min(10, len(po_file))]:
            if entry.msgid and len(entry.msgid) > 10:
                sample_texts.append(entry.msgid)
        
        if sample_texts:
            # Try to detect language using Google Translate
            try:
                from googletrans import Translator
                translator = Translator()
                detection = translator.detect(sample_texts[0])
                if detection and detection.lang:
                    return detection.lang
            except:
                # If googletrans fails, fallback to simple heuristics
                text = " ".join(sample_texts)
                
                # Check for common language patterns
                if re.search(r'[а-яА-Я]', text):  # Cyrillic characters
                    return 'ru'  # Russian
                elif re.search(r'[ا-ي]', text):  # Arabic characters
                    return 'ar'  # Arabic
                elif re.search(r'[一-龯]', text):  # Chinese characters
                    return 'zh'  # Chinese
                elif re.search(r'[あ-んア-ン]', text):  # Japanese characters
                    return 'ja'  # Japanese
                elif re.search(r'[가-힣]', text):  # Korean characters
                    return 'ko'  # Korean
                else:
                    # Default to English for Latin script
                    return 'en'
    
    # If all detection methods fail, return 'auto'
    return 'auto'

def get_language_name(lang_code):
    """Get the language name from its code."""
    return LANGUAGE_CODES.get(lang_code, lang_code)

def translate_with_google(text, source_lang="auto", target_lang="fa"):
    """Translate text using Google Translate API (no API key required)."""
    try:
        # Try to import googletrans if available
        from googletrans import Translator
        translator = Translator()
        result = translator.translate(text, dest=target_lang, src=source_lang)
        return result.text
    except ImportError:
        # Fallback to a simple HTTP request to Google Translate
        try:
            user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_lang}&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
            request = urllib.request.Request(url, headers={'User-Agent': user_agent})
            response = urllib.request.urlopen(request)
            data = json.loads(response.read().decode('utf-8'))
            translated_text = ''.join([sentence[0] for sentence in data[0]])
            return translated_text
        except Exception as e:
            print(f"Google Translate API error: {e}")
            return text

def translate_with_libretranslate(text, source_lang="auto", target_lang="fa", api_url="https://libretranslate.com/translate"):
    """Translate text using LibreTranslate API."""
    try:
        data = {
            "q": text,
            "source": source_lang if source_lang != "auto" else "auto",
            "target": target_lang,
            "format": "text"
        }
        headers = {"Content-Type": "application/json"}
        encoded_data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(api_url, data=encoded_data, headers=headers, method="POST")
        response = urllib.request.urlopen(req)
        response_data = json.loads(response.read().decode('utf-8'))
        return response_data.get("translatedText", text)
    except Exception as e:
        print(f"LibreTranslate API error: {e}")
        return text

def translate_with_mymemory(text, source_lang="en", target_lang="fa", email=None):
    """Translate text using MyMemory API (free, up to 5000 words/day)."""
    try:
        # MyMemory doesn't support 'auto' as source language
        if source_lang == "auto":
            source_lang = "en"
            
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text)}&langpair={source_lang}|{target_lang}"
        if email:
            url += f"&de={email}"
        
        request = urllib.request.Request(url)
        response = urllib.request.urlopen(request)
        data = json.loads(response.read().decode('utf-8'))
        
        if data["responseStatus"] == 200:
            return data["responseData"]["translatedText"]
        else:
            print(f"MyMemory API error: {data.get('responseDetails', 'Unknown error')}")
            return text
    except Exception as e:
        print(f"MyMemory API error: {e}")
        return text

def translate_text(text, source_lang="auto", target_lang="fa", service=TRANSLATION_SERVICE):
    """Translate text using the specified translation service."""
    if not text or text.isspace():
        return text
    
    # Add a small delay to avoid hitting API rate limits
    time.sleep(0.5)
    
    if service == "google":
        return translate_with_google(text, source_lang, target_lang)
    elif service == "libretranslate":
        return translate_with_libretranslate(text, source_lang, target_lang)
    elif service == "mymemory":
        return translate_with_mymemory(text, source_lang, target_lang)
    else:
        print(f"Unknown translation service: {service}")
        return text

def create_backup_filename(output_file):
    """Create a backup filename with timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name, ext = os.path.splitext(output_file)
    return f"{base_name}_backup_{timestamp}{ext}"

def save_progress(po, output_file, is_final=False):
    """Save current progress to a file."""
    global last_saved_file, backup_file
    
    # Create a backup file for the first save or if this is the final save
    if last_saved_file is None or is_final:
        backup_file = create_backup_filename(output_file)
        print(f"Creating backup file: {backup_file}")
    
    # Save to the backup file first
    try:
        po.save(backup_file)
        last_saved_file = backup_file
        
        # If this is the final save or we're interrupted, save to the actual output file
        if is_final:
            shutil.copy2(backup_file, output_file)
            print(f"Final translation saved to: {output_file}")
            
            # Keep the latest backup file
            if not interrupted:
                backup_files = [f for f in os.listdir(os.path.dirname(output_file)) 
                               if f.startswith(os.path.basename(os.path.splitext(output_file)[0]) + "_backup_")]
                # Sort by timestamp (newest first)
                backup_files.sort(reverse=True)
                
                # Keep only the latest backup file
                for old_backup in backup_files[1:]:
                    try:
                        os.remove(os.path.join(os.path.dirname(output_file), old_backup))
                    except:
                        pass
    except Exception as e:
        print(f"Error saving progress: {e}")
        # If we can't save to the backup, try to save directly to the output file
        try:
            po.save(output_file)
            print(f"Saved directly to: {output_file}")
        except Exception as e2:
            print(f"Failed to save progress: {e2}")

def translate_po_file(input_file, output_file, batch_size=10, service=TRANSLATION_SERVICE, 
                     ignore_translated=False, save_interval=50, target_lang=DEFAULT_TARGET_LANG,
                     source_lang=None):
    """
    Translate a PO file to the target language.
    
    Args:
        input_file: Path to the input PO file
        output_file: Path to save the translated PO file
        batch_size: Number of entries to translate in each batch
        service: Translation service to use
        ignore_translated: If True, already translated entries will be kept as is
        save_interval: Save progress after this many translations
        target_lang: Target language code
        source_lang: Source language code (if None, will be auto-detected)
    """
    global interrupted, backup_file
    
    try:
        # Set up signal handlers for graceful interruption
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Load the PO file
        po = polib.pofile(input_file)
        total_entries = len(po)
        
        print(f"Loaded {total_entries} entries from {input_file}")
        
        # Detect source language if not provided
        if source_lang is None:
            source_lang = detect_language_from_po(po)
        
        print(f"Source language detected: {source_lang} ({get_language_name(source_lang)})")
        print(f"Target language: {target_lang} ({get_language_name(target_lang)})")
        print(f"Using translation service: {service}")
        
        if ignore_translated:
            print("Ignoring already translated entries (keeping existing translations)")
        
        # Count entries that need translation
        entries_to_translate = 0
        for entry in po:
            if entry.msgid and not entry.obsolete:
                if not entry.msgstr and not ignore_translated:
                    entries_to_translate += 1
                elif not entry.msgstr and ignore_translated:
                    entries_to_translate += 1
                
                # Count plural forms that need translation
                if entry.msgid_plural and entry.msgstr_plural:
                    for plural_index in entry.msgstr_plural:
                        if not entry.msgstr_plural[plural_index] and not ignore_translated:
                            entries_to_translate += 1
                        elif not entry.msgstr_plural[plural_index] and ignore_translated:
                            entries_to_translate += 1
        
        if entries_to_translate == 0:
            print("No entries need translation. Saving file as is.")
            po.save(output_file)
            return
        
        print(f"Found {entries_to_translate} entries that need translation")
        print(f"Progress will be saved every {save_interval} translations")
        
        # Update the metadata to reflect the new language
        if 'Language' in po.metadata:
            po.metadata['Language'] = target_lang
        
        # Process entries in batches with progress bar if tqdm is available
        if use_tqdm:
            iterator = tqdm(range(0, total_entries, batch_size), desc="Translating")
        else:
            iterator = range(0, total_entries, batch_size)
            print("Starting translation...")
        
        translated_count = 0
        for i in iterator:
            batch = po[i:i+batch_size]
            
            for entry in batch:
                if interrupted:
                    print("Interrupted! Saving progress...")
                    save_progress(po, output_file, is_final=True)
                    print(f"Translated {translated_count}/{entries_to_translate} entries before interruption.")
                    print(f"You can resume by running the script again with the -i flag to keep existing translations.")
                    return
                
                if entry.msgid and not entry.obsolete:
                    # Translate msgstr if it's empty or if we're not ignoring already translated entries
                    if not entry.msgstr:
                        entry.msgstr = translate_text(entry.msgid, source_lang, target_lang, service)
                        translated_count += 1
                    elif not ignore_translated:
                        entry.msgstr = translate_text(entry.msgid, source_lang, target_lang, service)
                        translated_count += 1
                    
                    # Handle plural forms if they exist
                    if entry.msgid_plural and entry.msgstr_plural:
                        for plural_index in entry.msgstr_plural:
                            if not entry.msgstr_plural[plural_index]:
                                plural_text = entry.msgid_plural if plural_index != '0' else entry.msgid
                                entry.msgstr_plural[plural_index] = translate_text(plural_text, source_lang, target_lang, service)
                                translated_count += 1
                            elif not ignore_translated:
                                plural_text = entry.msgid_plural if plural_index != '0' else entry.msgid
                                entry.msgstr_plural[plural_index] = translate_text(plural_text, source_lang, target_lang, service)
                                translated_count += 1
            
            # Print progress if tqdm is not available
            if not use_tqdm and (i + batch_size) % (batch_size * 10) == 0:
                progress = min(100, int((i + batch_size) / total_entries * 100))
                print(f"Progress: {progress}% ({i + batch_size}/{total_entries})")
            
            # Save progress periodically
            if translated_count > 0 and translated_count % save_interval == 0:
                print(f"Saving progress after {translated_count} translations...")
                save_progress(po, output_file)
        
        # Save the final translated PO file
        save_progress(po, output_file, is_final=True)
        print(f"Translation completed. Translated {translated_count} entries. Saved to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        
        # Try to save progress if we have a PO file loaded
        if 'po' in locals():
            print("Attempting to save progress after error...")
            try:
                save_progress(po, output_file, is_final=True)
                print(f"Progress saved after error. You can resume with the -i flag.")
            except:
                print("Failed to save progress after error.")
        
        sys.exit(1)

def list_available_languages():
    """Print a list of available languages."""
    print("\nAvailable languages:")
    print("--------------------")
    for code, name in sorted(LANGUAGE_CODES.items()):
        print(f"{code}: {name}")
    print("\nUse the language code (e.g., 'fa' for Persian) when specifying the target language.")

def main():
    parser = argparse.ArgumentParser(description="Translate PO files to any language")
    parser.add_argument("input_file", help="Path to the input PO file")
    parser.add_argument("-o", "--output", help="Path to the output PO file (default: input_file.[target_lang].po)")
    parser.add_argument("-b", "--batch-size", type=int, default=10, 
                        help="Number of entries to translate in each batch (default: 10)")
    parser.add_argument("-s", "--service", choices=["google", "libretranslate", "mymemory"], 
                        default=TRANSLATION_SERVICE, help="Translation service to use")
    parser.add_argument("--source", help="Source language code (if not specified, will be auto-detected)")
    parser.add_argument("-t", "--target", default=DEFAULT_TARGET_LANG,
                        help=f"Target language code (default: {DEFAULT_TARGET_LANG} - {get_language_name(DEFAULT_TARGET_LANG)})")
    parser.add_argument("--libretranslate-url", default="https://libretranslate.com/translate",
                        help="URL for LibreTranslate API (if using libretranslate service)")
    parser.add_argument("--email", help="Email for MyMemory API (increases daily limit)")
    parser.add_argument("-i", "--ignore-translated", action="store_true",
                        help="Ignore already translated entries (keep existing translations)")
    parser.add_argument("--save-interval", type=int, default=50,
                        help="Save progress after this many translations (default: 50)")
    parser.add_argument("--list-languages", action="store_true",
                        help="List available languages and exit")
    
    args = parser.parse_args()
    
    # List languages if requested
    if args.list_languages:
        list_available_languages()
        sys.exit(0)
    
    # Check if input file exists
    if not os.path.isfile(args.input_file):
        print(f"Error: Input file '{args.input_file}' does not exist.")
        sys.exit(1)
    
    # Set default output file if not specified
    output_file = args.output
    if not output_file:
        base_name, ext = os.path.splitext(args.input_file)
        output_file = f"{base_name}.{args.target}{ext}"
    
    translate_po_file(
        args.input_file, 
        output_file, 
        args.batch_size, 
        args.service, 
        args.ignore_translated, 
        args.save_interval,
        args.target,
        args.source
    )

if __name__ == "__main__":
    main()
