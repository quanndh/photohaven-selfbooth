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

### Step 5: Enable Auto-Start on Boot

Run this command as Administrator:

```cmd
pm2 startup
```

It will output a command like `pm2-startup install`. Copy and run that command as Administrator.

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
2. Make sure you ran the `pm2 startup` command as Administrator
3. Check Windows Task Scheduler for the PM2 startup task

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

To remove the startup task, run as Administrator:

```cmd
pm2-startup uninstall
```

