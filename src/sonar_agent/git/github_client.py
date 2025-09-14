#!/usr/bin/env python3
"""
GitHub API client for repository operations and batch commits.
"""

import base64
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CommitResult:
    """Result of a commit operation."""
    success: bool
    commit_sha: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


class GitHubClient:
    """Client for interacting with GitHub REST API."""
    
    def __init__(self, base_url: str, token: str, repo_owner: str, repo_name: str, debug: bool = False):
        """Initialize GitHub client."""
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.debug = debug
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'sonar-agent/1.0'
        })
        
    def get_repository_info(self) -> Optional[Dict]:
        """Get repository information."""
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching repository info: {e}")
            return None
    
    def get_file_content(self, file_path: str, branch: str = 'main') -> Optional[str]:
        """Get file content from GitHub."""
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            data = response.json()
            if data.get('type') == 'file':
                content = base64.b64decode(data['content']).decode('utf-8')
                return content
            return None
            
        except requests.RequestException as e:
            print(f"Error fetching file {file_path}: {e}")
            return None
    
    def update_file(self, file_path: str, content: str, message: str, 
                   branch: str = 'main') -> CommitResult:
        """Update a single file in the repository."""
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"
        
        if self.debug:
            print(f"🔍 DEBUG: GitHub update_file")
            print(f"   File: {file_path}")
            print(f"   Branch: {branch}")
            print(f"   URL: {url}")
            print(f"   Content length: {len(content)} chars")
        
        try:
            # Get current file info to get SHA
            current_response = self.session.get(url, params={'ref': branch})
            
            if self.debug:
                print(f"   Current file check status: {current_response.status_code}")
            
            sha = None
            if current_response.status_code == 200:
                sha = current_response.json().get('sha')
                if self.debug:
                    print(f"   Found existing file SHA: {sha[:10]}...")
            elif current_response.status_code == 404:
                if self.debug:
                    print(f"   File doesn't exist, will create new")
            else:
                if self.debug:
                    print(f"   Unexpected status getting file: {current_response.text}")
            
            # Prepare update data
            encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            data = {
                'message': message,
                'content': encoded_content,
                'branch': branch
            }
            
            if sha:
                data['sha'] = sha
                if self.debug:
                    print(f"   Update mode: existing file")
            else:
                if self.debug:
                    print(f"   Create mode: new file")
            
            if self.debug:
                print(f"   Sending PUT request...")
            
            response = self.session.put(url, json=data)
            
            if self.debug:
                print(f"   Response status: {response.status_code}")
                if response.status_code != 200 and response.status_code != 201:
                    print(f"   Response body: {response.text}")
            
            response.raise_for_status()
            
            result_data = response.json()
            return CommitResult(
                success=True,
                commit_sha=result_data.get('commit', {}).get('sha'),
                message=message
            )
            
        except requests.RequestException as e:
            error_msg = f"Failed to update file {file_path}: {e}"
            if self.debug:
                print(f"   🔍 DEBUG: Request failed - {error_msg}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"   Response status: {e.response.status_code}")
                    print(f"   Response body: {e.response.text}")
            return CommitResult(
                success=False,
                error=error_msg
            )
    
    def create_branch(self, branch_name: str, from_branch: str = 'main') -> bool:
        """Create a new branch from an existing branch."""
        try:
            # Get the SHA of the source branch
            ref_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/ref/heads/{from_branch}"
            ref_response = self.session.get(ref_url)
            ref_response.raise_for_status()
            
            source_sha = ref_response.json()['object']['sha']
            
            # Create new branch
            create_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs"
            data = {
                'ref': f'refs/heads/{branch_name}',
                'sha': source_sha
            }
            
            response = self.session.post(create_url, json=data)
            response.raise_for_status()
            return True
            
        except requests.RequestException as e:
            print(f"Error creating branch {branch_name}: {e}")
            return False
    
    def create_pull_request(self, head_branch: str, base_branch: str, 
                          title: str, body: str) -> Optional[Dict]:
        """Create a pull request."""
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls"
        
        data = {
            'title': title,
            'head': head_branch,
            'base': base_branch,
            'body': body
        }
        
        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            print(f"Error creating pull request: {e}")
            return None


class GitHubBatchCommitter:
    """Handles batching of commits for GitHub."""
    
    def __init__(self, github_client: GitHubClient, batch_size: int = 10, debug: bool = False):
        """Initialize batch committer."""
        self.github_client = github_client
        self.batch_size = batch_size
        self.debug = debug
        self.pending_files = {}  # file_path -> content
        self.commit_count = 0
        
    def add_file(self, file_path: str, content: str):
        """Add a file to the pending batch."""
        self.pending_files[file_path] = content
        
    def should_commit(self) -> bool:
        """Check if batch should be committed."""
        return len(self.pending_files) >= self.batch_size
        
    def commit_batch(self, branch: str = 'main') -> CommitResult:
        """Commit the current batch of files."""
        if not self.pending_files:
            return CommitResult(success=True, message="No files to commit")
            
        try:
            # Create a single commit message for the batch
            file_count = len(self.pending_files)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_message = f"Sonar Agent: Fix {file_count} code smells ({timestamp})"
            
            # For GitHub, we need to commit files one by one
            # In a real implementation, you might want to use the Git Data API
            # to create a single commit with multiple files
            successful_commits = []
            failed_commits = []
            
            for file_path, content in self.pending_files.items():
                if self.debug:
                    print(f"🔍 DEBUG: Batch committing file: {file_path}")
                    print(f"   Content length: {len(content)} chars")
                    print(f"   Branch: {branch}")
                
                result = self.github_client.update_file(
                    file_path, content, commit_message, branch
                )
                
                if result.success:
                    successful_commits.append(file_path)
                    if self.debug:
                        print(f"   ✅ Success: {file_path}")
                else:
                    failed_commits.append((file_path, result.error))
                    if self.debug:
                        print(f"   ❌ Failed: {file_path} - {result.error}")
                    print(f"⚠️  Failed to commit {file_path}: {result.error}")
            
            # Clear pending files
            self.pending_files.clear()
            self.commit_count += 1
            
            if failed_commits:
                failed_files = [f[0] for f in failed_commits]
                failed_errors = [f[1] for f in failed_commits]
                error_msg = f"Failed files: {failed_files}. Errors: {failed_errors}"
                
                print(f"⚠️  Batch commit partial failure:")
                print(f"   ✅ Successful: {len(successful_commits)} files")
                print(f"   ❌ Failed: {len(failed_commits)} files")
                for file_path, error in failed_commits:
                    print(f"      - {file_path}: {error}")
                
                return CommitResult(
                    success=len(successful_commits) > 0,
                    message=f"Committed {len(successful_commits)}/{len(successful_commits) + len(failed_commits)} files",
                    error=error_msg
                )
            else:
                return CommitResult(
                    success=True,
                    message=f"Successfully committed {len(successful_commits)} files"
                )
                
        except Exception as e:
            return CommitResult(
                success=False,
                error=f"Batch commit failed: {e}"
            )
    
    def commit_remaining(self, branch: str = 'main') -> Optional[CommitResult]:
        """Commit any remaining files in the batch."""
        if self.pending_files:
            return self.commit_batch(branch)
        return None
        
    def get_pending_count(self) -> int:
        """Get count of pending files."""
        return len(self.pending_files)
