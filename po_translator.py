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
import threading
import queue
import hashlib
import concurrent.futures
from functools import lru_cache

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
worker_threads = []  # Keep track of worker threads

# Translation cache to avoid redundant API calls
translation_cache = {}
translation_cache_file = None
cache_lock = threading.Lock()

# Maximum number of worker threads/processes
MAX_WORKERS = 5

def signal_handler(sig, frame):
    """Handle interrupt signals to save progress before exiting."""
    global interrupted
    print("\nInterrupt received. Saving progress before exiting...")
    interrupted = True
    
    # Terminate any running worker threads
    for thread in worker_threads:
        if thread.is_alive():
            # We can't forcibly terminate threads in Python, but we can set a flag
            # The threads should check the interrupted flag regularly
            pass  # The threads will check the global interrupted flag
    
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
            # Simple language detection based on character sets
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

def load_translation_cache(input_file, target_lang):
    """Load the translation cache from file if it exists."""
    global translation_cache, translation_cache_file
    
    # Create a cache filename based on the input file and target language
    base_name = os.path.basename(input_file)
    cache_dir = os.path.join(os.path.dirname(input_file), '.cache')
    os.makedirs(cache_dir, exist_ok=True)
    
    cache_filename = f"{base_name}_{target_lang}_cache.json"
    translation_cache_file = os.path.join(cache_dir, cache_filename)
    
    if os.path.exists(translation_cache_file):
        try:
            with open(translation_cache_file, 'r', encoding='utf-8') as f:
                translation_cache = json.load(f)
            print(f"Loaded {len(translation_cache)} cached translations")
        except Exception as e:
            print(f"Error loading translation cache: {e}")
            translation_cache = {}
    else:
        translation_cache = {}

def save_translation_cache():
    """Save the translation cache to file."""
    global translation_cache, translation_cache_file
    
    if translation_cache_file and translation_cache:
        try:
            with cache_lock:
                with open(translation_cache_file, 'w', encoding='utf-8') as f:
                    json.dump(translation_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving translation cache: {e}")

def get_cache_key(text, source_lang, target_lang):
    """Generate a unique cache key for a translation request."""
    # Use a hash of the text to avoid issues with special characters in filenames
    text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
    return f"{source_lang}_{target_lang}_{text_hash}"

def get_cached_translation(text, source_lang, target_lang):
    """Get a translation from the cache if it exists."""
    if not text or text.isspace():
        return text
    
    cache_key = get_cache_key(text, source_lang, target_lang)
    with cache_lock:
        return translation_cache.get(cache_key)

def cache_translation(text, translated_text, source_lang, target_lang):
    """Cache a translation for future use."""
    if not text or text.isspace() or not translated_text:
        return
    
    cache_key = get_cache_key(text, source_lang, target_lang)
    with cache_lock:
        translation_cache[cache_key] = translated_text
    
    # Periodically save the cache to disk
    if len(translation_cache) % 100 == 0:
        save_translation_cache()

@lru_cache(maxsize=1000)
def translate_with_google(text, source_lang="auto", target_lang="fa"):
    """Translate text using Google Translate API (no API key required)."""
    if not text or text.isspace():
        return text
        
    # Add a small delay to avoid hitting API rate limits
    time.sleep(0.2)
    
    # Use direct HTTP request to Google Translate API
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
        # If the direct API call fails, try an alternative approach
        try:
            # Alternative API endpoint
            url = f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl={source_lang}&tl={target_lang}&q={urllib.parse.quote(text)}"
            request = urllib.request.Request(url, headers={'User-Agent': user_agent})
            response = urllib.request.urlopen(request)
            data = json.loads(response.read().decode('utf-8'))
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            return text
        except Exception as e2:
            print(f"Alternative Google Translate API error: {e2}")
            return text

@lru_cache(maxsize=1000)
def translate_with_libretranslate(text, source_lang="auto", target_lang="fa", api_url="https://libretranslate.com/translate"):
    """Translate text using LibreTranslate API."""
    if not text or text.isspace():
        return text
        
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

@lru_cache(maxsize=1000)
def translate_with_mymemory(text, source_lang="en", target_lang="fa", email=None):
    """Translate text using MyMemory API (free, up to 5000 words/day)."""
    if not text or text.isspace():
        return text
        
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
    """Translate text using the specified translation service with caching."""
    if not text or text.isspace():
        return text
    
    # Check if we have this translation in cache
    cached = get_cached_translation(text, source_lang, target_lang)
    if cached:
        return cached
    
    # Add a small delay to avoid hitting API rate limits
    time.sleep(0.2)  # Reduced from 0.5 to 0.2 seconds
    
    # Translate using the selected service
    if service == "google":
        result = translate_with_google(text, source_lang, target_lang)
    elif service == "libretranslate":
        result = translate_with_libretranslate(text, source_lang, target_lang)
    elif service == "mymemory":
        result = translate_with_mymemory(text, source_lang, target_lang)
    else:
        print(f"Unknown translation service: {service}")
        result = text
    
    # Cache the result
    cache_translation(text, result, source_lang, target_lang)
    
    return result

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

def worker_translate(work_queue, result_queue, source_lang, target_lang, service):
    """Worker function for parallel translation."""
    global interrupted
    while not interrupted:
        try:
            # Get a task from the queue with a timeout
            try:
                task = work_queue.get(block=True, timeout=0.5)
            except queue.Empty:
                # No more tasks or timeout
                continue
                
            if task is None:  # Sentinel value to indicate end of queue
                work_queue.task_done()
                break
                
            index, entry_id, text = task
            
            # Check if we've been interrupted
            if interrupted:
                work_queue.task_done()
                break
            
            # Translate the text
            translated = translate_text(text, source_lang, target_lang, service)
            
            # Put the result in the result queue
            result_queue.put((index, entry_id, translated))
            
            # Mark the task as done
            work_queue.task_done()
            
        except queue.Empty:
            # No more tasks
            break
        except Exception as e:
            print(f"Error in worker: {e}")
            # Mark the task as done even if it failed
            if 'task' in locals() and task is not None:
                work_queue.task_done()

def batch_translate(texts, source_lang, target_lang, service, num_workers=MAX_WORKERS):
    """
    Translate a batch of texts in parallel.
    
    Args:
        texts: List of (index, entry_id, text) tuples
        source_lang: Source language code
        target_lang: Target language code
        service: Translation service to use
        num_workers: Number of worker threads
        
    Returns:
        Dictionary mapping entry_id to translated text
    """
    global worker_threads, interrupted
    
    # If interrupted, don't start new translations
    if interrupted:
        return {}
    
    # Create queues for work and results
    work_queue = queue.Queue()
    result_queue = queue.Queue()
    
    # Add tasks to the work queue
    for item in texts:
        work_queue.put(item)
    
    # Add sentinel values to indicate end of queue
    for _ in range(num_workers):
        work_queue.put(None)
    
    # Create and start worker threads
    worker_threads = []
    for _ in range(min(num_workers, len(texts))):
        thread = threading.Thread(
            target=worker_translate,
            args=(work_queue, result_queue, source_lang, target_lang, service)
        )
        thread.daemon = True
        thread.start()
        worker_threads.append(thread)
    
    # Wait for all tasks to be processed or interrupted
    try:
        # Use a timeout to allow checking for interruption
        while not work_queue.empty() and not interrupted:
            time.sleep(0.1)
            
        # If we're interrupted, don't wait for the queue to be empty
        if not interrupted:
            work_queue.join()
    except KeyboardInterrupt:
        interrupted = True
        print("\nInterrupt received during batch translation")
    
    # Get results
    results = {}
    while not result_queue.empty():
        index, entry_id, translated = result_queue.get()
        results[entry_id] = translated
    
    return results

def translate_po_file(input_file, output_file, batch_size=10, service=TRANSLATION_SERVICE, 
                     ignore_translated=False, save_interval=50, target_lang=DEFAULT_TARGET_LANG,
                     source_lang=None, num_workers=MAX_WORKERS):
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
        num_workers: Number of worker threads/processes for parallel translation
    """
    global interrupted, backup_file, worker_threads
    
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
        print(f"Using {num_workers} worker threads for parallel translation")
        
        # Load translation cache
        load_translation_cache(input_file, target_lang)
        
        if ignore_translated:
            print("Ignoring already translated entries (keeping existing translations)")
        
        # Count entries that need translation
        entries_to_translate = []
        for i, entry in enumerate(po):
            if entry.msgid and not entry.obsolete:
                if not entry.msgstr and not ignore_translated:
                    entries_to_translate.append((i, 'msgstr', entry.msgid))
                elif not entry.msgstr and ignore_translated:
                    entries_to_translate.append((i, 'msgstr', entry.msgid))
                
                # Count plural forms that need translation
                if entry.msgid_plural and entry.msgstr_plural:
                    for plural_index in entry.msgstr_plural:
                        if not entry.msgstr_plural[plural_index] and not ignore_translated:
                            plural_text = entry.msgid_plural if plural_index != '0' else entry.msgid
                            entries_to_translate.append((i, f'msgstr_plural_{plural_index}', plural_text))
                        elif not entry.msgstr_plural[plural_index] and ignore_translated:
                            plural_text = entry.msgid_plural if plural_index != '0' else entry.msgid
                            entries_to_translate.append((i, f'msgstr_plural_{plural_index}', plural_text))
        
        total_to_translate = len(entries_to_translate)
        
        if total_to_translate == 0:
            print("No entries need translation. Saving file as is.")
            po.save(output_file)
            return
        
        print(f"Found {total_to_translate} entries that need translation")
        print(f"Progress will be saved every {save_interval} translations")
        
        # Update the metadata to reflect the new language
        if 'Language' in po.metadata:
            po.metadata['Language'] = target_lang
        
        # Process entries in batches with progress bar if tqdm is available
        if use_tqdm:
            progress_bar = tqdm(total=total_to_translate, desc="Translating")
        else:
            print("Starting translation...")
        
        translated_count = 0
        
        # Process in optimized batches
        for batch_start in range(0, total_to_translate, batch_size):
            if interrupted:
                print("Translation interrupted. Saving progress...")
                break
                
            # Get the current batch
            current_batch = entries_to_translate[batch_start:batch_start + batch_size]
            
            # Translate the batch in parallel
            batch_results = batch_translate(
                current_batch, 
                source_lang, 
                target_lang, 
                service,
                num_workers
            )
            
            # If we were interrupted during batch translation, break the loop
            if interrupted:
                print("Batch translation interrupted. Saving progress...")
                break
            
            # Update the PO file with translations
            for i, entry_id, _ in current_batch:
                if entry_id == 'msgstr':
                    po[i].msgstr = batch_results.get(entry_id, '')
                elif entry_id.startswith('msgstr_plural_'):
                    plural_index = entry_id.split('_')[-1]
                    # Convert plural_index to the same type as used in the PO file
                    if isinstance(next(iter(po[i].msgstr_plural.keys()), '0'), int):
                        plural_index = int(plural_index)
                    po[i].msgstr_plural[plural_index] = batch_results.get(entry_id, '')
            
            translated_count += len(current_batch)
            
            # Update progress bar
            if use_tqdm:
                progress_bar.update(len(current_batch))
            elif translated_count % (batch_size * 5) == 0 or translated_count == total_to_translate:
                progress = min(100, int(translated_count / total_to_translate * 100))
                print(f"Progress: {progress}% ({translated_count}/{total_to_translate})")
            
            # Save progress periodically
            if translated_count % save_interval == 0 or translated_count == total_to_translate:
                print(f"Saving progress after {translated_count} translations...")
                save_progress(po, output_file)
        
        if use_tqdm:
            progress_bar.close()
        
        # Save the final translated PO file with a timeout
        print("Saving final translation...")
        try:
            # Use a separate thread with timeout for saving to prevent hanging
            save_thread = threading.Thread(target=save_progress, args=(po, output_file, True))
            save_thread.daemon = True
            save_thread.start()
            
            # Wait for the save to complete with a timeout
            save_thread.join(timeout=30)  # 30 seconds timeout
            
            if save_thread.is_alive():
                print("Warning: Save operation is taking too long. It will continue in the background.")
                print(f"Your file will be saved to {output_file} when complete.")
            else:
                print(f"Final translation saved to: {output_file}")
        except Exception as e:
            print(f"Error during final save: {e}")
            print("Attempting direct save...")
            try:
                po.save(output_file)
                print(f"Saved directly to: {output_file}")
            except Exception as e2:
                print(f"Failed to save: {e2}")
        
        # Save the translation cache
        save_translation_cache()
        
        if interrupted:
            print(f"Interrupted! Translated {translated_count}/{total_to_translate} entries before interruption.")
            print(f"You can resume by running the script again with the -i flag to keep existing translations.")
        else:
            print(f"Translation completed. Translated {translated_count} entries.")
        
    except Exception as e:
        print(f"Error: {e}")
        
        # Try to save progress if we have a PO file loaded
        if 'po' in locals():
            print("Attempting to save progress after error...")
            try:
                # Direct save without threading to avoid hanging
                po.save(output_file)
                print(f"Progress saved after error. You can resume with the -i flag.")
            except Exception as e2:
                print(f"Failed to save progress after error: {e2}")
        
        # Save the translation cache
        if 'translation_cache' in globals() and translation_cache:
            save_translation_cache()
        
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
    parser.add_argument("-w", "--workers", type=int, default=MAX_WORKERS,
                        help=f"Number of worker threads for parallel translation (default: {MAX_WORKERS})")
    parser.add_argument("--no-cache", action="store_true",
                        help="Disable translation caching (not recommended)")
    
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
    
    # Disable caching if requested
    if args.no_cache:
        global translation_cache
        translation_cache = None
        print("Translation caching disabled")
    
    translate_po_file(
        args.input_file, 
        output_file, 
        args.batch_size, 
        args.service, 
        args.ignore_translated, 
        args.save_interval,
        args.target,
        args.source,
        args.workers
    )

if __name__ == "__main__":
    main()
