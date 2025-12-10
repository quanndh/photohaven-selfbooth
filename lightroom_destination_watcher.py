"""
Lightroom Destination Watcher
Monitors Lightroom destination folder for processed images and moves them back to original folders
"""

import time
import logging
import shutil
from pathlib import Path
from typing import Set, Dict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from queue import Queue
from threading import Thread, Lock

logger = logging.getLogger(__name__)


class LightroomDestinationHandler(FileSystemEventHandler):
    """Handle file system events in Lightroom destination folder"""
    
    def __init__(self, processor_queue: Queue, config: Dict, destination_folder: str, watch_folder: str):
        super().__init__()
        self.processor_queue = processor_queue
        self.config = config
        self.destination_folder = destination_folder
        self.watch_folder = watch_folder
        self.pending_files: Dict[str, float] = {}  # file_path -> timestamp
        self.processed_files: Set[str] = set()
        self.lock = Lock()
        self.debounce_seconds = config.get('processing', {}).get('debounce_seconds', 2)
        
        # Track existing files when app starts (to avoid processing old files)
        self._initialize_existing_files()
        
        # Start debounce thread
        self.debounce_thread = Thread(target=self._debounce_worker, daemon=True)
        self.debounce_thread.start()
    
    def _initialize_existing_files(self):
        """Mark all existing files as already processed to avoid re-processing"""
        try:
            dest_path = Path(self.destination_folder).resolve()
            if dest_path.exists():
                existing_files = set()
                for file_path in dest_path.iterdir():
                    if file_path.is_file():
                        try:
                            existing_files.add(str(file_path.resolve()))
                        except (OSError, PermissionError):
                            continue
                
                with self.lock:
                    self.processed_files.update(existing_files)
                    logger.info(f"Initialized: {len(existing_files)} existing files will be ignored")
        except Exception as e:
            logger.warning(f"Error initializing existing files: {e}")
    
    def on_created(self, event: FileSystemEvent):
        """Called when a new file is created"""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Check if it's an image file
        if not self._is_image_file(file_path):
            return
        
        logger.debug(f"New file detected: {file_path.name}")
        
        with self.lock:
            if str(file_path.resolve()) not in self.processed_files:
                self.pending_files[str(file_path.resolve())] = time.time()
    
    def on_moved(self, event: FileSystemEvent):
        """Called when a file is moved/renamed"""
        if event.is_directory:
            return
        
        # event.dest_path is the new location after move
        file_path = Path(event.dest_path)
        
        # Check if it's in our destination folder
        dest_path = Path(self.destination_folder).resolve()
        if file_path.parent.resolve() != dest_path:
            return
        
        # Check if it's an image file
        if not self._is_image_file(file_path):
            return
        
        logger.debug(f"File moved to destination: {file_path.name}")
        
        with self.lock:
            if str(file_path.resolve()) not in self.processed_files:
                self.pending_files[str(file_path.resolve())] = time.time()
    
    def _is_image_file(self, file_path: Path) -> bool:
        """Check if file is a supported image file"""
        ext = file_path.suffix.lower()
        
        raw_extensions = [
            ext.lower() for ext in self.config.get('supported_extensions', {}).get('raw', [])
        ]
        standard_extensions = [
            ext.lower() for ext in self.config.get('supported_extensions', {}).get('standard', [])
        ]
        all_extensions = raw_extensions + standard_extensions
        
        return ext in all_extensions
    
    def _debounce_worker(self):
        """Worker thread that processes files after debounce period"""
        while True:
            time.sleep(0.5)  # Check every 500ms
            
            current_time = time.time()
            files_to_process = []
            
            with self.lock:
                # Check which files are ready to process
                for file_path, timestamp in list(self.pending_files.items()):
                    if current_time - timestamp >= self.debounce_seconds:
                        if file_path not in self.processed_files:
                            files_to_process.append(file_path)
                            self.processed_files.add(file_path)
                        del self.pending_files[file_path]
            
            # Queue files for processing
            for file_path in files_to_process:
                self.processor_queue.put(file_path)


class LightroomDestinationWatcher:
    """Watch Lightroom destination folder and move processed images back to original folders"""
    
    def __init__(self, destination_folder: str, watch_folder: str, config: Dict):
        self.destination_folder = Path(destination_folder)
        self.watch_folder = Path(watch_folder)
        self.config = config
        
        if not self.destination_folder.exists():
            logger.warning(f"Lightroom destination folder does not exist, creating: {destination_folder}")
            self.destination_folder.mkdir(parents=True, exist_ok=True)
        
        # Processing queue
        self.processor_queue = Queue()
        
        # Event handler
        self.event_handler = LightroomDestinationHandler(
            self.processor_queue,
            config,
            str(self.destination_folder),
            str(self.watch_folder)
        )
        
        # Observer
        self.observer = Observer()
        self.observer.schedule(
            self.event_handler,
            str(self.destination_folder),
            recursive=False  # Only watch direct children
        )
        
        # Processing threads
        self.processing_threads = []
        self.max_concurrent = config.get('processing', {}).get('max_concurrent_jobs', 2)
        self.running = False
    
    def start(self):
        """Start watching for new files"""
        logger.info(f"Starting Lightroom destination watcher on: {self.destination_folder}")
        
        # Start observer
        self.observer.start()
        
        # Start processing threads
        self.running = True
        for i in range(self.max_concurrent):
            thread = Thread(target=self._processing_worker, daemon=True, name=f"LightroomDest-{i}")
            thread.start()
            self.processing_threads.append(thread)
        
        logger.info("Lightroom destination watcher started successfully")
    
    def stop(self):
        """Stop watching"""
        logger.info("Stopping Lightroom destination watcher...")
        self.running = False
        
        # Stop observer
        self.observer.stop()
        self.observer.join()
        
        # Wait for processing threads to finish current jobs
        for thread in self.processing_threads:
            thread.join(timeout=5)
        
        logger.info("Lightroom destination watcher stopped")
    
    def _processing_worker(self):
        """Worker thread that processes files from the queue"""
        while self.running:
            try:
                # Get file from queue (with timeout to allow checking running flag)
                try:
                    file_path = self.processor_queue.get(timeout=1)
                except:
                    continue
                
                # Process the file
                self._process_file(file_path)
                
                # Mark task as done
                self.processor_queue.task_done()
            
            except Exception as e:
                logger.error(f"Error in processing worker: {e}", exc_info=True)
    
    def _process_file(self, file_path: str):
        """Process a single file: extract folder name and move to original folder"""
        try:
            file_path_obj = Path(file_path)
            
            if not file_path_obj.exists():
                logger.warning(f"File no longer exists: {file_path}")
                return
            
            filename = file_path_obj.name
            logger.info(f"Processing file: {filename}")
            
            # Extract folder name from filename (format: folder_name_original_filename.ext)
            # Find first underscore and split
            if '_' not in filename:
                logger.warning(f"Filename does not contain folder prefix: {filename}")
                return
            
            # Split on first underscore
            parts = filename.split('_', 1)
            folder_name = parts[0]
            original_filename = parts[1]
            
            # Find the original folder in watch_folder
            original_folder = self.watch_folder / folder_name
            
            if not original_folder.exists():
                logger.warning(f"Original folder not found: {original_folder}")
                return
            
            # Create output folder in original folder
            output_folder = original_folder / self.config.get('output_folder', 'processed')
            output_folder.mkdir(parents=True, exist_ok=True)
            
            # Destination path
            destination = output_folder / original_filename
            
            # Move file to destination
            shutil.move(str(file_path_obj), str(destination))
            
            logger.info(f"Moved {filename} -> {destination}")
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}", exc_info=True)

