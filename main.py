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
from image_processor import ImageProcessor
from folder_watcher import FolderWatcher

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
        required_keys = ['watch_folder', 'preset_path']
        for key in required_keys:
            if key not in config:
                print(f"{Fore.RED}Error: Missing required configuration: {key}")
                sys.exit(1)
        
        # Resolve paths (support both absolute and relative)
        if 'watch_folder' in config:
            config['watch_folder'] = str(resolve_path(config['watch_folder'], config_dir))
        
        if 'preset_path' in config:
            config['preset_path'] = str(resolve_path(config['preset_path'], config_dir))
        
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
    
    # Validate preset file
    preset_path = Path(config['preset_path'])
    if not preset_path.exists():
        logger.error(f"Preset file not found: {preset_path}")
        print(f"{Fore.RED}Error: Preset file not found: {preset_path}")
        sys.exit(1)
    
    # Validate watch folder
    watch_folder = Path(config['watch_folder'])
    if not watch_folder.exists():
        logger.info(f"Creating watch folder: {watch_folder}")
        watch_folder.mkdir(parents=True, exist_ok=True)
    
    # Initialize image processor
    try:
        print(f"{Fore.GREEN}Loading preset: {preset_path}")
        processor = ImageProcessor(str(preset_path), config)
        logger.info(f"Preset loaded successfully: {preset_path}")
        print(f"{Fore.GREEN}Preset loaded successfully{Style.RESET_ALL}\n")
    except Exception as e:
        logger.error(f"Failed to initialize image processor: {e}", exc_info=True)
        print(f"{Fore.RED}Error: Failed to load preset: {e}")
        sys.exit(1)
    
    # Initialize folder watcher
    try:
        watcher = FolderWatcher(str(watch_folder), processor, config)
        print(f"{Fore.GREEN}Watching folder: {watch_folder}")
        print(f"{Fore.GREEN}Output format: {config.get('output_format', 'tiff')}")
        print(f"{Fore.GREEN}Ready to process images...{Style.RESET_ALL}\n")
    except Exception as e:
        logger.error(f"Failed to initialize folder watcher: {e}", exc_info=True)
        print(f"{Fore.RED}Error: Failed to start folder watcher: {e}")
        sys.exit(1)
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        print(f"\n{Fore.YELLOW}Shutting down...{Style.RESET_ALL}")
        logger.info("Received shutdown signal")
        watcher.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start watcher
    try:
        watcher.start()
        
        # Keep main thread alive
        print(f"{Fore.CYAN}Application running. Press Ctrl+C to stop.{Style.RESET_ALL}\n")
        
        # Wait for processing threads
        for thread in watcher.processing_threads:
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
        logger.info("Application stopped")


if __name__ == '__main__':
    main()

