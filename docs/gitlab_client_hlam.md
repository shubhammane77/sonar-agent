# GitLab Client High-Level Architecture Map (HLAM)

This document provides a high-level overview of the GitLab client implementation, method flows, and interactions between components.

## Class Structure

```
┌─────────────────┐      ┌─────────────────┐
│   GitLabFile    │      │   CommitResult  │
│ (Data Class)    │      │  (Data Class)   │
└─────────────────┘      └─────────────────┘
         ▲                        ▲
         │                        │
         │                        │
         │                        │
┌─────────────────┐      uses    │
│  GitLabClient   │◄─────────────┘
│                 │
└───────┬─────────┘
        │
        │ uses
        ▼
┌─────────────────┐
│GitLabBatchCommit│
│      ter        │
└─────────────────┘
```

## GitLabClient Class

The `GitLabClient` class provides an interface to interact with GitLab's API using the python-gitlab library.

### Method Flows

#### Initialization Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  __init__   │────►│ Initialize  │────►│  Get Project│
│             │     │ GitLab      │     │  Object     │
└─────────────┘     └─────────────┘     └─────────────┘
```

1. **__init__(base_url, token, project_id)**
   - Initializes the GitLab client with the provided URL, token, and project ID
   - Creates a gitlab.Gitlab instance
   - Attempts to retrieve the project object

#### Project Information Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│get_project_ │────►│ Fetch       │────►│ Return      │
│    info     │     │ Project     │     │ Project     │
└─────────────┘     └─────────────┘     └─────────────┘
```

1. **get_project_info()**
   - Retrieves project information from GitLab
   - Returns a dictionary with project details (id, name, description, etc.)
   - Handles GitLab API errors

#### File Operations Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│get_file_    │────►│ Get File    │────►│ Decode      │
│  content    │     │ Object      │     │ Content     │
└─────────────┘     └─────────────┘     └─────────────┘
```

1. **get_file_content(file_path, ref)**
   - Retrieves file content from the GitLab repository
   - Decodes base64 content
   - Handles GitLab API errors

#### Branch Operations Flow

```
┌─────────────┐     ┌─────────────┐
│create_branch │────►│ Create      │
│             │     │ Branch      │
└─────────────┘     └─────────────┘
```

1. **create_branch(branch_name, ref)**
   - Creates a new branch in the GitLab repository
   - Returns success/failure status
   - Handles GitLab API errors

#### Commit Operations Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│batch_commit │────►│ Prepare     │────►│ Create      │
│             │     │ Actions     │     │ Commit      │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
                                              ▼
                                        ┌─────────────┐
                                        │ Return      │
                                        │ Result      │
                                        └─────────────┘
```

1. **batch_commit(files, commit_message, branch, author_email, author_name)**
   - Commits multiple files in a single commit
   - Prepares actions for each file
   - Creates the commit in GitLab
   - Returns a CommitResult object
   - Handles GitLab API errors

#### Merge Request Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│create_merge_│────►│ Create MR   │────►│ Return      │
│  request    │     │ Object      │     │ MR Details  │
└─────────────┘     └─────────────┘     └─────────────┘
```

1. **create_merge_request(source_branch, target_branch, title, description)**
   - Creates a merge request in GitLab
   - Returns merge request details
   - Handles GitLab API errors

## GitLabBatchCommitter Class

The `GitLabBatchCommitter` class provides a way to batch multiple file changes into a single commit.

### Method Flows

#### Batch Management Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  add_file   │────►│should_commit│────►│commit_batch │
│             │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
                                              ▼
                                        ┌─────────────┐
                                        │commit_remain│
                                        │    ing      │
                                        └─────────────┘
```

1. **add_file(file_path, content, action)**
   - Adds a file to the pending commit batch
   - Creates a GitLabFile object and adds it to the pending files list

2. **should_commit()**
   - Checks if the current batch should be committed
   - Returns true if the batch size threshold is reached

3. **commit_batch(branch, custom_message)**
   - Commits the current batch of files
   - Creates a commit message with file details
   - Uses GitLabClient.batch_commit to perform the actual commit
   - Returns the CommitResult
   - Clears the pending files on success

4. **commit_remaining(branch)**
   - Commits any remaining files in the batch
   - Returns the CommitResult or None if no files are pending

5. **get_pending_count()**
   - Returns the number of pending files in the batch

6. **clear_pending()**
   - Clears all pending files without committing

## Sequence Diagrams

### Batch Commit Sequence

```
┌─────────┐          ┌─────────────────┐          ┌─────────────┐          ┌─────────┐
│ Client  │          │GitLabBatchCommit│          │GitLabClient │          │ GitLab  │
│         │          │      ter        │          │             │          │  API    │
└────┬────┘          └────────┬────────┘          └──────┬──────┘          └────┬────┘
     │                        │                          │                      │
     │ add_file(path,content) │                          │                      │
     │───────────────────────►│                          │                      │
     │                        │                          │                      │
     │ add_file(path,content) │                          │                      │
     │───────────────────────►│                          │                      │
     │                        │                          │                      │
     │ commit_batch(branch)   │                          │                      │
     │───────────────────────►│                          │                      │
     │                        │ batch_commit(files,msg)  │                      │
     │                        │─────────────────────────►│                      │
     │                        │                          │ create commit        │
     │                        │                          │─────────────────────►│
     │                        │                          │                      │
     │                        │                          │ commit result        │
     │                        │                          │◄─────────────────────│
     │                        │ CommitResult             │                      │
     │                        │◄─────────────────────────│                      │
     │ CommitResult           │                          │                      │
     │◄───────────────────────│                          │                      │
     │                        │                          │                      │
```

### Merge Request Sequence

```
┌─────────┐          ┌─────────────┐          ┌─────────┐
│ Client  │          │GitLabClient │          │ GitLab  │
│         │          │             │          │  API    │
└────┬────┘          └──────┬──────┘          └────┬────┘
     │                      │                      │
     │ create_merge_request │                      │
     │─────────────────────►│                      │
     │                      │ create MR            │
     │                      │─────────────────────►│
     │                      │                      │
     │                      │ MR details           │
     │                      │◄─────────────────────│
     │ MR details           │                      │
     │◄─────────────────────│                      │
     │                      │                      │
```

## Error Handling

All methods in the GitLab client handle errors from the python-gitlab library using try-except blocks with appropriate error messages. The CommitResult class provides a structured way to return success/failure information along with error details.

## Dependencies

- **python-gitlab**: Official GitLab API client for Python
- **base64**: For encoding/decoding file content
- **dataclasses**: For GitLabFile and CommitResult data classes
