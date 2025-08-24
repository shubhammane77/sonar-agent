"""
GitLab API client for batch commits and project operations.
"""

import base64
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

import requests


@dataclass
class GitLabFile:
    """Represents a file to be committed to GitLab."""
    file_path: str
    content: str
    action: str = "update"  # create, update, delete
    encoding: str = "text"


@dataclass
class CommitResult:
    """Result of a GitLab commit operation."""
    success: bool
    commit_id: Optional[str] = None
    commit_url: Optional[str] = None
    error: Optional[str] = None


class GitLabClient:
    """Client for interacting with GitLab API."""
    
    def __init__(self, base_url: str, token: str, project_id: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.project_id = project_id
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        })
    
    def get_project_info(self) -> Optional[Dict]:
        """Get project information from GitLab."""
        url = f"{self.base_url}/api/v4/projects/{self.project_id}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching project info: {e}")
            return None
    
    def get_file_content(self, file_path: str, ref: str = "main") -> Optional[str]:
        """Get file content from GitLab repository."""
        # URL encode the file path
        encoded_path = requests.utils.quote(file_path, safe='')
        url = f"{self.base_url}/api/v4/projects/{self.project_id}/repository/files/{encoded_path}"
        
        params = {'ref': ref}
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Decode base64 content
            if data.get('encoding') == 'base64':
                return base64.b64decode(data['content']).decode('utf-8')
            else:
                return data.get('content', '')
                
        except requests.RequestException as e:
            print(f"Error fetching file {file_path}: {e}")
            return None
    
    def create_branch(self, branch_name: str, ref: str = "main") -> bool:
        """Create a new branch in GitLab."""
        url = f"{self.base_url}/api/v4/projects/{self.project_id}/repository/branches"
        
        data = {
            'branch': branch_name,
            'ref': ref
        }
        
        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"Error creating branch {branch_name}: {e}")
            return False
    
    def batch_commit(self, files: List[GitLabFile], commit_message: str, 
                    branch: str = "main", author_email: Optional[str] = None,
                    author_name: Optional[str] = None) -> CommitResult:
        """Commit multiple files in a single commit to GitLab."""
        url = f"{self.base_url}/api/v4/projects/{self.project_id}/repository/commits"
        
        # Prepare actions for each file
        actions = []
        for file in files:
            action = {
                'action': file.action,
                'file_path': file.file_path,
                'content': file.content
            }
            
            if file.encoding == 'base64':
                action['encoding'] = 'base64'
            
            actions.append(action)
        
        # Prepare commit data
        commit_data = {
            'branch': branch,
            'commit_message': commit_message,
            'actions': actions
        }
        
        if author_email:
            commit_data['author_email'] = author_email
        if author_name:
            commit_data['author_name'] = author_name
        
        try:
            response = self.session.post(url, json=commit_data)
            response.raise_for_status()
            
            result = response.json()
            commit_id = result.get('id')
            commit_url = result.get('web_url')
            
            return CommitResult(
                success=True,
                commit_id=commit_id,
                commit_url=commit_url
            )
            
        except requests.RequestException as e:
            error_msg = f"Error committing to GitLab: {e}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {e.response.text}"
            
            return CommitResult(success=False, error=error_msg)
    
    def create_merge_request(self, source_branch: str, target_branch: str = "main",
                           title: str = None, description: str = None) -> Optional[Dict]:
        """Create a merge request in GitLab."""
        url = f"{self.base_url}/api/v4/projects/{self.project_id}/merge_requests"
        
        if not title:
            title = f"Sonar Agent: Code smell fixes from {source_branch}"
        
        if not description:
            description = "Automated code smell fixes generated by Sonar Agent"
        
        data = {
            'source_branch': source_branch,
            'target_branch': target_branch,
            'title': title,
            'description': description
        }
        
        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error creating merge request: {e}")
            return None


class GitLabBatchCommitter:
    """Handles batch commits for sonar-agent fixes."""
    
    def __init__(self, gitlab_client: GitLabClient, batch_size: int = 10):
        self.gitlab_client = gitlab_client
        self.batch_size = batch_size
        self.pending_files = []
        self.commit_count = 0
    
    def add_file(self, file_path: str, content: str, action: str = "update"):
        """Add a file to the pending commit batch."""
        gitlab_file = GitLabFile(
            file_path=file_path,
            content=content,
            action=action
        )
        self.pending_files.append(gitlab_file)
    
    def should_commit(self) -> bool:
        """Check if we should commit the current batch."""
        return len(self.pending_files) >= self.batch_size
    
    def commit_batch(self, branch: str = "main", custom_message: str = None) -> CommitResult:
        """Commit the current batch of files."""
        if not self.pending_files:
            return CommitResult(success=False, error="No files to commit")
        
        self.commit_count += 1
        
        if custom_message:
            commit_message = custom_message
        else:
            file_count = len(self.pending_files)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_message = f"Sonar Agent: Fix {file_count} code smells (batch #{self.commit_count}) - {timestamp}"
        
        # Add file list to commit message
        file_list = "\n".join([f"- {f.file_path}" for f in self.pending_files[:5]])
        if len(self.pending_files) > 5:
            file_list += f"\n- ... and {len(self.pending_files) - 5} more files"
        
        full_message = f"{commit_message}\n\nFiles modified:\n{file_list}"
        
        result = self.gitlab_client.batch_commit(
            files=self.pending_files,
            commit_message=full_message,
            branch=branch,
            author_name="Sonar Agent",
            author_email="sonar-agent@automated.local"
        )
        
        if result.success:
            print(f"✅ Committed batch #{self.commit_count} with {len(self.pending_files)} files")
            print(f"   Commit ID: {result.commit_id}")
            if result.commit_url:
                print(f"   URL: {result.commit_url}")
            self.pending_files.clear()
        else:
            print(f"❌ Failed to commit batch #{self.commit_count}: {result.error}")
        
        return result
    
    def commit_remaining(self, branch: str = "main") -> Optional[CommitResult]:
        """Commit any remaining files in the batch."""
        if self.pending_files:
            return self.commit_batch(branch)
        return None
    
    def get_pending_count(self) -> int:
        """Get the number of pending files."""
        return len(self.pending_files)
    
    def clear_pending(self):
        """Clear all pending files without committing."""
        self.pending_files.clear()
