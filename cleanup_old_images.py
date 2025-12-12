"""
Cleanup Old Images
Deletes files and folders older than specified age from configured folders
"""

import time
import logging
import shutil
import os
from pathlib import Path
from typing import List
from threading import Thread, Event

logger = logging.getLogger(__name__)


def normalize_path(path_str: str) -> Path:
    """
    Normalize a path string to handle Windows drive letters and UNC paths correctly.
    Handles: Z:/, Z:\\, \\\\server\\share, //server/share, etc.
    """
    if not path_str:
        return Path('.')
    
    # Normalize forward/backward slashes for Windows
    # Replace forward slashes with backslashes on Windows, but preserve UNC paths
    if os.name == 'nt':  # Windows
        # Handle UNC paths (\\server\share or //server/share)
        if path_str.startswith('\\\\') or path_str.startswith('//'):
            # Keep UNC format, normalize slashes
            normalized = path_str.replace('/', '\\')
            return Path(normalized)
        # Handle drive letters (Z:/ or Z:\)
        elif len(path_str) >= 2 and path_str[1] == ':':
            # Normalize to use backslash after drive letter
            if path_str[2:].startswith('/'):
                normalized = path_str[0:2] + path_str[2:].replace('/', '\\')
            else:
                normalized = path_str.replace('/', '\\')
            return Path(normalized)
        else:
            # Regular path, normalize slashes
            return Path(path_str.replace('/', '\\'))
    else:
        # Unix-like systems, just use Path directly
        return Path(path_str)


class ImageCleanup:
    """Cleanup old images from specified folders"""
    
    def __init__(self, config: dict):
        self.config = config
        self.cleanup_config = config.get('cleanup', {})
        self.enabled = self.cleanup_config.get('enabled', False)
        self.folders = self.cleanup_config.get('folders', [])
        self.max_age_minutes = self.cleanup_config.get('max_age_minutes', 30)
        self.interval_minutes = self.cleanup_config.get('interval_minutes', 30)
        self.running = False
        self.stop_event = Event()
        self.cleanup_thread = None
        
        if self.enabled and self.folders:
            logger.info(f"Cleanup enabled: checking {len(self.folders)} folder(s) every {self.interval_minutes} minutes")
            logger.info(f"Deleting files and folders older than {self.max_age_minutes} minutes")
    
    def start(self):
        """Start the cleanup thread"""
        if not self.enabled or not self.folders:
            logger.debug("Image cleanup disabled or no folders configured")
            return
        
        self.running = True
        self.stop_event.clear()
        self.cleanup_thread = Thread(target=self._cleanup_worker, daemon=True, name="ImageCleanup")
        self.cleanup_thread.start()
        logger.info("Image cleanup thread started")
    
    def stop(self):
        """Stop the cleanup thread"""
        if self.running:
            logger.info("Stopping image cleanup thread...")
            self.running = False
            self.stop_event.set()
            if self.cleanup_thread:
                self.cleanup_thread.join(timeout=5)
            logger.info("Image cleanup thread stopped")
    
    def _cleanup_worker(self):
        """Worker thread that runs cleanup periodically"""
        # Run cleanup immediately on start
        self._run_cleanup()
        
        # Then run at intervals
        while self.running:
            # Wait for interval (check stop_event periodically)
            wait_seconds = self.interval_minutes * 60
            if self.stop_event.wait(timeout=wait_seconds):
                # Stop event was set, exit
                break
            
            # Run cleanup
            if self.running:
                self._run_cleanup()
    
    def _run_cleanup(self):
        """Run cleanup on all configured folders"""
        logger.info(f"Starting cleanup (max age: {self.max_age_minutes} minutes)")
        
        total_deleted = 0
        total_errors = 0
        
        for folder_path_str in self.folders:
            try:
                # Normalize path to handle Windows drive letters and UNC paths
                folder_path = normalize_path(folder_path_str)
                
                if not folder_path.exists():
                    logger.warning(f"Cleanup folder does not exist: {folder_path}")
                    continue
                
                if not folder_path.is_dir():
                    logger.warning(f"Cleanup path is not a directory: {folder_path}")
                    continue
                
                deleted_count = self._cleanup_folder(folder_path)
                total_deleted += deleted_count
                
            except Exception as e:
                logger.error(f"Error cleaning up folder {folder_path_str}: {e}", exc_info=True)
                total_errors += 1
        
        logger.info(f"Cleanup complete: Deleted {total_deleted} item(s), Errors: {total_errors}")
    
    def _cleanup_folder(self, folder: Path) -> int:
        """Cleanup a single folder recursively, return number of items (files and folders) deleted"""
        deleted_count = 0
        current_time = time.time()
        max_age_seconds = self.max_age_minutes * 60
        
        try:
            # Collect all items (files and folders) to delete
            items_to_delete = []
            
            # Recursively iterate through all items in folder and subdirectories
            for item_path in folder.rglob('*'):
                try:
                    # Get item age (use modification time)
                    item_age = current_time - item_path.stat().st_mtime
                    
                    if item_age > max_age_seconds:
                        items_to_delete.append((item_path, item_age, item_path.is_dir()))
                
                except (OSError, PermissionError) as e:
                    logger.debug(f"Could not check age of {item_path}: {e}")
                    continue
            
            # Sort by depth (deepest first) and folders last, so we delete files before folders
            items_to_delete.sort(key=lambda x: (len(x[0].parts), x[2]), reverse=True)
            
            # Delete items (files first, then folders)
            for item_path, item_age, is_dir in items_to_delete:
                try:
                    if is_dir:
                        # Delete folder and all its contents
                        if item_path.exists():
                            shutil.rmtree(item_path)
                            deleted_count += 1
                            logger.debug(f"Deleted old folder: {item_path.relative_to(folder)} (age: {item_age/60:.1f} minutes)")
                    else:
                        # Delete file
                        if item_path.exists():
                            item_path.unlink()
                            deleted_count += 1
                            logger.debug(f"Deleted old file: {item_path.relative_to(folder)} (age: {item_age/60:.1f} minutes)")
                
                except (OSError, PermissionError) as e:
                    logger.warning(f"Could not delete {item_path}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error cleaning up folder {folder}: {e}", exc_info=True)
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {folder}: Deleted {deleted_count} old item(s)")
        
        return deleted_count
    
    def _get_image_extensions(self) -> List[str]:
        """Get list of supported image extensions"""
        extensions = []
        
        raw_extensions = self.config.get('supported_extensions', {}).get('raw', [])
        standard_extensions = self.config.get('supported_extensions', {}).get('standard', [])
        
        for ext_list in [raw_extensions, standard_extensions]:
            for ext in ext_list:
                ext_lower = ext.lower()
                if ext_lower not in extensions:
                    extensions.append(ext_lower)
        
        return extensions

