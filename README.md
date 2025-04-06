# PO File Translator

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL%203.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

A Python script that automatically detects the source language of PO files (gettext translation files) and translates them to any target language. The script can handle large files by processing entries in batches and saves progress periodically to prevent data loss.


If this project is helpful to you, you may wish to give it a 🌟

If you'd like to support the development of this project, you can donate:
- USDT (TRC20): TXpJ3V46j6oBRiThg8HV98FexoZ5AKB1tc
- TRX tron (TRC20): TXpJ3V46j6oBRiThg8HV98FexoZ5AKB1tc


## Features

- **Automatic Language Detection**: Detects the source language from PO file content and metadata
- **Flexible Target Language**: Translate to any supported language (not just Persian)
- **Multiple Translation Services**: Supports Google Translate (default), LibreTranslate, and MyMemory
- **Parallel Processing**: Uses multi-threading to translate multiple entries simultaneously
- **Translation Caching**: Stores previously translated strings to avoid redundant API calls
- **Batch Processing**: Translates entries in batches to handle large files efficiently
- **Progress Saving**: Automatically saves progress periodically to prevent data loss if interrupted
- **Preserve Existing Translations**: Option to keep existing translations and only translate missing entries
- **Progress Bar**: Visual progress indicator (if tqdm is installed)
- **Robust Error Handling**: Graceful recovery from network issues and interruptions

## Requirements

- Python 3.6+
- Required packages:
  - `polib`: For parsing and manipulating PO files
- Optional packages:
  - `tqdm`: For displaying progress bars

## Installation

### From PyPI (Recommended)

```bash
pip install po-translator
```

### From Source

1. Clone this repository:
```bash
git clone https://github.com/yourusername/po-translator.git
cd po-translator
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python po_translator.py input.po
```

This will automatically detect the source language and translate to Persian (default target language).

### Command-line Options

```
usage: po_translator.py [-h] [-o OUTPUT] [-b BATCH_SIZE] [-s {google,libretranslate,mymemory}]
                        [--source SOURCE] [-t TARGET] [--libretranslate-url LIBRETRANSLATE_URL]
                        [--email EMAIL] [-i] [--save-interval SAVE_INTERVAL] [--list-languages]
                        [-w WORKERS] [--no-cache]
                        input_file

Translate PO files to any language

positional arguments:
  input_file            Path to the input PO file

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Path to the output PO file (default: input_file.[target_lang].po)
  -b BATCH_SIZE, --batch-size BATCH_SIZE
                        Number of entries to translate in each batch (default: 10)
  -s {google,libretranslate,mymemory}, --service {google,libretranslate,mymemory}
                        Translation service to use
  --source SOURCE       Source language code (if not specified, will be auto-detected)
  -t TARGET, --target TARGET
                        Target language code (default: fa - Persian/Farsi)
  --libretranslate-url LIBRETRANSLATE_URL
                        URL for LibreTranslate API (if using libretranslate service)
  --email EMAIL         Email for MyMemory API (increases daily limit)
  -i, --ignore-translated
                        Ignore already translated entries (keep existing translations)
  --save-interval SAVE_INTERVAL
                        Save progress after this many translations (default: 50)
  --list-languages      List available languages and exit
  -w WORKERS, --workers WORKERS
                        Number of worker threads for parallel translation (default: 5)
  --no-cache            Disable translation caching
```

### Examples

List available languages:

```bash
python po_translator.py --list-languages
```

Translate to Spanish, ignoring existing translations:

```bash
python po_translator.py input.po -t es -i
```

Translate to German using MyMemory service:

```bash
python po_translator.py input.po -t de -s mymemory
```

Specify source language explicitly (instead of auto-detection):

```bash
python po_translator.py input.po --source en -t fr
```

Save progress more frequently (every 20 translations):

```bash
python po_translator.py input.po --save-interval 20
```

Use multiple worker threads for faster translation:

```bash
python po_translator.py input.po -w 8
```

Disable caching for testing purposes:

```bash
python po_translator.py input.po --no-cache
```

Optimize for very large files:

```bash
python po_translator.py input.po -b 5 -s 20 -w 3
```

## How Progress Saving Works

The script automatically saves progress at regular intervals (default: every 50 translations). If the script is interrupted for any reason (Ctrl+C, system crash, etc.), you can resume translation by running the script again with the `-i` flag to keep existing translations.

The save process uses a safe approach:
1. First saves to a temporary file
2. Creates a backup of the existing output file
3. Renames the temporary file to the final output file

If the normal save process fails, the script will attempt alternative save methods to ensure your translations are not lost.

## Translation Caching

The script maintains a cache of previously translated strings to improve performance and reduce API calls. The cache is stored in a `.cache` directory and persists between runs. This significantly speeds up translation of files with repeated phrases or when translating multiple similar files.

Cache files are named based on the source file and target language, so different translation projects maintain separate caches.

## Performance Optimization

For best performance with large files:

1. **Adjust Worker Threads**: Use `-w` to set the number of parallel translation threads (default: 5)
   - Increase for faster translation on powerful systems
   - Decrease for more stability on limited resources

2. **Batch Size**: Use `-b` to adjust how many entries are processed at once (default: 10)
   - Smaller batches use less memory but require more API calls
   - Larger batches are faster but use more memory

3. **Save Frequency**: Use `--save-interval` to control how often progress is saved (default: 50)
   - More frequent saves are safer but slower
   - Less frequent saves are faster but riskier if interrupted

## Supported Languages

The script supports a wide range of languages. Use the `--list-languages` option to see all available language codes.

Common language codes:
- `en`: English
- `fa`: Persian/Farsi
- `ar`: Arabic
- `zh`: Chinese
- `fr`: French
- `de`: German
- `es`: Spanish
- `ru`: Russian
- And many more...

## Translation Services

### Google Translate (Default)
- No API key required
- Good quality translations for most language pairs
- May have rate limiting for frequent usage

### LibreTranslate
- Open-source translation API
- Can be self-hosted for unlimited usage
- Use `--libretranslate-url` to specify a custom server

### MyMemory
- Free translation API with a limit of 5000 words per day
- Providing an email with `--email` increases the daily limit
- Good for professional translations with Translation Memory

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Contact

Behnam Moradi - [BehnamMoradi.com](https://BehnamMoradi.com)
