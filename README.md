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
  "task_description": "Brief title or summary of the task",
  "detailed_description": "Optional: Detailed explanation of the requirements and context",
  "repo_url": "Optional: override repo URL from env",
  "repo_name": "Optional: override repo name from env"
}
```

Response:

```json
{
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "running",
  "message": "Current status message",
  "created_at": "2024-03-20T10:30:00Z",
  "updated_at": "2024-03-20T10:35:00Z",
  "task_description": "Brief title or summary",
  "detailed_description": "Detailed explanation of requirements...",
  "branch_name": "feature/your-task-description",
  "error_detail": null
}
```

### Example Usage with JavaScript/TypeScript

```typescript
// Using fetch with detailed description
const response = await fetch("http://localhost:8000/api/tasks", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    task_description: "Add user authentication",
    detailed_description: `Implement user authentication with the following requirements:
- Use JWT tokens for session management
- Add login and registration endpoints
- Include password hashing with bcrypt
- Add rate limiting for auth endpoints
- Store user data in PostgreSQL`,
    // Optional: Override repo settings
    // repo_url: 'https://github.com/user/repo',
    // repo_name: 'repo-name'
  }),
});

const result = await response.json();

// Using axios with detailed description
import axios from "axios";

try {
  const response = await axios.post("http://localhost:8000/api/tasks", {
    task_description: "Add user authentication",
    detailed_description: `Implement user authentication with the following requirements:
- Use JWT tokens for session management
- Add login and registration endpoints
- Include password hashing with bcrypt
- Add rate limiting for auth endpoints
- Store user data in PostgreSQL`,
  });
  console.log(response.data);
} catch (error) {
  console.error("Error:", error.response?.data || error.message);
}
```

### Example: Polling for Task Completion

```typescript
async function waitForTaskCompletion(taskId: string, maxAttempts = 60) {
  for (let i = 0; i < maxAttempts; i++) {
    const response = await fetch(`http://localhost:8000/api/tasks/${taskId}`);
    const status = await response.json();

    switch (status.status) {
      case "completed":
        console.log(`Task completed! Branch: ${status.branch_name}`);
        console.log(`Original task: ${status.task_description}`);
        if (status.detailed_description) {
          console.log(`Detailed requirements:\n${status.detailed_description}`);
        }
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

// Usage example with detailed description
try {
  const createResponse = await fetch("http://localhost:8000/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task_description: "Add user authentication",
      detailed_description: `Implement user authentication with the following requirements:
- Use JWT tokens for session management
- Add login and registration endpoints
- Include password hashing with bcrypt
- Add rate limiting for auth endpoints
- Store user data in PostgreSQL`,
    }),
  });
  const { task_id } = await createResponse.json();

  // Wait for completion and get full task details
  const result = await waitForTaskCompletion(task_id);
  console.log("Task completed successfully!");
} catch (error) {
  console.error("Task failed:", error.message);
}
```

### API Documentation

Once the server is running, you can access:

- Interactive API docs: http://localhost:8000/docs
- OpenAPI specification: http://localhost:8000/openapi.json

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
