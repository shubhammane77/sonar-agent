"""
Local database for tracking fixed code smell issues to avoid redundant processing.
"""

import sqlite3
import hashlib
import os
from datetime import datetime, timedelta
from typing import List, Optional, Set
from dataclasses import dataclass
from pathlib import Path

from sonar_client import CodeSmell


@dataclass
class FixedIssue:
    """Represents a fixed issue in the database."""
    issue_key: str
    file_path: str
    rule: str
    message: str
    branch: str
    commit_id: Optional[str]
    fixed_at: datetime
    file_hash: str  # Hash of the file content when fixed


class IssueTracker:
    """Local database for tracking fixed code smell issues."""
    
    def __init__(self, db_path: str = ".sonar_agent_cache.db"):
        """Initialize the issue tracker with SQLite database."""
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the SQLite database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fixed_issues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_key TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    rule TEXT NOT NULL,
                    message TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    commit_id TEXT,
                    fixed_at TIMESTAMP NOT NULL,
                    file_hash TEXT NOT NULL,
                    UNIQUE(issue_key, branch)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_issue_branch 
                ON fixed_issues(issue_key, branch)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_branch 
                ON fixed_issues(file_path, branch)
            """)
            
            conn.commit()
    
    def _calculate_file_hash(self, file_content: str) -> str:
        """Calculate SHA-256 hash of file content."""
        return hashlib.sha256(file_content.encode('utf-8')).hexdigest()
    
    def is_issue_fixed(self, smell: CodeSmell, branch: str, current_file_content: str = None) -> bool:
        """
        Check if an issue has already been fixed in the current branch.
        
        Args:
            smell: The code smell to check
            branch: Current branch name
            current_file_content: Current file content to verify if fix is still valid
            
        Returns:
            True if issue is already fixed and still valid, False otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT file_hash, fixed_at FROM fixed_issues 
                WHERE issue_key = ? AND branch = ?
            """, (smell.key, branch))
            
            result = cursor.fetchone()
            if not result:
                return False
            
            stored_hash, fixed_at = result
            
            # If we have current file content, verify the fix is still valid
            if current_file_content is not None:
                current_hash = self._calculate_file_hash(current_file_content)
                # If file has changed since fix, the issue might have reappeared
                if current_hash != stored_hash:
                    # Remove stale entry
                    self._remove_fixed_issue(smell.key, branch)
                    return False
            
            return True
    
    def mark_issue_fixed(self, smell: CodeSmell, branch: str, commit_id: str = None, 
                        file_content: str = None) -> bool:
        """
        Mark an issue as fixed in the database.
        
        Args:
            smell: The fixed code smell
            branch: Current branch name
            commit_id: Commit ID where the fix was applied
            file_content: Content of the fixed file
            
        Returns:
            True if successfully marked as fixed, False otherwise
        """
        try:
            file_hash = self._calculate_file_hash(file_content) if file_content else ""
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO fixed_issues 
                    (issue_key, file_path, rule, message, branch, commit_id, fixed_at, file_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    smell.key,
                    smell.file_path,
                    smell.rule,
                    smell.message,
                    branch,
                    commit_id,
                    datetime.now(),
                    file_hash
                ))
                conn.commit()
            
            return True
            
        except sqlite3.Error as e:
            print(f"Error marking issue as fixed: {e}")
            return False
    
    def _remove_fixed_issue(self, issue_key: str, branch: str):
        """Remove a fixed issue entry (used for cleanup)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM fixed_issues 
                WHERE issue_key = ? AND branch = ?
            """, (issue_key, branch))
            conn.commit()
    
    def get_fixed_issues_for_branch(self, branch: str) -> List[FixedIssue]:
        """Get all fixed issues for a specific branch."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM fixed_issues WHERE branch = ?
                ORDER BY fixed_at DESC
            """, (branch,))
            
            results = []
            for row in cursor.fetchall():
                results.append(FixedIssue(
                    issue_key=row['issue_key'],
                    file_path=row['file_path'],
                    rule=row['rule'],
                    message=row['message'],
                    branch=row['branch'],
                    commit_id=row['commit_id'],
                    fixed_at=datetime.fromisoformat(row['fixed_at']),
                    file_hash=row['file_hash']
                ))
            
            return results
    
    def cleanup_old_entries(self, days_old: int = 30):
        """Remove entries older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM fixed_issues WHERE fixed_at < ?
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                print(f"Cleaned up {deleted_count} old issue entries")
    
    def get_branch_statistics(self, branch: str) -> dict:
        """Get statistics for fixed issues in a branch."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_fixed,
                    COUNT(DISTINCT file_path) as files_affected,
                    COUNT(DISTINCT rule) as rules_fixed,
                    MIN(fixed_at) as first_fix,
                    MAX(fixed_at) as last_fix
                FROM fixed_issues 
                WHERE branch = ?
            """, (branch,))
            
            result = cursor.fetchone()
            if result and result[0] > 0:
                return {
                    'total_fixed': result[0],
                    'files_affected': result[1],
                    'rules_fixed': result[2],
                    'first_fix': result[3],
                    'last_fix': result[4]
                }
            
            return {
                'total_fixed': 0,
                'files_affected': 0,
                'rules_fixed': 0,
                'first_fix': None,
                'last_fix': None
            }
    
    def filter_unfixed_issues(self, smells: List[CodeSmell], branch: str) -> List[CodeSmell]:
        """
        Filter out issues that have already been fixed in the current branch.
        
        Args:
            smells: List of code smells to filter
            branch: Current branch name
            
        Returns:
            List of code smells that haven't been fixed yet
        """
        unfixed_smells = []
        fixed_count = 0
        
        for smell in smells:
            if not self.is_issue_fixed(smell, branch):
                unfixed_smells.append(smell)
            else:
                fixed_count += 1
        
        if fixed_count > 0:
            print(f"ℹ️  Skipping {fixed_count} already fixed issues in branch '{branch}'")
        
        return unfixed_smells
