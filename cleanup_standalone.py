#!/usr/bin/env python3
"""
Standalone Image Cleanup Script
Can be run as a cron job independently of the main application
Usage: python cleanup_standalone.py
"""

import sys
import os
import logging
import yaml
from pathlib import Path
from colorama import init, Fore, Style
from cleanup_old_images import ImageCleanup

# Initialize colorama
init(autoreset=True)

def resolve_path(path_str: str, base_dir: Path) -> Path:
    """Resolve a path string to an absolute Path"""
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()

def load_config(config_path: str = 'config.yaml') -> dict:
    """Load configuration from YAML file"""
    script_dir = Path(__file__).parent.resolve()
    config_file = script_dir / config_path
    
    if not config_file.exists():
        print(f"{Fore.RED}Error: Configuration file not found: {config_path}")
        sys.exit(1)
    
    config_dir = config_file.parent
    
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Resolve paths
        if 'watch_folder' in config:
            config['watch_folder'] = str(resolve_path(config['watch_folder'], config_dir))
        
        if 'lightroom_watched_folder' in config:
            config['lightroom_watched_folder'] = str(resolve_path(config['lightroom_watched_folder'], config_dir))
        
        if 'lightroom_destination_folder' in config:
            config['lightroom_destination_folder'] = str(resolve_path(config['lightroom_destination_folder'], config_dir))
        
        # Resolve cleanup folder paths (use normalize_path for Windows compatibility)
        if 'cleanup' in config and 'folders' in config['cleanup']:
            from cleanup_old_images import normalize_path
            resolved_folders = []
            for folder in config['cleanup']['folders']:
                # For absolute paths (Windows drives, UNC), use normalize_path
                # For relative paths, use resolve_path
                if Path(folder).is_absolute() or (len(folder) >= 2 and folder[1] == ':'):
                    resolved_folders.append(str(normalize_path(folder)))
                else:
                    resolved_folders.append(str(resolve_path(folder, config_dir)))
            config['cleanup']['folders'] = resolved_folders
        
        return config
    
    except Exception as e:
        print(f"{Fore.RED}Error: Failed to load configuration: {e}")
        sys.exit(1)

def setup_logging(config: dict):
    """Setup logging configuration"""
    log_config = config.get('logging', {})
    log_level = getattr(logging, log_config.get('level', 'INFO').upper())
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    log_file = log_config.get('file', 'preset_processor.log')
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    
    if log_config.get('console', True):
        root_logger.addHandler(console_handler)

if __name__ == '__main__':
    # Change to script directory
    script_dir = Path(__file__).parent.resolve()
    os.chdir(script_dir)
    
    # Load config
    config = load_config()
    
    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    logger.info("Running standalone image cleanup")
    
    # Create cleanup instance
    cleanup = ImageCleanup(config)
    
    if not cleanup.enabled:
        logger.info("Cleanup is disabled in config")
        sys.exit(0)
    
    if not cleanup.folders:
        logger.warning("No cleanup folders configured")
        sys.exit(0)
    
    # Run cleanup once
    cleanup._run_cleanup()
    
    logger.info("Standalone cleanup completed")

