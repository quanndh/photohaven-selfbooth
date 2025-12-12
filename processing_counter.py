"""
Processing Counter
Shared counter mechanism to track number of images being processed per folder
"""

import logging
from threading import Lock
from typing import Dict
from collections import deque

logger = logging.getLogger(__name__)


class ProcessingCounter:
    """Thread-safe counter to track processing status per folder"""
    
    def __init__(self, threshold: int = 5):
        """
        Initialize processing counter
        
        Args:
            threshold: Maximum number of images that can be processed concurrently per folder
        """
        self.threshold = threshold
        self.counters: Dict[str, int] = {}  # folder_name -> counter
        self.pending_queues: Dict[str, deque] = {}  # folder_name -> queue of pending items
        self.lock = Lock()
    
    def increment(self, folder_name: str) -> int:
        """
        Increment counter for a folder (when image sent to lightroom)
        
        Args:
            folder_name: Name of the folder
            
        Returns:
            New counter value
        """
        with self.lock:
            if folder_name not in self.counters:
                self.counters[folder_name] = 0
            self.counters[folder_name] += 1
            count = self.counters[folder_name]
            logger.debug(f"Counter incremented for {folder_name}: {count}/{self.threshold}")
            return count
    
    def decrement(self, folder_name: str) -> int:
        """
        Decrement counter for a folder (when image moved to output)
        
        Args:
            folder_name: Name of the folder
            
        Returns:
            New counter value
        """
        with self.lock:
            if folder_name not in self.counters:
                logger.warning(f"Attempted to decrement counter for unknown folder: {folder_name}")
                return 0
            
            if self.counters[folder_name] > 0:
                self.counters[folder_name] -= 1
            else:
                logger.warning(f"Counter for {folder_name} was already 0, cannot decrement")
            
            count = self.counters[folder_name]
            logger.debug(f"Counter decremented for {folder_name}: {count}/{self.threshold}")
            
            # If counter dropped below threshold, process pending items
            if count < self.threshold and folder_name in self.pending_queues:
                pending_queue = self.pending_queues[folder_name]
                if pending_queue:
                    logger.info(f"Counter for {folder_name} dropped to {count}, processing {len(pending_queue)} pending image(s)")
            
            return count
    
    def can_process(self, folder_name: str) -> bool:
        """
        Check if a new image can be processed (counter < threshold)
        
        Args:
            folder_name: Name of the folder
            
        Returns:
            True if can process, False if should wait
        """
        with self.lock:
            if folder_name not in self.counters:
                self.counters[folder_name] = 0
            return self.counters[folder_name] < self.threshold
    
    def get_count(self, folder_name: str) -> int:
        """Get current counter value for a folder"""
        with self.lock:
            return self.counters.get(folder_name, 0)
    
    def add_pending(self, folder_name: str, item):
        """Add item to pending queue for a folder"""
        with self.lock:
            if folder_name not in self.pending_queues:
                self.pending_queues[folder_name] = deque()
            self.pending_queues[folder_name].append(item)
            logger.debug(f"Added pending item for {folder_name}, queue size: {len(self.pending_queues[folder_name])}")
    
    def get_pending(self, folder_name: str):
        """Get next pending item from queue (returns None if queue is empty)"""
        with self.lock:
            if folder_name not in self.pending_queues or not self.pending_queues[folder_name]:
                return None
            return self.pending_queues[folder_name].popleft()
    
    def has_pending(self, folder_name: str) -> bool:
        """Check if there are pending items for a folder"""
        with self.lock:
            return folder_name in self.pending_queues and len(self.pending_queues[folder_name]) > 0
    
    def remove_folder(self, folder_name: str):
        """Remove folder from tracking (when folder is deleted)"""
        with self.lock:
            if folder_name in self.counters:
                del self.counters[folder_name]
            if folder_name in self.pending_queues:
                pending_count = len(self.pending_queues[folder_name])
                del self.pending_queues[folder_name]
                if pending_count > 0:
                    logger.warning(f"Removed folder {folder_name} with {pending_count} pending items")

