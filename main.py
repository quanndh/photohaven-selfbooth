#!/usr/bin/env python3
"""
Lightroom Preset Auto-Processor
Main application entry point
"""

import sys
import signal
import logging
import yaml
from pathlib import Path
from colorama import init, Fore, Style
from folder_watcher import FolderWatcher
from lightroom_destination_watcher import LightroomDestinationWatcher
from cleanup_old_images import ImageCleanup
from processing_counter import ProcessingCounter

# Initialize colorama for colored console output
init(autoreset=True)


def setup_logging(config: dict):
    """Setup logging configuration"""
    log_config = config.get('logging', {})
    log_level = getattr(logging, log_config.get('level', 'INFO').upper())
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup file handler
    log_file = log_config.get('file', 'preset_processor.log')
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    
    if log_config.get('console', True):
        root_logger.addHandler(console_handler)


def resolve_path(path_str: str, base_dir: Path) -> Path:
    """
    Resolve a path string to an absolute Path.
    If the path is relative, it's resolved relative to base_dir.
    If the path is absolute, it's used as-is.
    
    Args:
        path_str: Path string (can be absolute or relative)
        base_dir: Base directory for resolving relative paths
        
    Returns:
        Resolved absolute Path
    """
    path = Path(path_str)
    
    # If path is already absolute, return it as-is
    if path.is_absolute():
        return path
    
    # Otherwise, resolve relative to base_dir
    return (base_dir / path).resolve()


def load_config(config_path: str = 'config.yaml') -> dict:
    """Load configuration from YAML file"""
    config_file = Path(config_path).resolve()
    
    if not config_file.exists():
        print(f"{Fore.RED}Error: Configuration file not found: {config_path}")
        print(f"{Fore.YELLOW}Please create a config.yaml file. See README.md for details.")
        sys.exit(1)
    
    # Get the directory containing the config file (for resolving relative paths)
    config_dir = config_file.parent
    
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Validate required settings
        required_keys = ['watch_folder']
        for key in required_keys:
            if key not in config:
                print(f"{Fore.RED}Error: Missing required configuration: {key}")
                sys.exit(1)
        
        # Resolve paths (support both absolute and relative)
        if 'watch_folder' in config:
            config['watch_folder'] = str(resolve_path(config['watch_folder'], config_dir))
        
        if 'lightroom_watched_folder' in config:
            config['lightroom_watched_folder'] = str(resolve_path(config['lightroom_watched_folder'], config_dir))
        
        if 'lightroom_destination_folder' in config:
            config['lightroom_destination_folder'] = str(resolve_path(config['lightroom_destination_folder'], config_dir))
        
        return config
    
    except yaml.YAMLError as e:
        print(f"{Fore.RED}Error: Failed to parse configuration file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"{Fore.RED}Error: Failed to load configuration: {e}")
        sys.exit(1)


def main():
    """Main application entry point"""
    # Change to script directory to ensure relative paths work
    script_dir = Path(__file__).parent.resolve()
    import os
    os.chdir(script_dir)
    
    print(f"{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}Lightroom Preset Auto-Processor")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
    
    # Load configuration
    config = load_config()
    
    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting Lightroom Preset Auto-Processor")
    
    # Initialize processing counter (shared between watchers)
    processing_threshold = config.get('processing', {}).get('processing_threshold', 5)
    processing_counter = ProcessingCounter(threshold=processing_threshold)
    logger.info(f"Processing counter initialized with threshold: {processing_threshold}")
    
    # Validate watch folder
    watch_folder = Path(config['watch_folder'])
    if not watch_folder.exists():
        logger.info(f"Creating watch folder: {watch_folder}")
        watch_folder.mkdir(parents=True, exist_ok=True)
    
    # Validate Lightroom folders
    lightroom_watched = Path(config.get('lightroom_watched_folder', '../lightroom-watched'))
    lightroom_watched.mkdir(parents=True, exist_ok=True)
    
    lightroom_destination = Path(config.get('lightroom_destination_folder', '../lightroom-destination'))
    lightroom_destination.mkdir(parents=True, exist_ok=True)
    
    # Initialize folder watcher (for input folders)
    try:
        watcher = FolderWatcher(str(watch_folder), None, config, processing_counter)
        print(f"{Fore.GREEN}Watching input folder: {watch_folder}")
    except Exception as e:
        logger.error(f"Failed to initialize folder watcher: {e}", exc_info=True)
        print(f"{Fore.RED}Error: Failed to start folder watcher: {e}")
        sys.exit(1)
    
    # Initialize Lightroom destination watcher (for processed images)
    try:
        destination_watcher = LightroomDestinationWatcher(
            str(lightroom_destination),
            str(watch_folder),
            config,
            processing_counter
        )
        print(f"{Fore.GREEN}Watching Lightroom destination: {lightroom_destination}")
        print(f"{Fore.GREEN}Lightroom watched folder: {lightroom_watched}")
    except Exception as e:
        logger.error(f"Failed to initialize Lightroom destination watcher: {e}", exc_info=True)
        print(f"{Fore.RED}Error: Failed to start Lightroom destination watcher: {e}")
        sys.exit(1)
    
    # Initialize image cleanup (runs every 30 minutes)
    try:
        cleanup = ImageCleanup(config)
        if cleanup.enabled:
            cleanup.start()
            cleanup_folders = ', '.join(cleanup.folders)
            print(f"{Fore.GREEN}Image cleanup enabled: {cleanup_folders}")
            print(f"{Fore.GREEN}Cleanup interval: {cleanup.interval_minutes} minutes, Max age: {cleanup.max_age_minutes} minutes")
        print(f"{Fore.GREEN}Ready to process images...{Style.RESET_ALL}\n")
    except Exception as e:
        logger.error(f"Failed to initialize image cleanup: {e}", exc_info=True)
        print(f"{Fore.YELLOW}Warning: Image cleanup failed to start: {e}")
        cleanup = None
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        print(f"\n{Fore.YELLOW}Shutting down...{Style.RESET_ALL}")
        logger.info("Received shutdown signal")
        watcher.stop()
        destination_watcher.stop()
        if cleanup:
            cleanup.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start watchers
    try:
        watcher.start()
        destination_watcher.start()
        
        # Keep main thread alive
        print(f"{Fore.CYAN}Application running. Press Ctrl+C to stop.{Style.RESET_ALL}\n")
        
        # Wait for processing threads
        for thread in watcher.processing_threads + destination_watcher.processing_threads:
            thread.join()
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Interrupted by user{Style.RESET_ALL}")
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"{Fore.RED}Fatal error: {e}{Style.RESET_ALL}")
        sys.exit(1)
    finally:
        watcher.stop()
        destination_watcher.stop()
        if cleanup:
            cleanup.stop()
        logger.info("Application stopped")


if __name__ == '__main__':
    main()

