#!/usr/bin/env python3
"""
SonarQube API client for fetching code smells and issues.
"""

import requests
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class CodeSmell:
    """Represents a code smell from SonarQube."""
    key: str
    rule: str
    severity: str
    message: str
    component: str
    file_path: str
    line: int
    debt_minutes: int
    type: str = "CODE_SMELL"
    
    @classmethod
    def from_sonar_issue(cls, issue: Dict[str, Any]) -> 'CodeSmell':
        """Create CodeSmell from SonarQube API response."""
        # Extract file path from component
        component = issue.get('component', '')
        file_path = component.split(':')[-1] if ':' in component else component
        
        # Parse debt (effort) - format like "5min"
        debt_str = issue.get('debt', '0min')
        debt_minutes = 0
        if debt_str and debt_str.endswith('min'):
            try:
                debt_minutes = int(debt_str[:-3])
            except ValueError:
                debt_minutes = 5  # Default fallback
        
        return cls(
            key=issue.get('key', ''),
            rule=issue.get('rule', ''),
            severity=issue.get('severity', 'MINOR'),
            message=issue.get('message', ''),
            component=component,
            file_path=file_path,
            line=issue.get('line', 1),
            debt_minutes=debt_minutes
        )


class SonarQubeClient:
    """Client for interacting with SonarQube API."""
    
    def __init__(self, base_url: str, token: str, debug: bool = False):
        """Initialize SonarQube client."""
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.debug = debug
        self.session = requests.Session()
        self.session.auth = (token, '')
        
    def get_code_smells(self, project_key: str, pull_request: Optional[str] = None, 
                       max_issues: int = 10) -> List[CodeSmell]:
        """Fetch code smells from SonarQube."""
        url = f"{self.base_url}/api/issues/search"
        
        params = {
            'componentKeys': project_key,
            'types': 'CODE_SMELL',
            'ps': max_issues,  # Page size
            'facets': 'severities,types',
            's': 'SEVERITY',  # Sort by severity
            'asc': 'false'    # Descending order
        }
        
        # Add pull request filter if specified
        if pull_request:
            params['pullRequest'] = pull_request
        
        if self.debug:
            print(f"🔍 DEBUG: SonarQube API Request")
            print(f"   URL: {url}")
            print(f"   Params: {params}")
            print(f"   Auth: {self.session.auth[0][:10]}...")
            
        try:
            response = self.session.get(url, params=params)
            
            if self.debug:
                print(f"   Response Status: {response.status_code}")
                print(f"   Response Headers: {dict(response.headers)}")
                
            response.raise_for_status()
            
            data = response.json()
            issues = data.get('issues', [])
            
            if self.debug:
                print(f"   Found {len(issues)} issues")
                if issues:
                    print(f"   First issue: {issues[0].get('key', 'N/A')} - {issues[0].get('message', 'N/A')[:50]}...")
            
            # Convert to CodeSmell objects
            code_smells = []
            for issue in issues:
                try:
                    smell = CodeSmell.from_sonar_issue(issue)
                    code_smells.append(smell)
                except Exception as e:
                    print(f"Warning: Failed to parse issue {issue.get('key', 'unknown')}: {e}")
                    continue
                    
            return code_smells
            
        except requests.RequestException as e:
            if self.debug:
                print(f"🔍 DEBUG: SonarQube Request Error")
                print(f"   Error: {e}")
                print(f"   Response: {getattr(e.response, 'text', 'No response')}")
            print(f"Error fetching code smells: {e}")
            return []
        except Exception as e:
            if self.debug:
                print(f"🔍 DEBUG: Unexpected SonarQube Error: {e}")
            print(f"Unexpected error: {e}")
            return []
    
    def get_project_info(self, project_key: str) -> Optional[Dict[str, Any]]:
        """Get project information from SonarQube."""
        url = f"{self.base_url}/api/projects/search"
        params = {'projects': project_key}
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            components = data.get('components', [])
            
            if components:
                return components[0]
            return None
            
        except requests.RequestException as e:
            print(f"Error fetching project info: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test connection to SonarQube server."""
        url = f"{self.base_url}/api/system/status"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return True
        except requests.RequestException:
            return False
