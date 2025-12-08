# Running with PM2 on Windows

PM2 is a popular process manager that works great with Python scripts. It provides automatic restart, monitoring, and easy log management.

## Prerequisites

1. **Node.js** - Download and install from https://nodejs.org/
2. **Python 3.9+** - Already installed

## Installation

### Step 1: Install PM2

Open Command Prompt and run:

```cmd
npm install -g pm2
```

### Step 2: Navigate to Project Directory

```cmd
cd C:\path\to\self_booth_1
```

### Step 3: Start the Application

Find your Python executable path first:

```cmd
where python
```

Then start with PM2 (replace `C:\Python313\python.exe` with your actual Python path):

```cmd
pm2 start C:\Python313\python.exe --name lightroom-preset-processor -- main.py
```

**Note:** If Python is in your PATH and not the Microsoft Store shim, you can use:

```cmd
pm2 start python --name lightroom-preset-processor -- main.py
```

### Step 4: Save PM2 Process List

This ensures PM2 remembers your processes:

```cmd
pm2 save
```

### Step 5: Enable Auto-Start on Boot (Windows)

PM2's built-in `startup` command doesn't work on Windows. Use Windows Task Scheduler instead:

1. **Open Task Scheduler:**
   - Press `Win + R`
   - Type `taskschd.msc` and press Enter

2. **Create Basic Task:**
   - Click "Create Basic Task" in the right panel
   - Name: `PM2 Startup`
   - Description: `Start PM2 processes on Windows boot`
   - Click Next

3. **Set Trigger:**
   - Select "When the computer starts"
   - Click Next

4. **Set Action:**
   - Select "Start a program"
   - Click Next
   - Program/script: `pm2` (or full path: `C:\Users\YourName\AppData\Roaming\npm\pm2.cmd`)
   - Add arguments: `resurrect`
   - Start in: `C:\path\to\self_booth_1` (your project directory)
   - Click Next

5. **Finish:**
   - Check "Open the Properties dialog for this task when I click Finish"
   - Click Finish

6. **Configure Additional Settings:**
   - In Properties dialog:
     - **General tab**: Check "Run whether user is logged on or not"
     - **General tab**: Check "Run with highest privileges"
     - **Conditions tab**: Uncheck "Start the task only if the computer is on AC power" (optional)
     - **Settings tab**: Select "If the task fails, restart every: 1 minute"
     - Click OK

Now PM2 will automatically start and restore your processes when Windows boots.

## Managing the Application

### View Status

```cmd
pm2 list
```

### View Logs

```cmd
pm2 logs lightroom-preset-processor
```

View last 100 lines:
```cmd
pm2 logs lightroom-preset-processor --lines 100
```

### Restart

```cmd
pm2 restart lightroom-preset-processor
```

### Stop

```cmd
pm2 stop lightroom-preset-processor
```

### Start

```cmd
pm2 start lightroom-preset-processor
```

### Delete (Remove from PM2)

```cmd
pm2 delete lightroom-preset-processor
```

### Monitor Dashboard

```cmd
pm2 monit
```

This opens an interactive dashboard showing CPU, memory, and logs.

## Configuration

### Auto-Restart on Failure

PM2 automatically restarts your process if it crashes. To configure restart behavior:

```cmd
pm2 start python --name lightroom-preset-processor -- main.py --max-restarts 10 --min-uptime 1000
```

### Environment Variables

Set environment variables:

```cmd
pm2 start python --name lightroom-preset-processor -- main.py --env production
```

Or create an ecosystem file (`ecosystem.config.js`):

```javascript
module.exports = {
  apps: [{
    name: 'lightroom-preset-processor',
    script: 'main.py',
    interpreter: 'C:\\Python313\\python.exe',
    cwd: 'C:\\path\\to\\self_booth_1',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      NODE_ENV: 'production'
    }
  }]
}
```

Then start with:

```cmd
pm2 start ecosystem.config.js
```

## Logs Location

PM2 stores logs in:
- `%USERPROFILE%\.pm2\logs\` (default)
- Or check with: `pm2 describe lightroom-preset-processor`

Application logs are still in your project directory:
- `service_output.log`
- `service_error.log`
- `preset_processor.log`

## Troubleshooting

### Process Not Starting

Check logs:
```cmd
pm2 logs lightroom-preset-processor --err
```

### Wrong Python Path

If you get errors about Python, specify the full path:
```cmd
pm2 delete lightroom-preset-processor
pm2 start C:\Python313\python.exe --name lightroom-preset-processor -- main.py
```

### PM2 Not Found

Make sure Node.js is installed and PM2 is installed globally:
```cmd
node --version
npm --version
npm install -g pm2
```

### Auto-Start Not Working

1. Make sure you ran `pm2 save` after starting the process
2. Verify the Task Scheduler task exists:
   - Open Task Scheduler (`Win + R`, type `taskschd.msc`)
   - Look for "PM2 Startup" task
   - Check if it's enabled
3. Test the task manually:
   - Right-click "PM2 Startup" → Run
   - Check if PM2 processes start: `pm2 list`
4. Check Task Scheduler history:
   - Right-click "PM2 Startup" → Properties → History tab
   - Look for any errors
5. Verify PM2 path in Task Scheduler:
   - Make sure the `pm2` command path is correct
   - Try using full path: `C:\Users\YourName\AppData\Roaming\npm\pm2.cmd`

## Advantages of PM2

- ✅ Simple installation and usage
- ✅ Built-in monitoring dashboard
- ✅ Automatic restart on failure
- ✅ Easy log management
- ✅ Works great with Python
- ✅ Cross-platform (if needed)
- ✅ No complex Windows service configuration

## Uninstall

To remove PM2:

```cmd
npm uninstall -g pm2
```

To remove the startup task:

1. Open Task Scheduler (`Win + R`, type `taskschd.msc`)
2. Find "PM2 Startup" task
3. Right-click → Delete

