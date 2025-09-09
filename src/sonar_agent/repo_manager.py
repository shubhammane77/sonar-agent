#!/usr/bin/env python3
"""
Repository manager for handling file operations in Git repositories.
"""

import os
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime


class RepoManager:
    """Manages file operations in a Git repository (works with any Git platform)."""
    
    def __init__(self, repo_root: str):
        """Initialize repository manager."""
        self.repo_root = Path(repo_root).resolve()
        self.backup_dir = self.repo_root / '.sonar-agent-backups'
        
        # Ensure repo root exists
        if not self.repo_root.exists():
            raise ValueError(f"Repository root does not exist: {repo_root}")
            
        # Create backup directory if it doesn't exist
        self.backup_dir.mkdir(exist_ok=True)
    
    def read_file(self, file_path: str) -> Optional[str]:
        """Read file content from the repository."""
        full_path = self.repo_root / file_path
        
        try:
            if not full_path.exists():
                print(f"Warning: File not found: {file_path}")
                return None
                
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
                
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return None
    
    def write_file(self, file_path: str, content: str, dry_run: bool = False) -> bool:
        """Write content to a file in the repository."""
        full_path = self.repo_root / file_path
        
        if dry_run:
            print(f"[DRY RUN] Would write to: {file_path}")
            return True
            
        try:
            # Create backup if file exists
            if full_path.exists():
                self._create_backup(file_path)
            
            # Ensure parent directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the file
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            print(f"✅ Updated: {file_path}")
            return True
            
        except Exception as e:
            print(f"Error writing file {file_path}: {e}")
            return False
    
    def _create_backup(self, file_path: str) -> bool:
        """Create a backup of the file before modification."""
        try:
            full_path = self.repo_root / file_path
            if not full_path.exists():
                return True
                
            # Create timestamped backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{file_path.replace('/', '_')}_{timestamp}.backup"
            backup_path = self.backup_dir / backup_name
            
            # Ensure backup directory structure exists
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy the file
            shutil.copy2(full_path, backup_path)
            return True
            
        except Exception as e:
            print(f"Warning: Failed to create backup for {file_path}: {e}")
            return False
    
    def get_file_info(self, file_path: str) -> Optional[dict]:
        """Get information about a file."""
        full_path = self.repo_root / file_path
        
        try:
            if not full_path.exists():
                return None
                
            stat = full_path.stat()
            return {
                'path': str(full_path),
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'exists': True
            }
            
        except Exception as e:
            print(f"Error getting file info for {file_path}: {e}")
            return None
    
    def list_backups(self) -> list:
        """List all backup files created."""
        try:
            if not self.backup_dir.exists():
                return []
                
            backups = []
            for backup_file in self.backup_dir.rglob('*.backup'):
                backups.append({
                    'file': backup_file.name,
                    'path': str(backup_file),
                    'created': datetime.fromtimestamp(backup_file.stat().st_mtime)
                })
                
            return sorted(backups, key=lambda x: x['created'], reverse=True)
            
        except Exception as e:
            print(f"Error listing backups: {e}")
            return []
    
    def cleanup_old_backups(self, days: int = 7) -> int:
        """Clean up backup files older than specified days."""
        try:
            if not self.backup_dir.exists():
                return 0
                
            cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)
            removed_count = 0
            
            for backup_file in self.backup_dir.rglob('*.backup'):
                if backup_file.stat().st_mtime < cutoff_time:
                    backup_file.unlink()
                    removed_count += 1
                    
            return removed_count
            
        except Exception as e:
            print(f"Error cleaning up backups: {e}")
            return 0
    
    @staticmethod
    def get_line_from_content(file_content: str, line_number: int) -> str:
        """
        Get a specific line of code from file content.

        Args:
            file_content (str): The full text content of the file.
            line_number (int): The line number to fetch (1-indexed).

        Returns:
            str: The content of the line at the given line_number.

        Raises:
            ValueError: If the line number is out of range.
        """
        lines = file_content.splitlines()
    
        if line_number < 1 or line_number > len(lines):
            raise ValueError(f"Line number {line_number} is out of range. File has {len(lines)} lines.")
    
        return lines[line_number - 1]
