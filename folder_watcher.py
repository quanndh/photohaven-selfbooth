"""
Folder Watcher Service
Monitors a folder for new subfolder creation and triggers image processing
"""

import time
import logging
from pathlib import Path
from typing import Set, Dict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from queue import Queue
from threading import Thread, Lock
from image_processor import ImageProcessor

logger = logging.getLogger(__name__)


class FolderCreatedHandler(FileSystemEventHandler):
    """Handle file system events for folder creation"""
    
    def __init__(self, processor_queue: Queue, config: Dict, watch_folder: str):
        super().__init__()
        self.processor_queue = processor_queue
        self.config = config
        self.watch_folder = watch_folder
        self.pending_folders: Dict[str, float] = {}  # folder_path -> timestamp
        self.processed_folders: Set[str] = set()
        self.lock = Lock()
        self.debounce_seconds = config.get('processing', {}).get('debounce_seconds', 2)
        
        # Track existing folders when app starts (to avoid processing old folders)
        self._initialize_existing_folders()
        
        # Start debounce thread
        self.debounce_thread = Thread(target=self._debounce_worker, daemon=True)
        self.debounce_thread.start()
        
        # Start periodic check thread (fallback for missed events)
        self.check_thread = Thread(target=self._periodic_check, daemon=True)
        self.check_thread.start()
    
    def _initialize_existing_folders(self):
        """Mark all existing child folders as already processed to avoid re-processing"""
        try:
            watch_path = Path(self.watch_folder).resolve()
            if watch_path.exists():
                existing_folders = set()
                for p in watch_path.iterdir():
                    # Only mark direct children as processed, not nested folders
                    if p.is_dir() and p.parent.resolve() == watch_path:
                        try:
                            existing_folders.add(str(p.resolve()))
                        except (OSError, PermissionError):
                            continue
                
                with self.lock:
                    # Mark all existing child folders as processed
                    self.processed_folders.update(existing_folders)
                    logger.info(f"Initialized: {len(existing_folders)} existing child folders will be ignored")
        except Exception as e:
            logger.warning(f"Error initializing existing folders: {e}")
    
    def on_created(self, event: FileSystemEvent):
        """Called when a file or directory is created"""
        logger.debug(f"on_created event: {event.src_path}, is_directory: {event.is_directory}")
        if event.is_directory:
            try:
                # Resolve the path to handle symlinks and relative paths
                folder_path_obj = Path(event.src_path).resolve()
                folder_path = str(folder_path_obj)
                watch_path = Path(self.watch_folder).resolve()
                
                # Only process if it's a direct child of the watched folder (not nested, not the watched folder itself)
                if folder_path_obj.parent.resolve() == watch_path:
                    logger.info(f"New child folder detected (created): {folder_path}")
                    
                    with self.lock:
                        # Check if already processed or pending
                        if folder_path not in self.processed_folders and folder_path not in self.pending_folders:
                            self.pending_folders[folder_path] = time.time()
                        else:
                            logger.debug(f"Folder already processed or pending: {folder_path}")
            except Exception as e:
                logger.debug(f"Error handling on_created: {e}")
    
    def on_moved(self, event: FileSystemEvent):
        """Called when a file or directory is moved/renamed"""
        logger.debug(f"on_moved event: {event.src_path} -> {event.dest_path}, is_directory: {event.is_directory}")
        if event.is_directory:
            try:
                # event.dest_path is the new location after move/paste
                folder_path_obj = Path(event.dest_path).resolve()
                folder_path = str(folder_path_obj)
                watch_path = Path(self.watch_folder).resolve()
                
                # Only process if it's a direct child of the watched folder (not nested, not the watched folder itself)
                if folder_path_obj.parent.resolve() == watch_path:
                    logger.info(f"New child folder detected (moved/pasted): {folder_path}")
                    
                    with self.lock:
                        # Check if already processed or pending
                        if folder_path not in self.processed_folders and folder_path not in self.pending_folders:
                            self.pending_folders[folder_path] = time.time()
                        else:
                            logger.debug(f"Folder already processed or pending: {folder_path}")
            except Exception as e:
                logger.debug(f"Error handling on_moved: {e}")
    
    def on_modified(self, event: FileSystemEvent):
        """Called when a directory is modified"""
        # Only check for new folders if the watched folder itself was modified
        # Ignore modifications to child folders (like deletions)
        try:
            watch_path = Path(self.watch_folder).resolve()
            watch_path_str = str(watch_path)
            
            # Only react if the watched folder itself was modified (not a child)
            if event.is_directory:
                try:
                    event_path = Path(event.src_path).resolve()
                    # Only trigger if the modified path is exactly the watched folder
                    if str(event_path) == watch_path_str:
                        logger.debug(f"Watched folder modified: {event.src_path}")
                        # Check for new subdirectories after a short delay
                        # Use a thread to avoid blocking
                        Thread(target=self._delayed_check, daemon=True).start()
                except (OSError, ValueError):
                    # If we can't resolve the path, check string match
                    if event.src_path == self.watch_folder or event.src_path == watch_path_str:
                        logger.debug(f"Watched folder modified (unresolved): {event.src_path}")
                        Thread(target=self._delayed_check, daemon=True).start()
        except Exception as e:
            logger.debug(f"Error in on_modified: {e}")
    
    def _delayed_check(self):
        """Delayed check for new folders (allows paste operation to complete)"""
        time.sleep(1.0)  # Wait 1 second for paste to complete
        self._check_for_new_folders()
    
    def _check_for_new_folders(self):
        """Manually check for new folders in the watched directory"""
        try:
            watch_path = Path(self.watch_folder).resolve()
            if not watch_path.exists():
                return
            
            # Get all current child folders (direct children only, not nested)
            current_folders = set()
            for p in watch_path.iterdir():
                # Only check direct children, not nested folders
                if p.is_dir() and p.parent.resolve() == watch_path:
                    try:
                        resolved_path = str(p.resolve())
                        current_folders.add(resolved_path)
                    except (OSError, PermissionError) as e:
                        logger.debug(f"Could not resolve path {p}: {e}")
                        continue
            
            with self.lock:
                # Find folders that are NEW (exist now but weren't in processed_folders)
                # This means they were just created/pasted
                new_folders = current_folders - self.processed_folders
                # Also exclude folders that are already pending
                new_folders = {f for f in new_folders if f not in self.pending_folders}
                
                if new_folders:
                    logger.info(f"Found {len(new_folders)} new child folder(s) in watched directory")
                    for folder_path in new_folders:
                        logger.info(f"New child folder detected: {folder_path}")
                        self.pending_folders[folder_path] = time.time()
        except Exception as e:
            logger.error(f"Error checking for new folders: {e}", exc_info=True)
    
    def _periodic_check(self):
        """Periodically check for new folders (fallback for missed events)"""
        while True:
            time.sleep(3)  # Check every 3 seconds (more frequent for better detection)
            self._check_for_new_folders()
    
    def on_any_event(self, event: FileSystemEvent):
        """Log all events for debugging"""
        logger.debug(f"File system event: {event.event_type} - {event.src_path} (is_directory: {event.is_directory})")
    
    def _debounce_worker(self):
        """Worker thread that processes folders after debounce period"""
        while True:
            time.sleep(0.5)  # Check every 500ms
            
            current_time = time.time()
            folders_to_process = []
            
            with self.lock:
                # Check which folders are ready to process
                for folder_path, timestamp in list(self.pending_folders.items()):
                    if current_time - timestamp >= self.debounce_seconds:
                        if folder_path not in self.processed_folders:
                            folders_to_process.append(folder_path)
                            self.processed_folders.add(folder_path)
                        del self.pending_folders[folder_path]
            
            # Queue folders for processing
            for folder_path in folders_to_process:
                logger.info(f"Queueing folder for processing: {folder_path}")
                self.processor_queue.put(folder_path)


class FolderWatcher:
    """Main folder watcher service"""
    
    def __init__(self, watch_folder: str, processor: ImageProcessor, config: Dict):
        self.watch_folder = Path(watch_folder)
        self.processor = processor
        self.config = config
        
        if not self.watch_folder.exists():
            logger.warning(f"Watch folder does not exist, creating: {watch_folder}")
            self.watch_folder.mkdir(parents=True, exist_ok=True)
        
        # Processing queue
        self.processor_queue = Queue()
        
        # Event handler
        self.event_handler = FolderCreatedHandler(self.processor_queue, config, str(self.watch_folder))
        
        # Observer
        self.observer = Observer()
        # Watch the folder with recursive=False to only watch direct children
        # But we need to handle events properly - watchdog may drop some events
        # so we'll also watch for modified events on the parent
        self.observer.schedule(
            self.event_handler,
            str(self.watch_folder),
            recursive=False  # Only watch direct children
        )
        
        # Processing threads
        self.processing_threads = []
        self.max_concurrent = config.get('processing', {}).get('max_concurrent_jobs', 2)
        self.running = False
    
    def start(self):
        """Start watching for new folders"""
        logger.info(f"Starting folder watcher on: {self.watch_folder}")
        
        # Start observer
        self.observer.start()
        
        # Start processing threads
        self.running = True
        for i in range(self.max_concurrent):
            thread = Thread(target=self._processing_worker, daemon=True, name=f"Processor-{i}")
            thread.start()
            self.processing_threads.append(thread)
        
        logger.info("Folder watcher started successfully")
    
    def stop(self):
        """Stop watching for new folders"""
        logger.info("Stopping folder watcher...")
        self.running = False
        
        # Stop observer
        self.observer.stop()
        self.observer.join()
        
        # Wait for processing threads to finish current jobs
        for thread in self.processing_threads:
            thread.join(timeout=5)
        
        logger.info("Folder watcher stopped")
    
    def _processing_worker(self):
        """Worker thread that processes folders from the queue"""
        while self.running:
            try:
                # Get folder from queue (with timeout to allow checking running flag)
                try:
                    folder_path = self.processor_queue.get(timeout=1)
                except:
                    continue
                
                # Process the folder
                self._process_folder(folder_path)
                
                # Mark task as done
                self.processor_queue.task_done()
            
            except Exception as e:
                logger.error(f"Error in processing worker: {e}", exc_info=True)
    
    def _process_folder(self, folder_path: str):
        """Process all images in a folder"""
        folder = Path(folder_path)
        
        if not folder.exists() or not folder.is_dir():
            logger.warning(f"Folder does not exist or is not a directory: {folder_path}")
            return
        
        logger.info(f"Processing folder: {folder_path}")
        
        # Get all supported image files
        image_files = self._get_image_files(folder)
        
        if not image_files:
            logger.info(f"No supported image files found in: {folder_path}")
            return
        
        # Create output folder
        output_folder = folder / self.config.get('output_folder', 'processed')
        output_folder.mkdir(exist_ok=True)
        
        # Process each image
        processed_count = 0
        failed_count = 0
        
        for image_file in image_files:
            try:
                # Generate output filename
                output_filename = image_file.stem
                output_format = self.config.get('output_format', 'tiff').lower()
                if output_format == 'jpg' or output_format == 'jpeg':
                    output_filename += '.jpg'
                else:
                    output_filename += '.tif'
                
                output_path = output_folder / output_filename
                
                # Process image
                success = self.processor.process_image(str(image_file), str(output_path))
                
                if success:
                    processed_count += 1
                    logger.info(f"Processed: {image_file.name} -> {output_path.name}")
                else:
                    failed_count += 1
                    logger.error(f"Failed to process: {image_file.name}")
                    
                    # Retry if configured
                    if self.config.get('processing', {}).get('retry_failed', True):
                        max_retries = self.config.get('processing', {}).get('max_retries', 3)
                        for retry in range(max_retries):
                            time.sleep(1)  # Wait before retry
                            logger.info(f"Retrying {image_file.name} (attempt {retry + 1}/{max_retries})")
                            if self.processor.process_image(str(image_file), str(output_path)):
                                processed_count += 1
                                failed_count -= 1
                                logger.info(f"Successfully processed on retry: {image_file.name}")
                                break
            
            except Exception as e:
                failed_count += 1
                logger.error(f"Error processing {image_file}: {e}", exc_info=True)
        
        logger.info(
            f"Folder processing complete: {folder_path} - "
            f"Processed: {processed_count}, Failed: {failed_count}"
        )
    
    def _get_image_files(self, folder: Path) -> list:
        """Get all supported image files from folder"""
        image_files = []
        
        # Get all supported extensions
        raw_extensions = [
            ext.lower() for ext in self.config['supported_extensions']['raw']
        ]
        standard_extensions = [
            ext.lower() for ext in self.config['supported_extensions']['standard']
        ]
        all_extensions = raw_extensions + standard_extensions
        
        # Find all image files
        for ext in all_extensions:
            # Case-insensitive search
            image_files.extend(folder.glob(f"*{ext}"))
            image_files.extend(folder.glob(f"*{ext.upper()}"))
        
        # Remove duplicates and sort
        image_files = sorted(set(image_files))
        
        return image_files

