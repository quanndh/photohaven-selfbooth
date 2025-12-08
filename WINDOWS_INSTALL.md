# Windows Service Installation Guide

## Method 1: Using NSSM (Recommended)

### Prerequisites

1. **Python 3.9+ installed** and added to PATH
2. **NSSM (Non-Sucking Service Manager)** installed

### Step-by-Step Installation

#### Step 1: Install NSSM

1. Download NSSM from: https://nssm.cc/download
2. Extract the ZIP file
3. Copy the appropriate version folder (64-bit or 32-bit) to a permanent location (e.g., `C:\Program Files\nssm`)
4. Add NSSM to your PATH:
   - Open System Properties → Advanced → Environment Variables
   - Edit the "Path" variable
   - Add the path to the NSSM folder (e.g., `C:\Program Files\nssm\win64`)
   - Click OK to save

#### Step 2: Verify NSSM Installation

Open Command Prompt (as Administrator) and run:

```cmd
nssm version
```

If you see a version number, NSSM is installed correctly.

#### Step 3: Configure the Application

1. Edit `config.yaml` with your settings:
   - Set `watch_folder`: The folder to monitor for new subfolders
   - Set `preset_path`: Path to your Lightroom `.xmp` preset file

#### Step 4: Install the Service

1. Open Command Prompt **as Administrator** (Right-click → Run as administrator)
2. Navigate to the project directory:
   ```cmd
   cd C:\path\to\self_booth_1
   ```
3. Run the installation script:
   ```cmd
   install_service.bat
   ```

The script will:

- Detect Python installation
- Check for NSSM
- Install the service
- Configure it to start automatically on boot
- Start the service immediately

#### Step 5: Verify Installation

Check if the service is running:

```cmd
sc query LightroomPresetProcessor
```

Or check in Services Manager:

1. Press `Win + R`, type `services.msc`, press Enter
2. Look for "Lightroom Preset Auto-Processor"
3. Status should be "Running"

---

## Method 2: Using Task Scheduler (Alternative)

If you prefer not to use NSSM, you can use Windows Task Scheduler:

### Step-by-Step Installation

#### Step 1: Configure the Application

1. Edit `config.yaml` with your settings

#### Step 2: Create Scheduled Task

1. Open Task Scheduler:

   - Press `Win + R`, type `taskschd.msc`, press Enter
   - Or search for "Task Scheduler" in Start menu

2. Create Basic Task:

   - Click "Create Basic Task" in the right panel
   - Name: `Lightroom Preset Auto-Processor`
   - Description: `Automatically applies Lightroom presets to images`

3. Set Trigger:

   - Select "When the computer starts"
   - Click Next

4. Set Action:

   - Select "Start a program"
   - Program/script: Browse to your Python executable (e.g., `C:\Python39\python.exe`)
   - Add arguments: `main.py`
   - Start in: Browse to your project directory (e.g., `C:\path\to\self_booth_1`)
   - Click Next

5. Finish:

   - Check "Open the Properties dialog for this task when I click Finish"
   - Click Finish

6. Configure Additional Settings:
   - In Properties dialog:
     - **General tab**: Check "Run whether user is logged on or not"
     - **General tab**: Check "Run with highest privileges"
     - **Conditions tab**: Uncheck "Start the task only if the computer is on AC power" (if you want it to run on battery)
     - **Settings tab**: Select "If the task fails, restart every: 1 minute"
     - Click OK

#### Step 3: Test the Task

1. Right-click the task in Task Scheduler
2. Select "Run"
3. Check if the application starts (check logs in the project directory)

---

## Managing the Service

### Check Service Status

**Using NSSM:**

```cmd
nssm status LightroomPresetProcessor
```

**Using Windows Services:**

```cmd
sc query LightroomPresetProcessor
```

**Using Services Manager:**

- Open `services.msc` and look for "Lightroom Preset Auto-Processor"

### Start the Service

**Using NSSM:**

```cmd
nssm start LightroomPresetProcessor
```

**Using Windows Services:**

```cmd
net start LightroomPresetProcessor
```

### Stop the Service

**Using NSSM:**

```cmd
nssm stop LightroomPresetProcessor
```

**Using Windows Services:**

```cmd
net stop LightroomPresetProcessor
```

### Restart the Service

**Using NSSM:**

```cmd
nssm restart LightroomPresetProcessor
```

### Remove the Service

**Using NSSM:**

```cmd
nssm stop LightroomPresetProcessor
nssm remove LightroomPresetProcessor confirm
```

**Using Task Scheduler:**

- Open Task Scheduler
- Find the task
- Right-click → Delete

---

## Viewing Logs

Logs are located in the project directory:

- **Application Log**: `preset_processor.log`
- **Service Output**: `service_output.log`
- **Service Errors**: `service_error.log`

You can view them with any text editor or Notepad.

---

## Troubleshooting

### Service Won't Start (SERVICE_STOPPED error)

This error means the service starts but immediately stops, usually due to a startup error.

**Step 1: Check the error logs**

```cmd
type service_error.log
type service_output.log
```

**Step 2: Test the application manually**

Run the application directly to see the actual error:

```cmd
cd C:\path\to\self_booth_1
python main.py
```

**Step 3: Common causes and fixes**

1. **Missing Python dependencies:**
   ```cmd
   pip install -r requirements.txt
   ```
   If `rawpy` fails to install (Python 3.14+), either:
   - Use Python 3.9-3.13, or
   - Set `raw_processing: false` in `config.yaml` and skip rawpy

2. **Config file issues:**
   - Ensure `config.yaml` exists in the project directory
   - Check that `watch_folder` and `preset_path` are correct
   - Verify paths exist (or can be created)

3. **Preset file not found:**
   - Check that the `preset_path` in `config.yaml` points to a valid `.xmp` file
   - Use absolute paths if relative paths don't work

4. **Python not found:**
   ```cmd
   python --version
   where python
   ```
   If Python is not found, reinstall Python and ensure it's added to PATH

5. **Permission issues:**
   - Ensure the service account has read/write access to:
     - Project directory
     - Watch folder
     - Output folders

**Step 4: Reinstall the service**

After fixing issues, reinstall:

```cmd
nssm stop LightroomPresetProcessor
nssm remove LightroomPresetProcessor confirm
install_service.bat
```

### Service Starts But Doesn't Process Images

1. Verify `watch_folder` path in `config.yaml` is correct
2. Verify `preset_path` in `config.yaml` exists and is valid
3. Check `preset_processor.log` for errors

### Service Not Starting on Boot

**For NSSM:**

- Verify service is set to "Automatic" startup:
  ```cmd
  sc config LightroomPresetProcessor start= auto
  ```

**For Task Scheduler:**

- Verify task is enabled
- Check task history in Task Scheduler for errors

---

## Notes

- The service runs in the background and starts automatically on boot
- It will continue running even when you log out
- To stop the service, you must use the commands above or Services Manager
- The service will automatically restart if it crashes (when using NSSM with default settings)
