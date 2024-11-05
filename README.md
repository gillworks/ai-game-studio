# ai-game-studio

A Python tool for automating GitHub operations, designed to help AI agents make code changes.

## Prerequisites

- Python 3.8 or higher

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/ai-game-studio.git
   cd ai-game-studio
   ```

2. Install dependencies using pip:

   ```bash
   pip install -r requirements.txt
   ```

3. Install the package in development mode:
   ```bash
   pip install -e .
   ```

## Configuration

1. Create a `.env` file in the root directory:

   ```bash
   cp .env.example .env
   ```

2. Add your GitHub Personal Access Token and OpenAI API key to the `.env` file:

   ```
   GITHUB_TOKEN=your_personal_access_token
   OPENAI_API_KEY=your_openai_api_key
   GITHUB_REPO_URL=your_repo_url
   GITHUB_REPO_NAME=your_repo_name
   ```

   To create a GitHub Personal Access Token:

   1. Go to GitHub Settings > Developer Settings > Personal Access Tokens
   2. Click "Generate New Token"
   3. Select the necessary scopes (repo, workflow)
   4. Copy the generated token

   To get an OpenAI API key:

   1. Go to OpenAI's website (https://platform.openai.com)
   2. Sign up or log in to your account
   3. Navigate to the API section
   4. Create a new API key
   5. Copy the generated key

## Usage

Run the main script:

```bash
python -m ai_game_studio.main
```

### Example Code

## API Usage

The AI Game Studio uses a distributed task queue system to handle concurrent AI operations. Here's how to set it up:

1. Start Redis (required for task queue):

   ```bash
   docker run -d -p 6379:6379 redis
   ```

2. Start one or more Celery workers:

   ```bash
   # Start a single worker
   celery -A ai_game_studio.worker worker --loglevel=info

   # Start multiple workers (recommended for concurrent tasks)
   celery -A ai_game_studio.worker worker --loglevel=info --concurrency=3
   ```

   Each worker handles one task at a time. For concurrent processing, start multiple workers.

3. Start the FastAPI server:

   ```bash
   python -m ai_game_studio.server
   ```

4. The API will be available at `http://localhost:8000`

### Architecture

The system uses a distributed architecture:

- FastAPI server: Handles HTTP requests and task management
- Redis: Message broker and result backend
- Celery workers: Process AI tasks independently
- Each worker:
  - Handles one task at a time
  - Manages its own GitHub repository clone
  - Runs LLM operations independently
  - Reports progress back to Redis

### API Endpoints

#### POST /api/tasks

Create a new AI implementation task. The task will be queued immediately and processed by an available worker.

Request body:

```json
{
  "task_description": "Your task description",
  "repo_url": "Optional: override repo URL from env",
  "repo_name": "Optional: override repo name from env"
}
```

Response:

```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "message": "Task created successfully"
}
```

#### GET /api/tasks/{task_id}

Get the status of a specific task.

Response:

```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "running", // "pending" | "running" | "completed" | "failed"
  "message": "Current status message",
  "created_at": "2024-03-20T10:30:00Z",
  "updated_at": "2024-03-20T10:35:00Z",
  "branch_name": "feature/your-task-description",
  "error_detail": null // Contains error message if status is "failed"
}
```

#### GET /api/tasks

Get a list of all tasks and their statuses.

Response:

```json
[
  {
    "task_id": "123e4567-e89b-12d3-a456-426614174000",
    "status": "completed",
    "message": "Changes implemented and pushed successfully",
    "created_at": "2024-03-20T10:30:00Z",
    "updated_at": "2024-03-20T10:35:00Z",
    "branch_name": "feature/your-task-description",
    "error_detail": null
  }
  // ... more tasks
]
```

### Task Lifecycle

Tasks go through the following states:

1. **Pending** (`status: "pending"`):

   - Initial state when task is created and queued
   - Task is waiting to be picked up by a worker
   - Message: "Task is queued"
   - No branch name or error details yet

2. **Running** (`status: "running"`):

   - Worker has started processing the task
   - AI is analyzing code and making changes
   - Message: "Processing task"
   - Branch name may be available once created
   - Progress visible in worker logs

3. **Completed** (`status: "completed"`):

   - Task finished successfully
   - Changes committed and pushed to GitHub
   - Message: "Changes implemented and pushed successfully"
   - Branch name available
   - No error details

4. **Failed** (`status: "failed"`):
   - Task encountered an error
   - Message: Description of what went wrong
   - Branch name may be available if failure occurred after branch creation
   - Error details contain specific error message

Each task maintains these timestamps:

- `created_at`: When the task was first created (never changes)
- `updated_at`: Last time the task status was checked (updates with each query)

### API Documentation

Once the server is running, you can access:

- Interactive API docs: http://localhost:8000/docs
- OpenAPI specification: http://localhost:8000/openapi.json

### Example Usage with JavaScript/TypeScript

```typescript
// Using fetch
const response = await fetch("http://localhost:8000/api/tasks", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    task_description: "Your task description",
    // Optional: Override repo settings
    // repo_url: 'https://github.com/user/repo',
    // repo_name: 'repo-name'
  }),
});

const result = await response.json();

// Using axios
import axios from "axios";

try {
  const response = await axios.post("http://localhost:8000/api/tasks", {
    task_description: "Your task description",
  });
  console.log(response.data);
} catch (error) {
  console.error("Error:", error.response?.data || error.message);
}
```

### Error Handling

The API returns appropriate HTTP status codes:

- 200: Success
- 400: Bad Request (missing or invalid parameters)
- 500: Internal Server Error

Error response format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Development Notes

1. For local development:

   - Ensure Redis is running (`docker ps` to verify)
   - Start at least one Celery worker
   - Monitor worker logs for task processing
   - Use `celery -A ai_game_studio.worker worker --loglevel=debug` for detailed logs

2. The system can be configured using environment variables:

   ```bash
   PORT=8000                    # API server port (default: 8000)
   HOST=0.0.0.0                # API server host (default: 0.0.0.0)
   REDIS_URL=redis://localhost:6379/0  # Redis connection URL
   ```

3. For production deployment, consider:

   - Using a production-grade ASGI server
   - Implementing authentication
   - Setting up rate limiting
   - Configuring HTTPS
   - Using a production Redis setup
   - Monitoring Celery workers with tools like Flower

   ```bash
   # Install Flower for Celery monitoring
   pip install flower

   # Start Flower dashboard
   celery -A ai_game_studio.worker flower
   ```

4. Scaling considerations:
   - Each worker requires:
     - ~2GB RAM (varies with LLM usage)
     - Disk space for Git operations
     - Network bandwidth for API calls
   - Monitor worker resource usage
   - Adjust number of workers based on server capacity
   - Consider using container orchestration for worker management

### Example: Polling for Task Completion

```typescript
async function waitForTaskCompletion(taskId: string, maxAttempts = 60) {
  for (let i = 0; i < maxAttempts; i++) {
    const response = await fetch(`http://localhost:8000/api/tasks/${taskId}`);
    const status = await response.json();

    switch (status.status) {
      case "completed":
        return status;
      case "failed":
        throw new Error(status.error_detail || "Task failed");
      default:
        // Task is still pending or running
        await new Promise((resolve) => setTimeout(resolve, 2000)); // Wait 2 seconds
    }
  }
  throw new Error("Task timed out");
}

// Usage
try {
  // Create task
  const createResponse = await fetch("http://localhost:8000/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task_description: "Your task description",
    }),
  });
  const { task_id } = await createResponse.json();

  // Wait for completion
  const result = await waitForTaskCompletion(task_id);
  console.log(`Task completed! Branch: ${result.branch_name}`);
} catch (error) {
  console.error("Task failed:", error.message);
}
```
