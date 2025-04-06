# PO File Translator

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL%203.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

A Python script that automatically detects the source language of PO files (gettext translation files) and translates them to any target language. The script can handle large files by processing entries in batches and saves progress periodically to prevent data loss.

<p align="center">
  <img src="https://raw.githubusercontent.com/behnam/Dev/Translator/assets/po_translator_logo.png" alt="PO Translator Logo" width="200" />
</p>

## Features

- **Automatic Language Detection**: Detects the source language from PO file content and metadata
- **Flexible Target Language**: Translate to any supported language (not just Persian)
- **Multiple Translation Services**: Supports Google Translate (default), LibreTranslate, and MyMemory
- **Batch Processing**: Translates entries in batches to handle large files efficiently
- **Progress Saving**: Automatically saves progress periodically to prevent data loss if interrupted
- **Preserve Existing Translations**: Option to keep existing translations and only translate missing entries
- **Progress Bar**: Visual progress indicator (if tqdm is installed)

## Requirements

- Python 3.6+
- Required packages:
  - `polib`: For parsing and manipulating PO files
- Optional packages:
  - `googletrans`: For Google Translate API (no API key required)
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

## How Progress Saving Works

The script automatically saves progress at regular intervals (default: every 50 translations). If the script is interrupted for any reason (Ctrl+C, system crash, etc.), you can resume translation by running the script again with the `-i` flag to keep existing translations.

When saving progress, the script creates timestamped backup files (e.g., `input_backup_20250406_181911.po`). The final output will be saved to the specified output file.

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

Your Name - [@your_twitter](https://twitter.com/your_twitter) - email@example.com

Project Link: [https://github.com/yourusername/po-translator](https://github.com/yourusername/po-translator)
