# Sonar Agent - Project Context

## Project Overview

**Sonar Agent** is an AI-powered SonarQube code smell fixer with comprehensive cost tracking and GitLab integration. It automatically fetches code smells from SonarQube and fixes them using Mistral AI through LangChain.

## Architecture

### Core Components

1. **SonarQubeClient** (`sonar_client.py`)
   - Fetches code smells via SonarQube REST API
   - Handles authentication and project filtering
   - Supports pull request filtering

2. **AICodeFixer** (`ai_client.py`)
   - LangChain integration with Mistral AI models
   - Token usage and cost tracking
   - Support for multiple AI providers (mistral, mock)

3. **GitLabRepoManager** (`repo_manager.py`)
   - Local repository file operations
   - File reading/writing with backup support
   - Git repository management

4. **GitLabClient** (`gitlab_client.py`)
   - GitLab REST API integration
   - Project operations and file management
   - Commit and merge request creation

5. **GitLabBatchCommitter** (`gitlab_client.py`)
   - Batch commit functionality
   - Configurable batch sizes
   - Automatic commit creation

6. **SonarAgentApp** (`main.py`)
   - Main application orchestrator
   - CLI argument parsing
   - Environment configuration management

### Data Models

- **CodeSmell**: SonarQube issue representation
- **TokenUsage**: AI token usage and cost tracking
- **FixResult**: Fix attempt result with success/failure status
- **CommitResult**: GitLab commit operation result

## Key Features

### AI Integration
- **Mistral AI Models**: mistral-tiny, mistral-small, mistral-medium, mistral-large
- **Cost Tracking**: Real-time token usage and cost calculation
- **Technical Debt Analysis**: Cost per minute of debt saved calculation

### GitLab Integration
- **Batch Commits**: Groups file changes into configurable batches (default: 10 files)
- **Merge Request Creation**: Automatic MR creation with detailed summaries
- **Branch Management**: Creates feature branches for fixes
- **Cost Analysis in MRs**: Includes token usage and cost information

### Configuration Management
- **Environment Files**: `.env` file support with fallback to CLI args
- **Priority System**: args > env file > environment variables
- **Comprehensive CLI**: All features configurable via command line

## Configuration

### Required Environment Variables
```bash
SONAR_URL=https://sonar.example.com
SONAR_TOKEN=your_sonar_token
SONAR_PROJECT_KEY=your_project_key
REPO_ROOT=/path/to/repository
AI_API_KEY=your_mistral_api_key
```

### GitLab Configuration (Optional)
```bash
GITLAB_URL=https://gitlab.example.com
GITLAB_TOKEN=your_gitlab_token
GITLAB_PROJECT_ID=123
GITLAB_BRANCH=main
GITLAB_BATCH_SIZE=10
GITLAB_AUTO_COMMIT=true
GITLAB_CREATE_MR=true
```

### AI Configuration (Optional)
```bash
AI_PROVIDER=mistral
AI_MODEL=mistral-small
```

## CLI Usage

### Basic Usage
```bash
sonar-agent --sonar-url https://sonar.example.com \
           --sonar-token your_token \
           --project-key your_project \
           --repo-root /path/to/repo \
           --ai-api-key your_mistral_key
```

### GitLab Integration
```bash
sonar-agent --gitlab-url https://gitlab.example.com \
           --gitlab-token your_token \
           --gitlab-project-id 123 \
           --gitlab-auto-commit \
           --gitlab-create-mr
```

### Processing Options
```bash
sonar-agent --max-smells 20 \
           --dry-run \
           --pull-request 456
```

## Docker Support

### Build and Run
```bash
cd docker
./run.sh --repo-path /path/to/repo --dry-run
```

### Docker Compose
```bash
docker-compose up --build
```

## Project Structure

```
sonar-agent/
├── src/sonar_agent/
│   ├── __init__.py
│   ├── main.py              # Main application and CLI
│   ├── sonar_client.py      # SonarQube API client
│   ├── ai_client.py         # AI integration with cost tracking
│   ├── repo_manager.py      # Repository file operations
│   └── gitlab_client.py     # GitLab API integration
├── tests/
│   └── test_ai_client.py    # AI client tests
├── docker/
│   ├── Dockerfile           # Multi-stage Docker build
│   ├── docker-compose.yml   # Docker Compose configuration
│   └── run.sh              # Helper script for Docker execution
├── .env.example            # Environment template
├── pyproject.toml          # Project configuration and dependencies
├── README.md               # User documentation
└── context.md              # This file
```

## Dependencies

### Core Dependencies
- `langchain>=0.1.0` - AI framework
- `langchain-mistralai>=0.1.0` - Mistral AI integration
- `tiktoken>=0.5.0` - Token estimation
- `requests` - HTTP client for APIs

### Development Dependencies
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting

## Cost Analysis

### Mistral AI Pricing (per 1M tokens)
- mistral-tiny: $0.25 input, $0.25 output
- mistral-small: $2.00 input, $6.00 output
- mistral-medium: $2.70 input, $8.10 output
- mistral-large: $8.00 input, $24.00 output

### Metrics Tracked
- Prompt tokens and completion tokens
- Total cost per fix
- Cost per minute of technical debt saved
- Session-wide usage tracking

## Workflow

1. **Configuration Loading**: Load from .env file and CLI args
2. **SonarQube Integration**: Fetch code smells with filtering
3. **AI Processing**: Fix each smell using Mistral AI
4. **File Operations**: Write fixes to repository
5. **GitLab Integration**: Batch commit and create MRs
6. **Reporting**: Generate comprehensive cost and fix summary

## Error Handling

- Graceful API failure handling
- File operation error recovery
- Cost tracking even on failures
- Detailed error reporting in summaries

## Recent Updates

- Added comprehensive GitLab integration with batch commits
- Implemented merge request creation with cost analysis
- Enhanced CLI with GitLab configuration options
- Added batch committer for efficient Git operations
- Improved error handling and reporting

## Development Notes

- Uses UV package manager for fast dependency resolution
- Modular architecture for easy testing and extension
- Comprehensive environment variable support
- Docker containerization for portability
- Cost-conscious design with detailed usage tracking
