# Sonar Agent

AI-powered SonarQube code smell fixer with cost tracking using Mistral AI and LangChain.

## Features

- **SonarQube Integration**: Fetch CODE_SMELL issues via REST API
- **Mistral AI Powered**: Use Mistral AI models via LangChain for intelligent code fixes
- **Cost Tracking**: Real-time token usage and cost calculation for each fix
- **Technical Debt Analysis**: Calculate cost per minute of technical debt saved
- **GitLab Repository Support**: Work with GitLab repositories via official python-gitlab library
- **Flexible Filtering**: Filter by project or specific pull requests
- **Smart Prioritization**: Sort issues by effort/technical debt
- **Safe Operations**: Automatic file backups and dry-run mode
- **Docker Support**: Portable containerized execution
- **Comprehensive Reporting**: Detailed summary with cost analysis

## Prerequisites

- Python 3.8+
- [UV](https://github.com/astral-sh/uv) (install with `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- SonarQube server access with API token
- Mistral AI API key
- Docker (optional, for containerized usage)

## Installation

### Local Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd sonar-agent
   ```

2. Install with UV:
   ```bash
   uv pip install -e .
   ```

### Docker Installation

1. Build the Docker image:
   ```bash
   docker build -t sonar-agent -f docker/Dockerfile .
   ```

## Configuration

### Environment-Based Configuration (Recommended)

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your configuration:
   ```bash
   # SonarQube Configuration
   SONAR_URL=https://your-sonarqube-server.com
   SONAR_TOKEN=your-sonar-token-here
   SONAR_PROJECT_KEY=your-project-key
   
   # Repository Configuration
   REPO_ROOT=/path/to/your/git/repository
   
   # AI Configuration
   AI_PROVIDER=mistral
   AI_API_KEY=your-mistral-api-key-here
   AI_MODEL=mistral-small  # mistral-tiny, mistral-small, mistral-medium, mistral-large
   
   # Processing Options
   MAX_SMELLS=10
   DRY_RUN=false
   ```

## Usage

### Local Usage

```bash
# Using environment file (recommended)
sonar-agent --dry-run

# Using command line arguments
sonar-agent \
  --sonar-url https://sonarqube.company.com \
  --sonar-token your-token \
  --project-key your-project \
  --repo-root /path/to/repo \
  --ai-api-key your-mistral-key \
  --max-smells 5 \
  --dry-run
```

### Docker Usage

#### Using Docker Compose

```bash
# Set your repository path
export REPO_ROOT=/path/to/your/repository

# Run with docker-compose
docker-compose up sonar-agent

# Include local SonarQube for development
docker-compose --profile dev up
```

#### Using the Run Script

```bash
# Make the script executable (if not already)
chmod +x docker/run.sh

# Run with dry-run
./docker/run.sh --repo-path /path/to/your/repo --dry-run

# Run with custom environment file
./docker/run.sh --repo-path /path/to/your/repo --env-file production.env

# Build and run
./docker/run.sh --build --repo-path /path/to/your/repo
```

#### Manual Docker Run

```bash
docker run --rm -it \
  -v /path/to/your/repo:/workspace:rw \
  -v $(pwd)/.env:/app/.env:ro \
  -e REPO_ROOT=/workspace \
  sonar-agent --dry-run
```

## AI Models and Pricing

Sonar Agent supports different Mistral AI models with varying capabilities and costs:

| Model | Input (per 1K tokens) | Output (per 1K tokens) | Use Case |
|-------|----------------------|------------------------|----------|
| mistral-tiny | $0.00025 | $0.00025 | Fast, basic fixes |
| mistral-small | $0.002 | $0.006 | Balanced performance |
| mistral-medium | $0.0027 | $0.0081 | Complex fixes |
| mistral-large | $0.008 | $0.024 | Most sophisticated |

## Command Line Options

### Configuration Priority
1. **Command line arguments** (highest priority)
2. **Environment file** (`.env`)
3. **System environment variables** (lowest priority)

### Parameters

#### SonarQube Configuration
- `--sonar-url` / `SONAR_URL`: SonarQube server URL
- `--sonar-token` / `SONAR_TOKEN`: SonarQube authentication token
- `--project-key` / `SONAR_PROJECT_KEY`: SonarQube project key
- `--pull-request` / `PULL_REQUEST`: GitLab MR ID for filtering issues

#### Repository Configuration
- `--repo-root` / `REPO_ROOT`: Path to your Git repository

#### AI Configuration
- `--ai-provider` / `AI_PROVIDER`: AI provider (`mistral`, `mock`)
- `--ai-api-key` / `AI_API_KEY`: Mistral AI API key
- `--ai-model` / `AI_MODEL`: AI model to use

#### Processing Options
- `--max-smells` / `MAX_SMELLS`: Maximum number of issues to process (default: 10)
- `--dry-run` / `DRY_RUN`: Show what would be changed without making changes
- `--env-file`: Path to environment file (default: `.env`)

## Example Output

```
Fetching code smells from SonarQube...
Found 5 code smell(s)

--- Processing issue 1/5 ---
File: src/main.py
Message: Remove this unused import of 'os'.
Lines: 3-3
Effort: 2min (2 minutes)
AI Usage: 1,247 tokens, Cost: $0.0087

--- Processing issue 2/5 ---
File: src/utils.py
Message: Extract this nested code block into a method.
Lines: 45-52
Effort: 15min (15 minutes)
AI Usage: 2,156 tokens, Cost: $0.0151

============================================================
SUMMARY REPORT
============================================================
Issues processed: 5
Successfully fixed: 4
Failed: 1
Technical debt reduced: 32 minutes (0.5 hours)

AI COST ANALYSIS:
Total tokens used: 8,429
Total cost: $0.0589
Average cost per fix: $0.0147
Average debt per fix: 8.0 minutes
Cost per minute of debt saved: $0.0018

Next steps:
1. Review the changes made to your files
2. Run your test suite to ensure functionality is preserved
3. Re-run SonarQube scan to verify issues are resolved
4. Commit the changes if satisfied
```

## How It Works

1. **Fetch Issues**: Connects to SonarQube API to retrieve open CODE_SMELL issues
2. **Prioritize**: Sorts issues by estimated effort (technical debt) in descending order
3. **Process Files**: For each issue:
   - Reads the file content from your Git repository
   - Sends the issue description and file content to Mistral AI via LangChain
   - Tracks token usage and calculates costs
   - Receives the fixed version from AI
   - Creates a backup of the original file
   - Writes the fixed version back to the file
4. **GitLab Integration**: Commits fixes to GitLab using the python-gitlab library
   - Batch commits for efficiency
   - Creates merge requests for review
   - Provides links to commits and MRs
5. **Report**: Provides detailed summary with cost analysis and ROI metrics

## Safety Features

- **Automatic Backups**: Original files are backed up with timestamps
- **Dry Run Mode**: Preview changes without applying them
- **Error Handling**: Graceful handling of API failures and file issues
- **Validation**: Ensures files exist and are readable before processing
- **Cost Monitoring**: Real-time cost tracking to prevent unexpected expenses

## Development

### Running Tests

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=sonar_agent
```

### Code Formatting

```bash
black .
isort .
mypy .
```

## Docker Development

### Building

```bash
# Build the image
docker build -t sonar-agent -f docker/Dockerfile .

# Build with docker-compose
docker-compose build
```

### Local SonarQube for Testing

```bash
# Start SonarQube locally
docker-compose --profile dev up sonarqube

# Access at http://localhost:9000
# Default credentials: admin/admin
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT
