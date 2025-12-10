# Image Cleanup Cron Job Setup

## Overview

The image cleanup runs automatically every 30 minutes when the main application is running. You can also set up a standalone cron job to run cleanup independently.

## Option 1: Built-in Cleanup (Recommended)

The cleanup runs automatically as part of the main application. Just ensure `cleanup.enabled: true` in `config.yaml`.

## Option 2: Standalone Cron Job

If you want to run cleanup independently (even when main app is not running), set up a cron job:

### macOS/Linux Cron Setup

1. **Make the script executable:**
   ```bash
   chmod +x cleanup_standalone.py
   ```

2. **Edit crontab:**
   ```bash
   crontab -e
   ```

3. **Add this line to run every 30 minutes:**
   ```cron
   */30 * * * * cd /Users/quanndh/Documents/job/self_booth_1 && /path/to/python cleanup_standalone.py >> cleanup_cron.log 2>&1
   ```

   Replace:
   - `/Users/quanndh/Documents/job/self_booth_1` with your actual project path
   - `/path/to/python` with your Python path (e.g., `/usr/bin/python3` or `/Users/quanndh/Documents/job/self_booth_1/venv/bin/python`)

4. **Example with virtual environment:**
   ```cron
   */30 * * * * cd /Users/quanndh/Documents/job/self_booth_1 && /Users/quanndh/Documents/job/self_booth_1/venv/bin/python cleanup_standalone.py >> cleanup_cron.log 2>&1
   ```

### Windows Task Scheduler

1. Open **Task Scheduler**
2. Create **Basic Task**
3. Name: "Image Cleanup"
4. Trigger: **Daily** → Recur every 30 minutes
5. Action: **Start a program**
   - Program: `python.exe` (or full path to Python)
   - Arguments: `cleanup_standalone.py`
   - Start in: `C:\path\to\self_booth_1`
6. Save

## Configuration

Edit `config.yaml`:

```yaml
cleanup:
  enabled: true
  folders:
    - "../lightroom_watched"
    - "../lightroom_processed"
  max_age_minutes: 30  # Delete images older than 30 minutes
  interval_minutes: 30  # Run cleanup every 30 minutes
```

## How It Works

- Checks configured folders every 30 minutes (or custom interval)
- Deletes image files older than 30 minutes (or custom max age)
- Only deletes files with supported image extensions
- Logs all deletions and errors

## Testing

Test the cleanup manually:

```bash
python cleanup_standalone.py
```

Check the logs to see what was deleted.

## Notes

- Cleanup uses file modification time (`st_mtime`) to determine age
- Only image files matching `supported_extensions` are deleted
- Folders are cleaned recursively (all subdirectories)
- Safe to run - only deletes files, never folders

