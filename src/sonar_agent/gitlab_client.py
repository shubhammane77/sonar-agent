"""
GitLab API client for batch commits and project operations.
"""

import base64
from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass
from datetime import datetime

import gitlab
from gitlab.v4.objects import Project


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
    """Client for interacting with GitLab API using python-gitlab library."""
    
    def __init__(self, base_url: str, token: str, project_id: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.project_id = project_id
        
        # Initialize the GitLab client
        self.gl = gitlab.Gitlab(url=self.base_url, private_token=token, ssl_verify=False)
        
        # Get the project object
        try:
            self.project = self.gl.projects.get(self.project_id)
        except gitlab.exceptions.GitlabGetError as e:
            print(f"Error connecting to GitLab project: {e}")
            self.project = None
    
    def get_project_info(self) -> Optional[Dict]:
        """Get project information from GitLab."""
        try:
            if not self.project:
                self.project = self.gl.projects.get(self.project_id)
            
            # Convert project object to dictionary
            return {
                'id': self.project.id,
                'name': self.project.name,
                'description': self.project.description,
                'web_url': self.project.web_url,
                'default_branch': self.project.default_branch,
                'visibility': self.project.visibility,
                'path_with_namespace': self.project.path_with_namespace
            }
        except gitlab.exceptions.GitlabError as e:
            print(f"Error fetching project info: {e}")
            return None
    
    def get_file_content(self, file_path: str, ref: str = "main") -> Optional[str]:
        """Get file content from GitLab repository."""
        try:
            f = self.project.files.get(file_path=file_path, ref=ref)
            
            # Decode base64 content
            return base64.b64decode(f.content).decode('utf-8')
                
        except gitlab.exceptions.GitlabError as e:
            print(f"Error fetching file {file_path}: {e}")
            return None
    
    def create_branch(self, branch_name: str, ref: str = "main") -> bool:
        """Create a new branch in GitLab."""
        try:
            self.project.branches.create({'branch': branch_name, 'ref': ref})
            return True
        except gitlab.exceptions.GitlabError as e:
            print(f"Error creating branch {branch_name}: {e}")
            return False
    
    def batch_commit(self, files: List[GitLabFile], commit_message: str, 
                    branch: str = "main", author_email: Optional[str] = None,
                    author_name: Optional[str] = None) -> CommitResult:
        """Commit multiple files in a single commit to GitLab."""
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
            # Use the commits API to create a commit with multiple file actions
            commit = self.project.commits.create(commit_data)
            
            return CommitResult(
                success=True,
                commit_id=commit.id,
                commit_url=f"{self.base_url}/{self.project.path_with_namespace}/-/commit/{commit.id}"
            )
            
        except gitlab.exceptions.GitlabError as e:
            error_msg = f"Error committing to GitLab: {e}"
            return CommitResult(success=False, error=error_msg)
    
    def create_merge_request(self, source_branch: str, target_branch: str = "main",
                           title: str = None, description: str = None) -> Optional[Dict]:
        """Create a merge request in GitLab."""
        if not title:
            title = f"Sonar Agent: Code smell fixes from {source_branch}"
        
        if not description:
            description = "Automated code smell fixes generated by Sonar Agent"
        
        try:
            mr = self.project.mergerequests.create({
                'source_branch': source_branch,
                'target_branch': target_branch,
                'title': title,
                'description': description
            })
            
            # Convert to dictionary
            return {
                'id': mr.iid,
                'web_url': mr.web_url,
                'title': mr.title,
                'state': mr.state
            }
        except gitlab.exceptions.GitlabError as e:
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
