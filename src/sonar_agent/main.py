#!/usr/bin/env python3
"""
Sonar Agent - AI-powered SonarQube code smell fixer with cost tracking

A tool to automatically fetch code smells from SonarQube and fix them using AI.
"""

import argparse
import os
import sys
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass

from .sonar_client import SonarQubeClient, CodeSmell
from .ai_client import AICodeFixer, TokenUsage
from .gitlab_client import GitLabClient, GitLabBatchCommitter
from .github_client import GitHubClient, GitHubBatchCommitter
from .rule_prompt_map import rule_prompt_map
from .issue_tracker import IssueTracker

def load_env_file(env_path: str = ".env") -> Dict[str, str]:
    """Load environment variables from a .env file."""
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


def get_config_value(key: str, args_value: Optional[str] = None, env_vars: Dict[str, str] = None) -> Optional[str]:
    """Get configuration value with priority: args > env file > environment variable."""
    if args_value:
        return args_value
    
    if env_vars and key in env_vars:
        return env_vars[key]
    
    return os.getenv(key)


@dataclass
class CodeSmell:
    """Represents a code smell issue from SonarQube."""
    key: str
    file_path: str
    message: str
    start_line: int
    end_line: int
    effort: str
    debt_minutes: int
    rule: str
    severity: str


@dataclass
class FixResult:
    """Result of fixing a code smell."""
    smell: CodeSmell
    success: bool
    usage: TokenUsage
    error: Optional[str] = None


class SonarAgentApp:
    """Main application class."""
    
    def __init__(self):
        self.sonar_client = None
        self.repo_manager = None
        self.ai_fixer = None
        self.gitlab_client = None
        self.github_client = None
        self.batch_committer = None
        self.working_branch = None
        self.issue_tracker = IssueTracker()

    def create_working_branch(self, config):
        """Create a new working branch for commits."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        branch_name = f"sonar-agent-fixes-{timestamp}"
        
        if self.gitlab_client:
            base_branch = config['gitlab_branch']
            if self.gitlab_client.create_branch(branch_name, base_branch):
                print(f"📝 Created GitLab branch: {branch_name}")
                self.working_branch = branch_name
                return True
            else:
                print(f"⚠️  Failed to create GitLab branch {branch_name}")
                return False
        elif self.github_client:
            base_branch = config['github_branch']
            if self.github_client.create_branch(branch_name, base_branch):
                print(f"📝 Created GitHub branch: {branch_name}")
                self.working_branch = branch_name
                return True
            else:
                print(f"⚠️  Failed to create GitHub branch {branch_name}")
                return False
        else:
            print("⚠️  No Git client configured, cannot create branch")
            return False

    def _load_configuration(self, args):
        """Load and validate configuration from args, env file, and environment variables."""
        # Load environment variables
        env_vars = load_env_file(getattr(args, 'env_file', '.env'))
        
        # Get configuration values with priority: args > env file > environment
        config = {
            # SonarQube configuration
            'sonar_url': get_config_value('SONAR_URL', args.sonar_url, env_vars),
            'sonar_token': get_config_value('SONAR_TOKEN', args.sonar_token, env_vars),
            'project_key': get_config_value('SONAR_PROJECT_KEY', args.project_key, env_vars),
            'pull_request': get_config_value('PULL_REQUEST', args.pull_request, env_vars),
            'max_smells': int(get_config_value('MAX_SMELLS', str(args.max_smells), env_vars) or '10'),
            'dry_run': args.dry_run or get_config_value('DRY_RUN', None, env_vars) == 'true',
            'debug': getattr(args, 'debug', False) or get_config_value('DEBUG', None, env_vars) == 'true',
            
            # AI configuration
            'ai_provider': get_config_value('AI_PROVIDER', getattr(args, 'ai_provider', None), env_vars),
            'ai_api_key': get_config_value('AI_API_KEY', getattr(args, 'ai_api_key', None), env_vars),
            'ai_model': get_config_value('AI_MODEL', getattr(args, 'ai_model', None), env_vars),
            'ai_custom_url': get_config_value('AI_CUSTOM_URL', getattr(args, 'ai_custom_url', None), env_vars),
            
            # GitLab configuration
            'gitlab_url': get_config_value('GITLAB_URL', getattr(args, 'gitlab_url', None), env_vars),
            'gitlab_token': get_config_value('GITLAB_TOKEN', getattr(args, 'gitlab_token', None), env_vars),
            'gitlab_project_id': get_config_value('GITLAB_PROJECT_ID', getattr(args, 'gitlab_project_id', None), env_vars),
            'gitlab_branch': get_config_value('GITLAB_BRANCH', getattr(args, 'gitlab_branch', None), env_vars) or 'main',
            'gitlab_batch_size': int(get_config_value('GITLAB_BATCH_SIZE', getattr(args, 'gitlab_batch_size', None), env_vars) or '10'),
            'gitlab_auto_commit': get_config_value('GITLAB_AUTO_COMMIT', getattr(args, 'gitlab_auto_commit', None), env_vars) == 'true',
            'gitlab_create_mr': get_config_value('GITLAB_CREATE_MR', getattr(args, 'gitlab_create_mr', None), env_vars) == 'true',
            
            # GitHub configuration
            'github_url': get_config_value('GITHUB_URL', getattr(args, 'github_url', None), env_vars) or 'https://api.github.com',
            'github_token': get_config_value('GITHUB_TOKEN', getattr(args, 'github_token', None), env_vars),
            'github_repo_owner': get_config_value('GITHUB_REPO_OWNER', getattr(args, 'github_repo_owner', None), env_vars),
            'github_repo_name': get_config_value('GITHUB_REPO_NAME', getattr(args, 'github_repo_name', None), env_vars),
            'github_branch': get_config_value('GITHUB_BRANCH', getattr(args, 'github_branch', None), env_vars) or 'main',
            'github_batch_size': int(get_config_value('GITHUB_BATCH_SIZE', getattr(args, 'github_batch_size', None), env_vars) or '10'),
            'github_auto_commit': get_config_value('GITHUB_AUTO_COMMIT', getattr(args, 'github_auto_commit', None), env_vars) == 'true',
            'github_create_pr': get_config_value('GITHUB_CREATE_PR', getattr(args, 'github_create_pr', None), env_vars) == 'true',
        }
        
        # Validate required configuration
        if not config['sonar_url']:
            raise ValueError("SonarQube URL is required (--sonar-url or SONAR_URL)")
        if not config['sonar_token']:
            raise ValueError("SonarQube token is required (--sonar-token or SONAR_TOKEN)")
        if not config['project_key']:
            raise ValueError("Project key is required (--project-key or SONAR_PROJECT_KEY)")
        
        print('ai_provider', config['ai_provider'])
        print('ai_api_key', config['ai_api_key'])
        print('ai_model', config['ai_model'])
        
        return config

    def _initialize_clients(self, config):
        """Initialize SonarQube, AI, and Git clients based on configuration."""
        # Initialize SonarQube client
        self.sonar_client = SonarQubeClient(
            config['sonar_url'], 
            config['sonar_token'], 
            debug=config['debug']
        )
        
        # Initialize AI client
        if config['ai_api_key']:
            self.ai_fixer = AICodeFixer(
                config['ai_provider'], 
                config['ai_api_key'], 
                config['ai_model'],
                config['ai_custom_url']
            )
        else:
            print("Warning: No AI API key provided. Using mock responses.")
            self.ai_fixer = AICodeFixer("mock")
        
        # Initialize Git clients (GitLab or GitHub)
        self.gitlab_client = None
        self.github_client = None
        self.batch_committer = None
        
        # GitLab integration
        if (config['gitlab_url'] and config['gitlab_token'] and 
            config['gitlab_project_id']):
            self.gitlab_client = GitLabClient(
                config['gitlab_url'], 
                config['gitlab_token'], 
                config['gitlab_project_id']
            )
            self.batch_committer = GitLabBatchCommitter(
                self.gitlab_client, 
                config['gitlab_batch_size']
            )
            print(f"✅ GitLab integration enabled (batch size: {config['gitlab_batch_size']})")
            
            # Verify GitLab connection
            project_info = self.gitlab_client.get_project_info()
            if project_info:
                print(f"   Connected to project: {project_info.get('name', 'Unknown')}")
            else:
                print("⚠️  Warning: Could not verify GitLab connection")
        
        # GitHub integration (alternative to GitLab)
        elif (config['github_url'] and config['github_token'] and 
              config['github_repo_owner'] and config['github_repo_name']):
            self.github_client = GitHubClient(
                config['github_url'], 
                config['github_token'], 
                config['github_repo_owner'], 
                config['github_repo_name'], 
                debug=config['debug']
            )
            self.batch_committer = GitHubBatchCommitter(
                self.github_client, 
                config['github_batch_size'], 
                debug=config['debug']
            )
            print(f"✅ GitHub integration enabled (batch size: {config['github_batch_size']})")
            
            # Verify GitHub connection
            repo_info = self.github_client.get_repository_info()
            if repo_info:
                print(f"   Connected to repository: {repo_info.get('full_name', 'Unknown')}")
            else:
                print("⚠️  Warning: Could not verify GitHub connection")
        
        else:
            print("ℹ️  Git integration disabled (missing configuration)")

    def _fetch_code_smells(self, config):
        """Fetch code smells from SonarQube."""
        print("Fetching code smells from SonarQube...")
        smells = self.sonar_client.get_code_smells(
            config['project_key'], 
            config['pull_request'], 
            config['max_smells']
        )
        
        if not smells:
            print("No code smells found.")
            return None
        
        print(f"Found {len(smells)} code smell(s)")
        return smells

    def _process_code_smells(self, smells, config):
        """Process each code smell and generate fixes."""
        # Get current branch name for issue tracking
        current_branch = self.working_branch or config.get('gitlab_branch') or config.get('github_branch') or 'main'
        
        # Filter out already fixed issues
        unfixed_smells = self.issue_tracker.filter_unfixed_issues(smells, current_branch)
        
        if len(unfixed_smells) < len(smells):
            print(f"📊 Processing {len(unfixed_smells)} unfixed issues out of {len(smells)} total issues")
        
        results = []
        
        for i, smell in enumerate(unfixed_smells, 1):
            print(smell)
            print(f"\n--- Processing issue {i}/{len(unfixed_smells)} ---")
            print(f"File: {smell.file_path}")
            print(f"Message: {smell.message}")
            print(f"Lines: {smell.line}")
            print(f"Processing {smell.file_path}...")
            
            # Get prompt for the rule based on severity
            try:
                rule = smell.rule
                severity = smell.severity
                
                # Extract rule number and get prompt for all severities
                if ":S" in rule:
                    number = int(rule.split(":S")[1])
                    prompt = rule_prompt_map.get('RSPEC-' + str(number))
                else:
                    print(f"Rule {rule} does not contain ':S', will use default prompt...")
                    prompt = None
                
            except Exception as e:
                print(f"Error processing rule {rule}: {e}, skipping...")
                continue
            
            if prompt is None:
                print(f"No prompt found for rule {rule}, using default prompt...")
                prompt = rule_prompt_map.get('DEFAULT_PROMPT')
                if prompt is None:
                    print(f"Default prompt not found, skipping...")
                    continue
            # Get file content from Git client
            file_content = self._get_file_content(smell.file_path, config)
            if not file_content:
                result = FixResult(smell, False, TokenUsage(), "Could not read file from repository")
                results.append(result)
                print(f"Skipping - could not read file: {smell.file_path}")
                continue
            
            # Fix with AI
            fixed_content, usage = self.ai_fixer.fix_code_smell(smell, file_content, prompt)
            if not fixed_content:
                result = FixResult(smell, False, usage, "AI could not fix the issue")
                results.append(result)
                print(f"Skipping - AI could not fix the issue")
                continue
            
            # Display cost information
            if usage.cost_usd > 0:
                print(f"AI Usage: {usage.total_tokens} tokens, Cost: ${usage.cost_usd:.4f}")
            
            # Handle the fix (dry run or actual commit)
            result = self._handle_single_fix(smell, fixed_content, usage, config)
            
            # Mark issue as fixed if successful and not in dry run mode
            if result.success and not config['dry_run']:
                self.issue_tracker.mark_issue_fixed(
                    smell, 
                    current_branch, 
                    file_content=fixed_content
                )
            
            results.append(result)
        
        return results

    def _get_file_content(self, file_path, config):
        """Get file content from the appropriate Git client."""
        # Always read from the main branch (not the working branch)
        # This ensures we're getting the original files before any fixes
        if self.gitlab_client:
            return self.gitlab_client.get_file_content(file_path, config['gitlab_branch'])
        elif self.github_client:
            return self.github_client.get_file_content(file_path, config['github_branch'])
        return None

    def _handle_single_fix(self, smell, fixed_content, usage, config):
        """Handle a single fix - either dry run or actual commit."""
        if config['dry_run']:
            print(f"[DRY RUN] Would update file: {smell.file_path}")
            return FixResult(smell, True, usage)
        
        # Create working branch if not already created
        if not self.working_branch:
            if not self.create_working_branch(config):
                return FixResult(smell, False, usage, "Failed to create working branch")
        
        # Add to batch committer if available
        if self.batch_committer:
            self.batch_committer.add_file(smell.file_path, fixed_content)
            
            # Check if we should commit this batch
            if self.batch_committer.should_commit():
                commit_result = self.batch_committer.commit_batch(self.working_branch)
                if not commit_result.success:
                    print(f"⚠️  Batch commit failed: {commit_result.error}")
            
            return FixResult(smell, True, usage)
        
        # Direct commit if no batch committer
        return self._direct_commit_fix(smell, fixed_content, usage, config)

    def _direct_commit_fix(self, smell, fixed_content, usage, config):
        """Commit a single fix directly to the repository."""
        # Create working branch if not already created
        if not self.working_branch:
            if not self.create_working_branch(config):
                return FixResult(smell, False, usage, "Failed to create working branch")
        
        commit_message = f"Sonar Agent: Fix code smell in {smell.file_path}"
        
        if self.gitlab_client:
            commit_result = self.gitlab_client.update_file(
                smell.file_path, fixed_content, commit_message, self.working_branch
            )
        elif self.github_client:
            commit_result = self.github_client.update_file(
                smell.file_path, fixed_content, commit_message, self.working_branch
            )
        else:
            return FixResult(smell, False, usage, "No Git client available")
        
        if commit_result.success:
            print(f"✅ Committed fix for: {smell.file_path}")
            return FixResult(smell, True, usage)
        else:
            return FixResult(smell, False, usage, f"Failed to commit: {commit_result.error}")

    def _handle_git_operations(self, results, config):
        """Handle remaining Git operations like final commits and MR/PR creation."""
        if not self.batch_committer or config['dry_run'] or not self.working_branch:
            return
        
        # Commit any remaining files in the batch
        remaining_result = self.batch_committer.commit_remaining(self.working_branch)
        if remaining_result and not remaining_result.success:
            print(f"⚠️  Final batch commit failed: {remaining_result.error}")
        
        # Create merge/pull request if requested
        if ((config['gitlab_create_mr'] or config['github_create_pr']) and 
            self.batch_committer.commit_count > 0):
            self._create_merge_or_pull_request(results, config)

    def _create_merge_or_pull_request(self, results, config):
        """Create a merge request (GitLab) or pull request (GitHub)."""
        if not self.working_branch:
            print("⚠️  No working branch available for creating merge/pull request")
            return
            
        successful_fixes = [r for r in results if r.success]
        
        # Prepare description
        description = f"""
Automated code smell fixes generated by Sonar Agent.

**Summary:**
- Fixed {len(successful_fixes)} code smells
- Total commits: {self.batch_committer.commit_count}
- Technical debt reduced: {sum(r.smell.debt_minutes for r in successful_fixes)} minutes

**Cost Analysis:**
- Total AI cost: ${sum(r.usage.cost_usd for r in results):.4f}
- Total tokens: {sum(r.usage.total_tokens for r in results):,}

Please review the changes before merging.
"""
        
        if self.gitlab_client:
            self._create_gitlab_mr(self.working_branch, description, config)
        elif self.github_client:
            self._create_github_pr(self.working_branch, description, config)

    def _create_gitlab_mr(self, branch_name, description, config):
        """Create a GitLab merge request."""
        title = f"Sonar Agent: Automated code smell fixes ({self.batch_committer.commit_count} batches)"
        mr_result = self.gitlab_client.create_merge_request(
            branch_name, config['gitlab_branch'], title, description
        )
        
        if mr_result:
            print(f"🔀 Created merge request: {mr_result.get('web_url', 'N/A')}")
        else:
            print("⚠️  Failed to create merge request")

    def _create_github_pr(self, branch_name, description, config):
        """Create a GitHub pull request."""
        title = f"Sonar Agent: Automated code smell fixes ({self.batch_committer.commit_count} batches)"
        pr_result = self.github_client.create_pull_request(
            branch_name, config['github_branch'], title, description
        )
        
        if pr_result:
            print(f"🔀 Created pull request: {pr_result.get('html_url', 'N/A')}")
        else:
            print("⚠️  Failed to create pull request")
    
    def _print_summary(self, results: List[FixResult], dry_run: bool, gitlab_enabled: bool = False):
        """Print summary report with cost analysis."""
        print(f"\n{'='*60}")
        print("SUMMARY REPORT")
        print(f"{'='*60}")
        
        successful_fixes = [r for r in results if r.success]
        failed_fixes = [r for r in results if not r.success]
        
        total_debt_minutes = sum(r.smell.debt_minutes for r in successful_fixes)
        total_cost = sum(r.usage.cost_usd for r in results)
        total_tokens = sum(r.usage.total_tokens for r in results)
        
        # Get current branch for statistics
        current_branch = self.working_branch or 'main'
        branch_stats = self.issue_tracker.get_branch_statistics(current_branch)
        
        mode = "DRY RUN - " if dry_run else ""
        print(f"{mode}Issues processed: {len(results)}")
        print(f"{mode}Successfully fixed: {len(successful_fixes)}")
        print(f"{mode}Failed: {len(failed_fixes)}")
        print(f"{mode}Technical debt reduced: {total_debt_minutes} minutes ({total_debt_minutes/60:.1f} hours)")
        
        if total_cost > 0:
            print(f"\nAI COST ANALYSIS:")
            print(f"Total tokens used: {total_tokens:,}")
            print(f"Total cost: ${total_cost:.4f}")
            if len(successful_fixes) > 0:
                avg_cost_per_fix = total_cost / len(successful_fixes)
                avg_debt_per_fix = total_debt_minutes / len(successful_fixes)
                cost_per_minute_saved = total_cost / total_debt_minutes if total_debt_minutes > 0 else 0
                print(f"Average cost per fix: ${avg_cost_per_fix:.4f}")
                print(f"Average debt per fix: {avg_debt_per_fix:.1f} minutes")
                print(f"Cost per minute of debt saved: ${cost_per_minute_saved:.4f}")
        
        if failed_fixes:
            print(f"\nFAILED FIXES:")
            for result in failed_fixes:
                print(f"- {result.smell.file_path}: {result.error}")
        
        # Issue tracking statistics
        if branch_stats['total_fixed'] > 0:
            print(f"\nISSUE TRACKING STATISTICS (Branch: {current_branch}):")
            print(f"Total issues fixed in branch: {branch_stats['total_fixed']}")
            print(f"Files affected: {branch_stats['files_affected']}")
            print(f"Different rules fixed: {branch_stats['rules_fixed']}")
            if branch_stats['first_fix']:
                print(f"First fix: {branch_stats['first_fix']}")
            if branch_stats['last_fix']:
                print(f"Last fix: {branch_stats['last_fix']}")
        
        # GitLab integration summary
        if gitlab_enabled and self.batch_committer:
            print(f"\nGITLAB INTEGRATION:")
            print(f"Commits created: {self.batch_committer.commit_count}")
            print(f"Pending files: {self.batch_committer.get_pending_count()}")
        
        if not dry_run and successful_fixes:
            print("\nNext steps:")
            if gitlab_enabled:
                print("1. Review the GitLab commits and merge requests")
                print("2. Run your test suite to ensure functionality is preserved")
                print("3. Re-run SonarQube scan to verify issues are resolved")
                print("4. Merge the changes if satisfied")
            else:
                print("1. Review the changes made to your files")
                print("2. Run your test suite to ensure functionality is preserved")
                print("3. Re-run SonarQube scan to verify issues are resolved")
                print("4. Commit the changes if satisfied")
        elif dry_run:
            print("\nRe-run without --dry-run to apply the changes")
    def run(self, args):
        """Main entry point."""
        try:
            config = self._load_configuration(args)
            self._initialize_clients(config)
            
            # Fetch and process code smells
            smells = self._fetch_code_smells(config)
            if not smells:
                return
                
            # Create a working branch if we're not in dry run mode and have a Git client
            if not config['dry_run'] and (self.gitlab_client or self.github_client):
                # We'll create the branch on demand when the first fix is ready
                # This avoids creating empty branches if no fixes are made
                pass
            
            # Process each smell and generate fixes
            results = self._process_code_smells(smells, config)
            
            # Handle Git operations (commits, MRs/PRs)
            self._handle_git_operations(results, config)
            
            # Cleanup old database entries (older than 30 days)
            self.issue_tracker.cleanup_old_entries(30)
            
            # Print summary report
            self._print_summary(results, config['dry_run'], config.get('gitlab_auto_commit', False))
            
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AI-powered SonarQube code smell fixer with cost tracking"
    )
    
    # Configuration file
    parser.add_argument('--env-file', default='.env',
                       help='Environment file path (default: .env)')
    
    # SonarQube configuration (optional if in env)
    parser.add_argument('--sonar-url',
                       help='SonarQube server URL (or set SONAR_URL)')
    parser.add_argument('--sonar-token',
                       help='SonarQube authentication token (or set SONAR_TOKEN)')
    parser.add_argument('--project-key',
                       help='SonarQube project key (or set SONAR_PROJECT_KEY)')
    parser.add_argument('--pull-request', 
                       help='GitLab MR ID for filtering issues (or set PULL_REQUEST)')
    
    
    # AI configuration (optional if in env)
    parser.add_argument('--ai-provider', choices=['mistral', 'gemini', 'mock'], default='mistral',
                       help='AI provider to use (or set AI_PROVIDER)')
    parser.add_argument('--ai-api-key',
                       help='AI API key (or set AI_API_KEY)')
    parser.add_argument('--ai-model',
                       help='AI model to use (or set AI_MODEL)')
    parser.add_argument('--ai-custom-url',
                       help='Custom API URL for AI provider (or set AI_CUSTOM_URL)')
    
    # GitLab configuration (optional if in env)
    parser.add_argument('--gitlab-url',
                       help='GitLab server URL (or set GITLAB_URL)')
    parser.add_argument('--gitlab-token',
                       help='GitLab access token (or set GITLAB_TOKEN)')
    parser.add_argument('--gitlab-project-id',
                       help='GitLab project ID (or set GITLAB_PROJECT_ID)')
    parser.add_argument('--gitlab-branch', 
                       help='Target branch for commits (default: main, or set GITLAB_BRANCH)')
    parser.add_argument('--gitlab-batch-size', type=int, default=10,
                       help='Number of files per commit batch (default: 10, or set GITLAB_BATCH_SIZE)')
    parser.add_argument('--gitlab-auto-commit', action='store_true',
                       help='Enable automatic GitLab commits (or set GITLAB_AUTO_COMMIT=true)')
    parser.add_argument('--gitlab-create-mr', action='store_true',
                       help='Create merge request after fixes (or set GITLAB_CREATE_MR=true)')
    
    # GitHub configuration (optional if in env)
    parser.add_argument('--github-url', default='https://api.github.com',
                       help='GitHub API URL (or set GITHUB_URL)')
    parser.add_argument('--github-token',
                       help='GitHub access token (or set GITHUB_TOKEN)')
    parser.add_argument('--github-repo-owner',
                       help='GitHub repository owner (or set GITHUB_REPO_OWNER)')
    parser.add_argument('--github-repo-name',
                       help='GitHub repository name (or set GITHUB_REPO_NAME)')
    parser.add_argument('--github-branch',
                       help='Target branch for commits (default: main, or set GITHUB_BRANCH)')
    parser.add_argument('--github-batch-size', type=int, default=10,
                       help='Number of files per commit batch (default: 10, or set GITHUB_BATCH_SIZE)')
    parser.add_argument('--github-auto-commit', action='store_true',
                       help='Enable automatic GitHub commits (or set GITHUB_AUTO_COMMIT=true)')
    parser.add_argument('--github-create-pr', action='store_true',
                       help='Create pull request after fixes (or set GITHUB_CREATE_PR=true)')
    
    # Processing options
    parser.add_argument('--max-smells', type=int, default=10,
                       help='Maximum number of issues to process (default: 10)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be changed without making changes')
    
    args = parser.parse_args()
    
    app = SonarAgentApp()
    app.run(args)


if __name__ == '__main__':
    main()
