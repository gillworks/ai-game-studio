from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Literal, Dict, List
from datetime import datetime
import uuid
from .worker import celery_app, process_task
from .project_manager import create_subtasks

app = FastAPI(
    title="AI Game Studio API",
    description="API for automating GitHub operations with AI",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for task creation times
task_timestamps = {}

# Add at the top with other storage
project_timestamps = {}  # Store project creation times
project_subtasks = {}   # Store mapping of project_id to subtask_ids

# Add new models
class TaskRequest(BaseModel):
    task_description: str
    detailed_description: Optional[str] = None
    repo_url: Optional[str] = None
    repo_name: Optional[str] = None

class TaskResponse(BaseModel):
    task_id: str
    message: str

class TaskStatus(BaseModel):
    task_id: str
    status: Literal["pending", "running", "completed", "failed"]
    message: str
    created_at: datetime
    updated_at: datetime
    task_description: str
    detailed_description: Optional[str] = None
    branch_name: Optional[str] = None
    error_detail: Optional[str] = None

class ProjectTaskRequest(BaseModel):
    project_name: str
    project_description: str
    repo_url: Optional[str] = None
    repo_name: Optional[str] = None
    key_files: Optional[List[str]] = None

class ProjectTaskResponse(BaseModel):
    project_id: str
    subtask_ids: list[str]
    message: str

# Add new endpoint
@app.post("/api/project-tasks", response_model=ProjectTaskResponse)
async def create_project_task(request: ProjectTaskRequest):
    """Create a new project task that will be broken down into smaller tasks"""
    try:
        # Generate a project ID
        project_id = str(uuid.uuid4())
        
        # Use the project manager to create subtasks
        subtask_ids = await create_subtasks(
            project_id=project_id,
            project_name=request.project_name,
            project_description=request.project_description,
            repo_url=request.repo_url,
            repo_name=request.repo_name,
            key_files=request.key_files
        )
        
        return ProjectTaskResponse(
            project_id=project_id,
            subtask_ids=subtask_ids,
            message="Project tasks created successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Add project status endpoint
@app.get("/api/project-tasks/{project_id}")
async def get_project_status(project_id: str):
    """Get the status of all subtasks in a project"""
    if project_id not in project_timestamps:
        raise HTTPException(status_code=404, detail="Project not found")
    
    subtask_ids = project_subtasks.get(project_id, [])
    subtask_statuses = []
    
    for task_id in subtask_ids:
        status = await get_task_status(task_id)
        subtask_statuses.append(status)
    
    return {
        "project_id": project_id,
        "created_at": project_timestamps[project_id],
        "updated_at": datetime.utcnow(),
        "subtasks": subtask_statuses
    }

def get_task_status_info(task_id: str, created_time: datetime) -> Dict:
    """Helper function to get consistent task status information"""
    task = celery_app.AsyncResult(task_id)
    
    if task.state == 'PENDING':
        return {
            'status': 'pending',
            'message': 'Task is queued',
            'branch_name': None,
            'error_detail': None
        }
    elif task.state == 'RUNNING':
        info = task.info or {}
        return {
            'status': 'running',
            'message': info.get('message', 'Task is running'),
            'branch_name': info.get('branch_name'),
            'error_detail': info.get('error_detail')
        }
    elif task.state == 'SUCCESS':
        result = task.get()
        return {
            'status': result.get('status', 'completed'),
            'message': result.get('message', 'Task completed'),
            'branch_name': result.get('branch_name'),
            'error_detail': result.get('error_detail')
        }
    else:  # FAILURE or other states
        return {
            'status': 'failed',
            'message': str(task.info) if task.info else 'Task failed',
            'branch_name': None,
            'error_detail': str(task.info) if task.info else None
        }

@app.get("/")
async def root():
    """Redirect root to API documentation"""
    return RedirectResponse(url="/docs")

@app.post("/api/tasks", response_model=TaskResponse)
async def create_task(request: TaskRequest):
    """Create a new task and return its ID immediately"""
    # Start Celery task first to get its ID
    celery_task = process_task.delay(
        request.task_description,
        request.detailed_description,
        request.repo_url,
        request.repo_name
    )
    
    task_id = celery_task.id
    # Store creation timestamp and task details
    task_timestamps[task_id] = {
        'created_at': datetime.utcnow(),
        'task_description': request.task_description,
        'detailed_description': request.detailed_description
    }

    return TaskResponse(
        task_id=task_id,
        message="Task created successfully"
    )

@app.get("/api/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get the status of a specific task"""
    if task_id not in task_timestamps:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_info = task_timestamps[task_id]
    status_info = get_task_status_info(task_id, task_info['created_at'])
    
    return TaskStatus(
        task_id=task_id,
        created_at=task_info['created_at'],
        updated_at=datetime.utcnow(),
        task_description=task_info['task_description'],
        detailed_description=task_info['detailed_description'],
        **status_info
    )

@app.get("/api/tasks", response_model=list[TaskStatus])
async def list_tasks():
    """Get a list of all active tasks and their statuses"""
    all_tasks = []
    
    for task_id, task_info in task_timestamps.items():
        status_info = get_task_status_info(task_id, task_info['created_at'])
        
        all_tasks.append(TaskStatus(
            task_id=task_id,
            created_at=task_info['created_at'],
            updated_at=datetime.utcnow(),
            task_description=task_info['task_description'],
            detailed_description=task_info['detailed_description'],
            **status_info
        ))
    
    return all_tasks

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}