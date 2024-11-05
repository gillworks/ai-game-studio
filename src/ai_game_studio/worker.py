from celery import Celery
from dotenv import load_dotenv
import os
from .main import get_ai_changes, sanitize_branch_name
from .tools.github_tools import GitHubAutomation
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize Celery
celery_app = Celery(
    'ai_game_studio',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0')
)

@celery_app.task(bind=True)
def process_task(self, task_description: str, repo_url: str = None, repo_name: str = None):
    """Celery task to process AI changes"""
    try:
        # Update task status to running
        self.update_state(
            state='RUNNING',
            meta={
                'status': 'running',
                'message': 'Processing task',
                'updated_at': datetime.utcnow().isoformat()
            }
        )

        # Use provided repo details or fall back to env vars
        repo_url = repo_url or os.getenv('GITHUB_REPO_URL')
        repo_name = repo_name or os.getenv('GITHUB_REPO_NAME')

        if not repo_url or not repo_name:
            raise ValueError("Repository URL and name must be provided")

        # Initialize automation
        automation = GitHubAutomation()
        branch_name = sanitize_branch_name(task_description)

        # Setup repository
        if not automation.setup_repository(repo_url, repo_name):
            raise RuntimeError("Failed to setup repository")

        # Create feature branch
        if not automation.create_feature_branch(branch_name):
            raise RuntimeError("Failed to create feature branch")

        # Implement AI-driven changes
        if not get_ai_changes(task_description, automation.current_repo_path):
            raise RuntimeError("Failed to implement AI changes")

        # Commit changes
        if not automation.commit_changes(f"AI Implementation: {task_description}"):
            raise RuntimeError("No changes to commit or commit failed")

        # Push changes
        if not automation.push_changes():
            raise RuntimeError("Failed to push changes")

        # Return success result
        return {
            'status': 'completed',
            'message': 'Changes implemented and pushed successfully',
            'branch_name': branch_name,
            'updated_at': datetime.utcnow().isoformat()
        }

    except Exception as e:
        # Return failure result
        return {
            'status': 'failed',
            'message': 'Task failed',
            'error_detail': str(e),
            'updated_at': datetime.utcnow().isoformat()
        } 