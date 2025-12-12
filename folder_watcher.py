"""
Folder Watcher Service
Monitors a folder for new subfolder creation and watches each subfolder for new images
"""

import time
import logging
import shutil
import os
from pathlib import Path
from typing import Set, Dict, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from queue import Queue
from threading import Thread, Lock

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
            # Handle cases like "Z:/", "Z:\", "Z:/folder", "Z:\folder"
            if len(path_str) == 2 or (len(path_str) == 3 and path_str[2] in ['/', '\\']):
                # Just "Z:" or "Z:/" or "Z:\" - return as "Z:\"
                return Path(path_str[0:2] + '\\')
            elif path_str[2:].startswith('/'):
                # "Z:/folder" -> "Z:\folder"
                normalized = path_str[0:2] + '\\' + path_str[3:].replace('/', '\\')
                return Path(normalized)
            else:
                # "Z:\folder" or "Z:folder" - normalize slashes
                normalized = path_str[0:2] + '\\' + path_str[2:].lstrip('\\/').replace('/', '\\')
                return Path(normalized)
        else:
            # Regular path, normalize slashes
            return Path(path_str.replace('/', '\\'))
    else:
        # Unix-like systems, just use Path directly
        return Path(path_str)


class ParentFolderSubfolderHandler(FileSystemEventHandler):
    """Handle file system events for subfolder creation in parent folders"""
    
    def __init__(self, parent_folder_path: str, parent_folder_name: str, folder_watcher, config: Dict):
        super().__init__()
        self.parent_folder_path = Path(parent_folder_path)
        self.parent_folder_name = parent_folder_name
        self.folder_watcher = folder_watcher
        self.config = config
        self.child_folder_found = False
        self.lock = Lock()
        
        # Start periodic check thread (fallback for missed events or delayed folder creation)
        self.check_thread = Thread(target=self._periodic_check, daemon=True, name=f"SubfolderCheck-{parent_folder_name}")
        self.check_thread.start()
    
    def _periodic_check(self):
        """Periodically check for subfolders (fallback for missed events)"""
        check_interval = 2  # Check every 2 seconds
        max_checks = 30  # Check for up to 60 seconds (30 * 2)
        checks = 0
        
        while checks < max_checks and not self.child_folder_found:
            time.sleep(check_interval)
            checks += 1
            
            with self.lock:
                if self.child_folder_found:
                    return  # Already found, stop checking
            
            try:
                if not self.parent_folder_path.exists():
                    return  # Parent folder no longer exists
                
                # Check for subfolders
                subfolders = [p for p in self.parent_folder_path.iterdir() if p.is_dir()]
                if subfolders:
                    first_subfolder = subfolders[0]
                    with self.lock:
                        if not self.child_folder_found:
                            self.child_folder_found = True
                            logger.info(f"Periodic check: Found subfolder in {self.parent_folder_name}: {first_subfolder.name}")
                            self.folder_watcher._watch_child_folder_for_images(
                                str(self.parent_folder_path),
                                self.parent_folder_name,
                                first_subfolder
                            )
                            return
            except Exception as e:
                logger.debug(f"Error in periodic subfolder check for {self.parent_folder_name}: {e}")
        
        if not self.child_folder_found:
            logger.warning(f"Periodic check: No subfolder found in {self.parent_folder_name} after {max_checks * check_interval} seconds")
    
    def on_created(self, event: FileSystemEvent):
        """Called when a new file or directory is created"""
        if not event.is_directory:
            return
        
        with self.lock:
            if self.child_folder_found:
                return  # Already found child folder, ignore
        
        try:
            folder_path = Path(event.src_path).resolve()
            
            # Check if it's a direct child of the parent folder
            if folder_path.parent.resolve() != self.parent_folder_path.resolve():
                return
            
            # Found the first child folder!
            with self.lock:
                if not self.child_folder_found:
                    self.child_folder_found = True
                    logger.info(f"First child folder detected in {self.parent_folder_name}: {folder_path.name}")
                    # Start watching this child folder for images
                    self.folder_watcher._watch_child_folder_for_images(
                        str(self.parent_folder_path),
                        self.parent_folder_name,
                        folder_path
                    )
        except Exception as e:
            logger.debug(f"Error handling subfolder creation in {self.parent_folder_name}: {e}")
    
    def on_moved(self, event: FileSystemEvent):
        """Called when a folder is moved/renamed"""
        if not event.is_directory:
            return
        
        with self.lock:
            if self.child_folder_found:
                return  # Already found child folder, ignore
        
        try:
            # event.dest_path is the new location after move
            folder_path = Path(event.dest_path).resolve()
            
            # Check if it's a direct child of the parent folder
            if folder_path.parent.resolve() != self.parent_folder_path.resolve():
                return
            
            # Found the first child folder!
            with self.lock:
                if not self.child_folder_found:
                    self.child_folder_found = True
                    logger.info(f"First child folder detected (moved) in {self.parent_folder_name}: {folder_path.name}")
                    # Start watching this child folder for images
                    self.folder_watcher._watch_child_folder_for_images(
                        str(self.parent_folder_path),
                        self.parent_folder_name,
                        folder_path
                    )
        except Exception as e:
            logger.debug(f"Error handling subfolder move in {self.parent_folder_name}: {e}")


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
        """Process all existing image files when starting to watch a folder"""
        try:
            if self.folder_path.exists():
                existing_files = []
                
                for file_path in self.folder_path.iterdir():
                    if file_path.is_file() and self._is_image_file(file_path):
                        try:
                            file_path_str = str(file_path.resolve())
                            existing_files.append(file_path_str)
                            logger.debug(f"Found existing image in {self.folder_name}: {file_path.name}")
                            
                            # Mark as processed to avoid duplicate processing from file system events
                            with self.lock:
                                self.processed_files.add(file_path_str)
                                
                        except (OSError, PermissionError) as e:
                            logger.debug(f"Could not process file {file_path}: {e}")
                            continue
                
                # Queue all existing files for processing
                for file_path_str in existing_files:
                    logger.info(f"Queueing existing image for processing: {file_path_str}")
                    logger.debug(f"Queue size before put: {self.image_queue.qsize()}")
                    try:
                        self.image_queue.put((self.folder_path, self.folder_name, file_path_str))
                        logger.info(f"Successfully queued image: {Path(file_path_str).name} (queue size: {self.image_queue.qsize()})")
                    except Exception as e:
                        logger.error(f"Error queueing image {file_path_str}: {e}", exc_info=True)
                
                if existing_files:
                    logger.info(f"Found {len(existing_files)} existing image(s) in {self.folder_name}, queued for processing (final queue size: {self.image_queue.qsize()})")
                else:
                    logger.info(f"No existing images found in {self.folder_name}")
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
            
            logger.debug(f"on_created event in {self.folder_name}: {file_path.name}")
            
            # Check if it's an image file
            if not self._is_image_file(file_path):
                logger.debug(f"File {file_path.name} is not an image file, ignoring")
                return
            
            # Check if it's in our watched folder
            if file_path.parent.resolve() != self.folder_path.resolve():
                logger.debug(f"File {file_path.name} not in watched folder, ignoring")
                return
            
            logger.info(f"New image detected in {self.folder_name}: {file_path.name}")
            
            with self.lock:
                file_path_str = str(file_path.resolve())
                # Check if already processed (from initialization or previous event)
                if file_path_str not in self.processed_files:
                    logger.info(f"Adding image to pending queue: {file_path.name}")
                    self.pending_files[file_path_str] = time.time()
                else:
                    logger.debug(f"Image {file_path.name} already processed, skipping")
        except Exception as e:
            logger.error(f"Error handling on_created in {self.folder_name}: {e}", exc_info=True)
    
    def on_moved(self, event: FileSystemEvent):
        """Called when a file is moved/renamed"""
        if event.is_directory:
            return
        
        try:
            # event.dest_path is the new location after move
            file_path = Path(event.dest_path).resolve()
            
            logger.debug(f"on_moved event in {self.folder_name}: {file_path.name}, parent: {file_path.parent.resolve()}, watched: {self.folder_path.resolve()}")
            
            # Check if it's in our watched folder
            if file_path.parent.resolve() != self.folder_path.resolve():
                logger.debug(f"File {file_path.name} not in watched folder, ignoring")
                return
            
            # Check if it's an image file
            if not self._is_image_file(file_path):
                logger.debug(f"File {file_path.name} is not an image file, ignoring")
                return
            
            logger.info(f"Image moved/pasted to {self.folder_name}: {file_path.name}")
            
            with self.lock:
                file_path_str = str(file_path.resolve())
                # Check if already processed (from initialization or previous event)
                if file_path_str not in self.processed_files:
                    logger.info(f"Adding image to pending queue: {file_path.name}")
                    self.pending_files[file_path_str] = time.time()
                else:
                    logger.debug(f"Image {file_path.name} already processed, skipping")
        except Exception as e:
            logger.error(f"Error handling on_moved in {self.folder_name}: {e}", exc_info=True)
    
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
    
    def _start_watching_folder(self, parent_folder_path: str):
        """Start watching a parent folder for the first subfolder created, then watch that subfolder for images"""
        try:
            logger.info(f"_start_watching_folder called with: {parent_folder_path}")
            parent_folder = Path(parent_folder_path)
            
            if not parent_folder.exists() or not parent_folder.is_dir():
                logger.warning(f"Parent folder does not exist or is not a directory: {parent_folder_path}")
                return
            
            parent_folder_name = parent_folder.name
            logger.info(f"Starting to watch parent folder for first subfolder: {parent_folder_name}")
            logger.info(f"Parent folder path: {parent_folder}")
            logger.info(f"Parent folder exists: {parent_folder.exists()}, is_dir: {parent_folder.is_dir()}")
            
            # Check if there's already a subfolder (with retry for pasted folders)
            logger.info(f"Checking for existing subfolders in {parent_folder_name}")
            existing_subfolders = []
            for attempt in range(3):  # Try 3 times with delays
                try:
                    existing_subfolders = [p for p in parent_folder.iterdir() if p.is_dir()]
                    logger.info(f"Attempt {attempt + 1}: Found {len(existing_subfolders)} subfolder(s) in {parent_folder_name}")
                    if existing_subfolders:
                        break
                    if attempt < 2:  # Don't sleep on last attempt
                        time.sleep(0.5)  # Wait 500ms before retry
                except (OSError, PermissionError) as e:
                    logger.warning(f"Error checking for subfolders (attempt {attempt + 1}): {e}")
                    if attempt < 2:
                        time.sleep(0.5)
            
            if existing_subfolders:
                # Use the first existing subfolder
                first_subfolder = existing_subfolders[0]
                logger.info(f"Found existing subfolder in {parent_folder_name}: {first_subfolder.name}")
                logger.info(f"Subfolder path: {first_subfolder}")
                logger.info(f"Calling _watch_child_folder_for_images for {parent_folder_name}")
                self._watch_child_folder_for_images(parent_folder_path, parent_folder_name, first_subfolder)
                logger.info(f"Returning from _start_watching_folder after watching child folder")
                return
            else:
                logger.info(f"No existing subfolders found in {parent_folder_name}, will watch for creation")
        
            # No subfolder exists yet, watch for the first one to be created
            logger.info(f"Creating subfolder handler for {parent_folder_name}")
            # Create handler to watch for subfolder creation
            subfolder_handler = ParentFolderSubfolderHandler(
                parent_folder_path,
                parent_folder_name,
                self,
                self.config
            )
            logger.info(f"Subfolder handler created for {parent_folder_name}")
            
            # Create observer for the parent folder (to detect subfolder creation)
            observer = Observer()
            observer.schedule(subfolder_handler, str(parent_folder), recursive=False)
            observer.start()
            logger.info(f"Observer started for {parent_folder_name}")
            
            # Track using parent folder path
            created_time = time.time()
            with self.watched_folders_lock:
                self.watched_folders[parent_folder_path] = (observer, subfolder_handler, created_time)
            
            logger.info(f"Now watching parent folder {parent_folder_name} for first subfolder creation")
        
        except Exception as e:
            logger.error(f"Error in _start_watching_folder for {parent_folder_path}: {e}", exc_info=True)
            
        except Exception as e:
            logger.error(f"Error starting to watch folder {parent_folder_path}: {e}", exc_info=True)
    
    def _watch_child_folder_for_images(self, parent_folder_path: str, parent_folder_name: str, child_folder_path: Path):
        """Watch the child folder for images, using parent folder name for processing"""
        try:
            if not child_folder_path.exists() or not child_folder_path.is_dir():
                logger.warning(f"Child folder does not exist or is not a directory: {child_folder_path}")
                return
            
            logger.info(f"Starting to watch child folder '{child_folder_path.name}' for images in parent: {parent_folder_name}")
            logger.info(f"Child folder path: {child_folder_path}")
            logger.info(f"Child folder exists: {child_folder_path.exists()}, is_dir: {child_folder_path.is_dir()}")
            
            # Stop any existing observer for this parent folder (if watching for subfolder creation)
            with self.watched_folders_lock:
                if parent_folder_path in self.watched_folders:
                    old_observer, old_handler, _ = self.watched_folders[parent_folder_path]
                    try:
                        old_observer.stop()
                        old_observer.join(timeout=1)
                        logger.debug(f"Stopped old observer for {parent_folder_name}")
                    except Exception as e:
                        logger.debug(f"Error stopping old observer: {e}")
            
            # Create image handler for the child folder, but use parent folder name
            logger.info(f"Creating image handler for child folder: {child_folder_path}")
            image_handler = ChildFolderImageHandler(
                str(child_folder_path),
                parent_folder_name,  # Use parent folder name, not child folder name
                self.image_queue,
                self.config
            )
            logger.info(f"Image handler created successfully for {parent_folder_name}")
            
            # Create observer for the child folder
            observer = Observer()
            observer.schedule(image_handler, str(child_folder_path), recursive=False)
            observer.start()
            
            # Track using parent folder path (for cleanup/deletion)
            created_time = time.time()
            with self.watched_folders_lock:
                self.watched_folders[parent_folder_path] = (observer, image_handler, created_time)
            
            logger.info(f"Now watching child folder '{child_folder_path.name}' for images (using parent name: {parent_folder_name})")
            
        except Exception as e:
            logger.error(f"Error watching child folder {child_folder_path}: {e}", exc_info=True)
    
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
        logger.debug("Image processing worker started")
        while self.running:
            try:
                # Get image from queue (with timeout to allow checking running flag)
                try:
                    folder_path, folder_name, image_path = self.image_queue.get(timeout=1)
                    logger.info(f"Got image from queue: {Path(image_path).name} for folder: {folder_name} (queue size: {self.image_queue.qsize()})")
                except Exception as queue_exception:
                    # Queue timeout (expected) or other exception
                    if "Empty" not in str(type(queue_exception).__name__):
                        logger.debug(f"Queue get exception: {type(queue_exception).__name__}: {queue_exception}")
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
                logger.debug(f"About to process image: {Path(image_path).name} for folder: {folder_name}")
                self._process_image(folder_path, folder_name, image_path)
                logger.debug(f"Finished processing image: {Path(image_path).name} for folder: {folder_name}")
                
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
    
    def _process_image(self, folder_path, folder_name: str, image_path: str):
        """Process a single image: move original to output, copy renamed to Lightroom"""
        try:
            # Ensure folder_path is a Path object (it might be passed as Path or str)
            if isinstance(folder_path, str):
                folder_path = Path(folder_path)
            elif not isinstance(folder_path, Path):
                logger.error(f"Invalid folder_path type: {type(folder_path)}")
                return
            
            image_file = Path(image_path)
            
            if not image_file.exists():
                logger.warning(f"Image file no longer exists: {image_path}")
                return
            
            logger.info(f"Processing image: {image_file.name} from folder: {folder_name}")
            logger.debug(f"Image path: {image_path}, Folder path: {folder_path}")
            
            # Get output base folder (normalize Windows paths)
            output_base_str = self.config.get('output_base_folder', '../output')
            output_base = normalize_path(output_base_str)
            
            logger.debug(f"Output base folder: {output_base} (normalized from: {output_base_str})")
            
            # Check if path is a root drive (e.g., "Z:\") - skip mkdir on root, but allow subdirectories
            output_base_path_str = str(output_base)
            is_root_drive = os.name == 'nt' and len(output_base_path_str) == 3 and output_base_path_str[1] == ':' and output_base_path_str[2] == '\\'
            
            if not is_root_drive:
                # Not a root drive, try to create the base folder
                try:
                    output_base.mkdir(parents=True, exist_ok=True)
                    logger.debug(f"Output base folder exists or created: {output_base}")
                except (OSError, PermissionError) as e:
                    logger.error(f"Cannot create output folder {output_base}: {e}")
                    logger.error(f"Original path string: {output_base_str}")
                    return
            else:
                # Root drive - verify it exists/accessible by trying to list it
                # Don't try to create it (can't create root drive)
                try:
                    # Try to access the root drive by checking if we can get its parent (which should be the drive itself)
                    # Or try to list it
                    list(output_base.iterdir())
                    logger.debug(f"Root drive {output_base} is accessible")
                except (OSError, PermissionError) as e:
                    logger.error(f"Root drive {output_base} is not accessible: {e}")
                    logger.error(f"Original path string: {output_base_str}")
                    logger.error(f"Please ensure the drive is mapped and accessible, or use a subdirectory like 'Z:/output'")
                    return
            
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
