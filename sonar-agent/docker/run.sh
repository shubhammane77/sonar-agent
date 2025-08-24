#!/bin/bash

# Sonar Agent Docker Runner Script

set -e

# Default values
REPO_PATH=""
ENV_FILE=".env"
DRY_RUN="false"
DOCKER_IMAGE="sonar-agent:latest"

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -r, --repo-path PATH     Path to your Git repository (required)"
    echo "  -e, --env-file FILE      Environment file path (default: .env)"
    echo "  -d, --dry-run           Run in dry-run mode"
    echo "  -b, --build             Build Docker image before running"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --repo-path /path/to/repo --dry-run"
    echo "  $0 -r /path/to/repo -e production.env"
    echo "  $0 --build --repo-path /path/to/repo"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--repo-path)
            REPO_PATH="$2"
            shift 2
            ;;
        -e|--env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN="true"
            shift
            ;;
        -b|--build)
            BUILD_IMAGE="true"
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required parameters
if [[ -z "$REPO_PATH" ]]; then
    echo "Error: Repository path is required"
    usage
fi

if [[ ! -d "$REPO_PATH" ]]; then
    echo "Error: Repository path does not exist: $REPO_PATH"
    exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: Environment file does not exist: $ENV_FILE"
    echo "Please create $ENV_FILE based on .env.example"
    exit 1
fi

# Build image if requested
if [[ "$BUILD_IMAGE" == "true" ]]; then
    echo "Building Docker image..."
    docker build -t $DOCKER_IMAGE -f docker/Dockerfile .
fi

# Prepare Docker run command
DOCKER_CMD="docker run --rm -it"
DOCKER_CMD="$DOCKER_CMD -v $(realpath $REPO_PATH):/workspace:rw"
DOCKER_CMD="$DOCKER_CMD -v $(realpath $ENV_FILE):/app/.env:ro"
DOCKER_CMD="$DOCKER_CMD -e REPO_ROOT=/workspace"
DOCKER_CMD="$DOCKER_CMD $DOCKER_IMAGE"

# Add dry-run flag if specified
if [[ "$DRY_RUN" == "true" ]]; then
    DOCKER_CMD="$DOCKER_CMD --dry-run"
fi

echo "Running Sonar Agent..."
echo "Repository: $REPO_PATH"
echo "Environment: $ENV_FILE"
echo "Dry run: $DRY_RUN"
echo ""

# Execute the command
eval $DOCKER_CMD
