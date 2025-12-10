"""
Cleanup Old Images
Deletes images older than specified age from configured folders
"""

import time
import logging
from pathlib import Path
from typing import List
from threading import Thread, Event

logger = logging.getLogger(__name__)


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
            logger.info(f"Image cleanup enabled: checking {len(self.folders)} folder(s) every {self.interval_minutes} minutes")
            logger.info(f"Deleting images older than {self.max_age_minutes} minutes")
    
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
        logger.info(f"Starting image cleanup (max age: {self.max_age_minutes} minutes)")
        
        total_deleted = 0
        total_errors = 0
        
        for folder_path_str in self.folders:
            try:
                folder_path = Path(folder_path_str)
                
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
        
        logger.info(f"Cleanup complete: Deleted {total_deleted} file(s), Errors: {total_errors}")
    
    def _cleanup_folder(self, folder: Path) -> int:
        """Cleanup a single folder recursively, return number of files deleted"""
        deleted_count = 0
        current_time = time.time()
        max_age_seconds = self.max_age_minutes * 60
        
        # Get supported image extensions
        image_extensions = self._get_image_extensions()
        
        try:
            # Recursively iterate through all files in folder and subdirectories
            for file_path in folder.rglob('*'):
                if not file_path.is_file():
                    continue
                
                # Check if it's an image file
                if file_path.suffix.lower() not in image_extensions:
                    continue
                
                # Check file age
                try:
                    file_age = current_time - file_path.stat().st_mtime
                    
                    if file_age > max_age_seconds:
                        # File is older than max age, delete it
                        file_path.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted old image: {file_path.relative_to(folder)} (age: {file_age/60:.1f} minutes)")
                
                except (OSError, PermissionError) as e:
                    logger.warning(f"Could not process file {file_path}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error cleaning up folder {folder}: {e}", exc_info=True)
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {folder}: Deleted {deleted_count} old image(s)")
        
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

