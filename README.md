# Lightroom Preset Auto-Processor

A high-quality, automated image processing application that watches a folder for new subfolders and automatically applies Lightroom presets to images within those folders. Designed for maximum image quality with proper color management and RAW file support.

## Features

- **High-Quality Processing**: Maintains 16-bit color depth, proper color profiles, and lossless output formats
- **RAW File Support**: Full support for RAW formats (CR2, NEF, ARW, DNG, RAF, ORF, RW2, CR3) using libraw
- **Automatic Folder Monitoring**: Watches a configurable folder and processes images in new subfolders automatically
- **XMP Preset Support**: Parses and applies Lightroom `.xmp` preset files
- **Stable Background Operation**: Runs as a system service/daemon with auto-restart capabilities
- **Boot-Time Startup**: Automatically starts when the computer boots
- **Concurrent Processing**: Multi-threaded processing for efficient handling of multiple images
- **Error Handling**: Robust error handling with retry logic and comprehensive logging

## Requirements

- Python 3.9 or later
- libraw (for RAW file processing)
- Required Python packages (see `requirements.txt`)

### System Dependencies

**macOS:**

```bash
# Install libraw via Homebrew
brew install libraw
```

**Linux (Ubuntu/Debian):**

```bash
sudo apt-get update
sudo apt-get install libraw-dev python3-dev
```

**Linux (Fedora/RHEL):**

```bash
sudo dnf install LibRaw-devel python3-devel
```

**Windows:**

- Download libraw from: https://www.libraw.org/download
- Or use pre-built wheels if available

## Installation

1. **Clone or download this repository**

2. **Create a virtual environment (recommended):**

```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# On Windows: venv\Scripts\activate
```

3. **Install Python dependencies:**

```bash
pip install -r requirements.txt
```

**Note**:

- If you're not using a virtual environment and get an "externally-managed-environment" error, you can use:
  - `pip3 install --user -r requirements.txt` (installs to user directory)
  - Or create a virtual environment (recommended above)
- On macOS, use `pip3` instead of `pip` if `pip` is not available

4. **Install system dependencies** (see above)

5. **Configure the application:**

   - Edit `config.yaml` with your settings:
     - `watch_folder`: Folder to monitor for new subfolders (supports absolute or relative paths)
     - `preset_path`: Path to your Lightroom `.xmp` preset file (supports absolute or relative paths)
     - `output_format`: "tiff" (16-bit, lossless) or "jpg" (high-quality)
     - Other settings as needed
   - **Note**: Both `watch_folder` and `preset_path` support absolute paths (e.g., `/Users/name/Documents/watch`) and relative paths (e.g., `./watch` or `../watched`). Relative paths are resolved relative to the `config.yaml` file's directory.

6. **Test the application:**

```bash
# If using virtual environment, activate it first:
source venv/bin/activate  # On macOS/Linux

python3 main.py
```

6. **Install as a service** (choose based on your OS):

   **macOS:**

   ```bash
   ./install_service.sh
   ```

   **Linux:**

   ```bash
   sudo ./install_service_linux.sh
   ```

   **Windows:**

   **Option 1 - PM2 (Recommended, easiest):**
   ```cmd
   install_pm2.bat
   ```
   Requires Node.js (downloads automatically if needed)

   **Option 2 - Supervisor (Python-native):**
   ```cmd
   install_supervisor.bat
   ```

   **Option 3 - NSSM (Traditional Windows Service):**
   ```cmd
   install_service.bat
   ```

   **Detailed Windows installation instructions:** See [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md) for step-by-step guide.
   
   **Note:** PM2 is recommended as it's the simplest and most user-friendly option. NSSM requires additional setup.

## Configuration

Edit `config.yaml` to customize the application:

```yaml
# Folder to watch for new subfolders
# Supports both absolute paths (e.g., "/Users/name/Documents/watch")
# and relative paths (e.g., "./watch" or "../watched")
# Relative paths are resolved relative to the config file's directory
watch_folder: "/path/to/watch"
# Example relative: "./watch" or "../watched"

# Path to the Lightroom preset file (.xmp)
# Supports both absolute paths (e.g., "/Users/name/presets/default.xmp")
# and relative paths (e.g., "./presets/default.xmp" or "../presets/default.xmp")
# Relative paths are resolved relative to the config file's directory
preset_path: "/path/to/preset.xmp"
# Example relative: "./presets/default.xmp" or "../presets/default.xmp"

# Output format: "tiff" (16-bit, lossless) or "jpg"
output_format: "tiff"

# JPEG quality (1-100, only used if output_format is "jpg")
jpeg_quality: 95

# Output subfolder name within each processed folder
output_folder: "processed"

# Enable RAW file processing
raw_processing: true

# Color profile: "sRGB", "AdobeRGB", "ProPhotoRGB", or "preserve"
color_profile: "sRGB"

# Processing settings
processing:
  debounce_seconds: 2 # Wait time before processing after folder creation
  max_concurrent_jobs: 2 # Number of concurrent processing threads
  retry_failed: true # Retry failed images
  max_retries: 3 # Maximum retry attempts

# Logging
logging:
  level: "INFO" # DEBUG, INFO, WARNING, ERROR
  file: "preset_processor.log"
  console: true
```

## How It Works

1. **Folder Monitoring**: The application watches the configured `watch_folder` for new subfolder creation
2. **Debouncing**: When a new folder is detected, it waits a configurable amount of time (default 2 seconds) to ensure the folder is fully created
3. **Image Discovery**: Scans the new folder for supported image files (RAW and standard formats)
4. **Preset Application**:
   - Parses the XMP preset file to extract Lightroom adjustments
   - For RAW files: Uses rawpy (libraw) for high-quality demosaicing and processing
   - For standard formats: Uses Pillow with proper color management
   - Applies adjustments: Exposure, Contrast, Highlights, Shadows, Whites, Blacks, Clarity, Vibrance, Saturation, White Balance, etc.
5. **Quality Preservation**:
   - Maintains 16-bit color depth for RAW files
   - Preserves color profiles
   - Outputs to lossless TIFF or high-quality JPEG
6. **Output**: Saves processed images to a `processed` subfolder (configurable) within each source folder

## Supported Adjustments

The application supports the following Lightroom adjustments from XMP presets:

- **Exposure** (EV stops)
- **Contrast** (-100 to +100)
- **Highlights** (-100 to +100)
- **Shadows** (-100 to +100)
- **Whites** (-100 to +100)
- **Blacks** (-100 to +100)
- **Clarity** (local contrast enhancement)
- **Vibrance** (selective saturation)
- **Saturation** (global saturation)
- **Temperature** (white balance)
- **Tint** (white balance)

## Supported Image Formats

### RAW Formats:

- Canon: `.cr2`, `.cr3`
- Nikon: `.nef`
- Sony: `.arw`
- Adobe: `.dng`
- Fujifilm: `.raf`
- Olympus: `.orf`
- Panasonic: `.rw2`

### Standard Formats:

- JPEG: `.jpg`, `.jpeg`
- TIFF: `.tif`, `.tiff`
- PNG: `.png`

## Quality Settings

### Maximum Quality (Recommended):

- `output_format: "tiff"` - 16-bit TIFF with LZW compression (lossless)
- Best for archival and further editing

### High Quality (Smaller Files):

- `output_format: "jpg"`
- `jpeg_quality: 95` - Very high quality JPEG
- Good balance between quality and file size

## Logging

The application creates detailed logs:

- **Application Log**: `preset_processor.log` - Main application log
- **Service Output**: `service_output.log` - Service stdout (when running as service)
- **Service Error**: `service_error.log` - Service stderr (when running as service)

Log levels: DEBUG, INFO, WARNING, ERROR

## Troubleshooting

### Application won't start

- Check that Python 3.9+ is installed: `python3 --version`
- Verify all dependencies are installed: `pip3 install -r requirements.txt`
- Check that libraw is installed on your system
- Review `preset_processor.log` for error messages

### Images not processing

- Verify the preset file path is correct in `config.yaml`
- Check that the preset file is a valid XMP file
- Ensure image files are in supported formats
- Check logs for specific error messages

### Service not starting on boot

- **macOS**: Check LaunchAgent status: `launchctl list | grep presetprocessor`
- **Linux**: Check service status: `sudo systemctl status lightroom-preset-processor`
- **Windows**: Check service status in Services manager

### Quality issues

- Use `output_format: "tiff"` for maximum quality
- Ensure `raw_processing: true` for RAW files
- Check that color profiles are being applied correctly
- Verify source images are high quality

## Manual Operation

To run the application manually (without service):

```bash
python3 main.py
```

Press `Ctrl+C` to stop.

## Uninstalling the Service

**macOS:**

```bash
launchctl unload ~/Library/LaunchAgents/com.lightroom.presetprocessor.plist
rm ~/Library/LaunchAgents/com.lightroom.presetprocessor.plist
```

**Linux:**

```bash
sudo systemctl stop lightroom-preset-processor
sudo systemctl disable lightroom-preset-processor
sudo rm /etc/systemd/system/lightroom-preset-processor.service
sudo systemctl daemon-reload
```

**Windows:**

```cmd
nssm stop LightroomPresetProcessor
nssm remove LightroomPresetProcessor confirm
```

## Performance Tips

- Adjust `max_concurrent_jobs` based on your CPU cores
- Use SSD storage for faster processing
- For large batches, consider processing during off-hours
- Monitor system resources (CPU, RAM) during processing

## License

This project is provided as-is for use in your workflow.

## Support

For issues or questions:

1. Check the logs: `preset_processor.log`
2. Review the configuration in `config.yaml`
3. Verify all dependencies are installed correctly
4. Test with a single image manually before batch processing

## Notes

- The application processes images in-place (creates a `processed` subfolder)
- Original images are never modified
- Processing is non-destructive
- The application will automatically retry failed images (if configured)
- Folder monitoring is recursive only for direct children (not nested subfolders)
