"""
Folder Watcher Service
Monitors a folder for new subfolder creation and watches each subfolder for new images
"""

import time
import logging
import shutil
from pathlib import Path
from typing import Set, Dict, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from queue import Queue
from threading import Thread, Lock

logger = logging.getLogger(__name__)


class ChildFolderImageHandler(FileSystemEventHandler):
    """Handle file system events for new images in child folders"""
    
    def __init__(self, folder_path: str, folder_name: str, image_queue: Queue, config: Dict):
        super().__init__()
        self.folder_path = Path(folder_path)
        self.folder_name = folder_name
        self.image_queue = image_queue
        self.config = config
        self.processed_files: Set[str] = set()
        self.lock = Lock()
        self.debounce_seconds = config.get('processing', {}).get('debounce_seconds', 2)
        self.pending_files: Dict[str, float] = {}  # file_path -> timestamp
        
        # Track existing files when folder watching starts
        self._initialize_existing_files()
        
        # Start debounce thread
        self.debounce_thread = Thread(target=self._debounce_worker, daemon=True, name=f"ImageDebounce-{folder_name}")
        self.debounce_thread.start()
    
    def _initialize_existing_files(self):
        """Mark all existing image files as already processed"""
        try:
            if self.folder_path.exists():
                existing_files = set()
                for file_path in self.folder_path.iterdir():
                    if file_path.is_file() and self._is_image_file(file_path):
                        try:
                            existing_files.add(str(file_path.resolve()))
                        except (OSError, PermissionError):
                            continue
                
                with self.lock:
                    self.processed_files.update(existing_files)
                    logger.debug(f"Initialized {len(existing_files)} existing images in folder {self.folder_name}")
        except Exception as e:
            logger.warning(f"Error initializing existing files in {self.folder_name}: {e}")
    
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
    
    def on_created(self, event: FileSystemEvent):
        """Called when a new file is created"""
        if event.is_directory:
            return
        
        try:
            file_path = Path(event.src_path).resolve()
            
            # Check if it's an image file
            if not self._is_image_file(file_path):
                return
            
            # Check if it's in our watched folder
            if file_path.parent.resolve() != self.folder_path.resolve():
                return
            
            logger.debug(f"New image detected in {self.folder_name}: {file_path.name}")
            
            with self.lock:
                file_path_str = str(file_path)
                if file_path_str not in self.processed_files:
                    self.pending_files[file_path_str] = time.time()
        except Exception as e:
            logger.debug(f"Error handling on_created in {self.folder_name}: {e}")
    
    def on_moved(self, event: FileSystemEvent):
        """Called when a file is moved/renamed"""
        if event.is_directory:
            return
        
        try:
            # event.dest_path is the new location after move
            file_path = Path(event.dest_path).resolve()
            
            # Check if it's in our watched folder
            if file_path.parent.resolve() != self.folder_path.resolve():
                return
            
            # Check if it's an image file
            if not self._is_image_file(file_path):
                return
            
            logger.debug(f"Image moved to {self.folder_name}: {file_path.name}")
            
            with self.lock:
                file_path_str = str(file_path)
                if file_path_str not in self.processed_files:
                    self.pending_files[file_path_str] = time.time()
        except Exception as e:
            logger.debug(f"Error handling on_moved in {self.folder_name}: {e}")
    
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
                logger.info(f"Queueing image for processing: {file_path}")
                self.image_queue.put((self.folder_path, self.folder_name, file_path))


class FolderCreatedHandler(FileSystemEventHandler):
    """Handle file system events for folder creation"""
    
    def __init__(self, folder_queue: Queue, config: Dict, watch_folder: str):
        super().__init__()
        self.folder_queue = folder_queue
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
                logger.info(f"Queueing folder for watching: {folder_path}")
                self.folder_queue.put(folder_path)


class FolderWatcher:
    """Main folder watcher service"""
    
    def __init__(self, watch_folder: str, processor, config: Dict, processing_counter):
        self.watch_folder = Path(watch_folder)
        self.processor = processor
        self.config = config
        self.processing_counter = processing_counter
        
        if not self.watch_folder.exists():
            logger.warning(f"Watch folder does not exist, creating: {watch_folder}")
            self.watch_folder.mkdir(parents=True, exist_ok=True)
        
        # Folder queue (for new folders to start watching)
        self.folder_queue = Queue()
        
        # Image queue (for new images in watched folders)
        self.image_queue = Queue()
        
        # Event handler for main watch folder
        self.event_handler = FolderCreatedHandler(self.folder_queue, config, str(self.watch_folder))
        
        # Main observer (watches for new folders)
        self.observer = Observer()
        self.observer.schedule(
            self.event_handler,
            str(self.watch_folder),
            recursive=False  # Only watch direct children
        )
        
        # Track watched child folders: folder_path -> (observer, handler, created_time)
        self.watched_folders: Dict[str, tuple] = {}
        self.watched_folders_lock = Lock()
        
        # Folder watch timeout
        self.folder_timeout_minutes = config.get('folder_watch_timeout_minutes', 20)
        self.folder_timeout_seconds = self.folder_timeout_minutes * 60
        
        # Processing threads
        self.processing_threads = []
        self.max_concurrent = config.get('processing', {}).get('max_concurrent_jobs', 2)
        self.running = False
        
        # Folder management thread (handles timeouts and cleanup)
        self.folder_management_thread: Optional[Thread] = None
        
        # Pending items processing thread (checks for pending items that can be processed)
        self.pending_processor_thread: Optional[Thread] = None
    
    def start(self):
        """Start watching for new folders"""
        logger.info(f"Starting folder watcher on: {self.watch_folder}")
        
        # Start main observer
        self.observer.start()
        
        # Start folder watching thread
        self.running = True
        folder_thread = Thread(target=self._folder_watching_worker, daemon=True, name="FolderWatcher")
        folder_thread.start()
        
        # Start image processing threads
        for i in range(self.max_concurrent):
            thread = Thread(target=self._image_processing_worker, daemon=True, name=f"ImageProcessor-{i}")
            thread.start()
            self.processing_threads.append(thread)
        
        # Start folder management thread (timeout and cleanup)
        self.folder_management_thread = Thread(target=self._folder_management_worker, daemon=True, name="FolderManager")
        self.folder_management_thread.start()
        
        # Start pending items processor thread
        self.pending_processor_thread = Thread(target=self._pending_processor_worker, daemon=True, name="PendingProcessor")
        self.pending_processor_thread.start()
        
        logger.info("Folder watcher started successfully")
    
    def stop(self):
        """Stop watching for new folders"""
        logger.info("Stopping folder watcher...")
        self.running = False
        
        # Stop all child folder observers
        with self.watched_folders_lock:
            for folder_path, (observer, handler, _) in list(self.watched_folders.items()):
                try:
                    observer.stop()
                    observer.join(timeout=2)
                except Exception as e:
                    logger.warning(f"Error stopping observer for {folder_path}: {e}")
            self.watched_folders.clear()
        
        # Stop main observer
        self.observer.stop()
        self.observer.join()
        
        # Wait for processing threads to finish current jobs
        for thread in self.processing_threads:
            thread.join(timeout=5)
        
        if self.folder_management_thread:
            self.folder_management_thread.join(timeout=5)
        
        if self.pending_processor_thread:
            self.pending_processor_thread.join(timeout=5)
        
        logger.info("Folder watcher stopped")
    
    def _folder_watching_worker(self):
        """Worker thread that starts watching new folders"""
        while self.running:
            try:
                # Get folder from queue (with timeout to allow checking running flag)
                try:
                    folder_path = self.folder_queue.get(timeout=1)
                except:
                    continue
                
                # Start watching this folder for new images
                self._start_watching_folder(folder_path)
                
                # Mark task as done
                self.folder_queue.task_done()
            
            except Exception as e:
                logger.error(f"Error in folder watching worker: {e}", exc_info=True)
    
    def _start_watching_folder(self, folder_path: str):
        """Start watching a child folder for new images"""
        try:
            folder = Path(folder_path)
            
            if not folder.exists() or not folder.is_dir():
                logger.warning(f"Folder does not exist or is not a directory: {folder_path}")
                return
            
            folder_name = folder.name
            logger.info(f"Starting to watch folder for new images: {folder_name} ({folder_path})")
            
            # Create image handler for this folder
            image_handler = ChildFolderImageHandler(
                folder_path,
                folder_name,
                self.image_queue,
                self.config
            )
            
            # Create observer for this folder
            observer = Observer()
            observer.schedule(image_handler, str(folder), recursive=False)
            observer.start()
            
            # Track this folder
            created_time = time.time()
            with self.watched_folders_lock:
                self.watched_folders[folder_path] = (observer, image_handler, created_time)
            
            logger.info(f"Now watching folder for new images: {folder_name}")
            
        except Exception as e:
            logger.error(f"Error starting to watch folder {folder_path}: {e}", exc_info=True)
    
    def _stop_watching_folder(self, folder_path: str):
        """Stop watching a folder and delete it"""
        try:
            folder_name = None
            with self.watched_folders_lock:
                if folder_path not in self.watched_folders:
                    return
        
                observer, handler, _ = self.watched_folders[folder_path]
                folder_name = Path(folder_path).name
                del self.watched_folders[folder_path]
            
            # Stop observer
            observer.stop()
            observer.join(timeout=2)
            
            # Remove folder from processing counter
            if folder_name:
                self.processing_counter.remove_folder(folder_name)
            
            # Delete the folder
            folder = Path(folder_path)
            if folder.exists():
                try:
                    shutil.rmtree(folder)
                    logger.info(f"Deleted folder after timeout: {folder_path}")
                except Exception as e:
                    logger.warning(f"Error deleting folder {folder_path}: {e}")
            
        except Exception as e:
            logger.error(f"Error stopping watch for folder {folder_path}: {e}", exc_info=True)
    
    def _folder_management_worker(self):
        """Worker thread that manages folder timeouts and cleanup"""
        while self.running:
            try:
                time.sleep(10)  # Check every 10 seconds
                
                current_time = time.time()
                folders_to_remove = []
                
                with self.watched_folders_lock:
                    for folder_path, (observer, handler, created_time) in list(self.watched_folders.items()):
                        age_seconds = current_time - created_time
                        if age_seconds >= self.folder_timeout_seconds:
                            folders_to_remove.append(folder_path)
                
                # Stop watching and delete folders that have timed out
                for folder_path in folders_to_remove:
                    logger.info(f"Folder timeout reached: {folder_path} (age: {age_seconds/60:.1f} minutes)")
                    self._stop_watching_folder(folder_path)
            
            except Exception as e:
                logger.error(f"Error in folder management worker: {e}", exc_info=True)
    
    def _image_processing_worker(self):
        """Worker thread that processes individual images"""
        while self.running:
            try:
                # Get image from queue (with timeout to allow checking running flag)
                try:
                    folder_path, folder_name, image_path = self.image_queue.get(timeout=1)
                except:
                    # Check for pending items that can now be processed
                    self._process_pending_items()
                    continue
                
                # Check if we can process this image (threshold check)
                if not self.processing_counter.can_process(folder_name):
                    # Threshold exceeded, add to pending queue
                    logger.info(
                        f"Processing threshold exceeded for {folder_name} "
                        f"(count: {self.processing_counter.get_count(folder_name)}), "
                        f"holding image: {Path(image_path).name}"
                    )
                    self.processing_counter.add_pending(folder_name, (folder_path, folder_name, image_path))
                    self.image_queue.task_done()
                    continue
                
                # Process the image
                self._process_image(folder_path, folder_name, image_path)
                
                # Mark task as done
                self.image_queue.task_done()
                
                # Check for pending items that can now be processed
                self._process_pending_items()
            
            except Exception as e:
                logger.error(f"Error in image processing worker: {e}", exc_info=True)
    
    def _process_pending_items(self):
        """Process pending items for all folders that are below threshold"""
        # Get all folder names from watched folders
        with self.watched_folders_lock:
            folder_names = [Path(f).name for f in self.watched_folders.keys()]
        
        # Check each folder for pending items
        for folder_name in folder_names:
            while (self.processing_counter.can_process(folder_name) and 
                   self.processing_counter.has_pending(folder_name)):
                pending_item = self.processing_counter.get_pending(folder_name)
                if pending_item:
                    folder_path, folder_name, image_path = pending_item
                    logger.info(f"Processing pending image for {folder_name}: {Path(image_path).name}")
                    self._process_image(folder_path, folder_name, image_path)
    
    def _pending_processor_worker(self):
        """Worker thread that periodically checks for pending items that can be processed"""
        while self.running:
            try:
                time.sleep(2)  # Check every 2 seconds
                self._process_pending_items()
            except Exception as e:
                logger.error(f"Error in pending processor worker: {e}", exc_info=True)
    
    def _process_image(self, folder_path: Path, folder_name: str, image_path: str):
        """Process a single image: move original to output, copy renamed to Lightroom"""
        try:
            image_file = Path(image_path)
            
            if not image_file.exists():
                logger.warning(f"Image file no longer exists: {image_path}")
                return
            
            logger.info(f"Processing image: {image_file.name} from folder: {folder_name}")
            
            # Get output base folder
            output_base = Path(self.config.get('output_base_folder', '../output'))
            output_base.mkdir(parents=True, exist_ok=True)
            
            # Create output folder structure: output_base/folder_name/ (for original images)
            output_folder = output_base / folder_name
            output_folder.mkdir(parents=True, exist_ok=True)
            
            # Move original image to output folder (not in processed subfolder)
            original_destination = output_folder / image_file.name
            try:
                shutil.move(str(image_file), str(original_destination))
                logger.info(f"Moved original image: {image_file.name} -> {original_destination}")
            except Exception as e:
                logger.error(f"Error moving original image {image_file.name}: {e}", exc_info=True)
                return
            
            # Create new name with folder prefix for Lightroom
            # Use separator to reliably separate folder name from filename
            separator = self.config.get('filename_separator', '___')
            new_name = f"{folder_name}{separator}{image_file.name}"
            
            # Copy to lightroom watched folder with new name
            lightroom_watched = Path(self.config.get('lightroom_watched_folder', '../lightroom_watched'))
            lightroom_watched.mkdir(parents=True, exist_ok=True)
            lightroom_destination = lightroom_watched / new_name
            
            try:
                shutil.copy2(str(original_destination), str(lightroom_destination))
                logger.info(f"Copied to Lightroom watched: {image_file.name} -> {new_name}")
                
                # Increment processing counter (image sent to lightroom)
                count = self.processing_counter.increment(folder_name)
                logger.debug(f"Processing counter for {folder_name}: {count}/{self.processing_counter.threshold}")
                
            except Exception as e:
                logger.error(f"Error copying to Lightroom watched {image_file.name}: {e}", exc_info=True)
        
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {e}", exc_info=True)
