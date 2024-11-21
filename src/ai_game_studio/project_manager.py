from typing import List, Optional
import os
import json
from pathlib import Path
from openai import OpenAI
from .tools.github_tools import GitHubAutomation
from .worker import process_task
from celery import chain
from datetime import datetime
from .main import sanitize_branch_name, print_agent_message, ANSI_BLUE, ANSI_RED

PROJECT_MANAGER_PROMPT = """You are an expert project manager for software development. Your task is to:

1. Analyze the repository and understand its current state
2. Break down the requested project into smaller, focused tasks
3. For each task, provide:
   - A clear, concise task description
   - Detailed requirements and acceptance criteria
   - Dependencies between tasks (if any)
   - List of relevant files that will need to be modified or referenced
   - List of relevant requirements from the original project description

Format your response as a JSON array of tasks, where each task has:
- task_description: A brief title
- detailed_description: Detailed requirements and context
- dependencies: List of task numbers that must be completed first (or empty list)
- relevant_files: List of files that are relevant to this specific task
- original_requirements: List of requirements from the original project description that this task implements

Example:
[
    {
        "task_description": "Create database schema for inventory",
        "detailed_description": "Design and implement the database schema...",
        "dependencies": [],
        "relevant_files": [
            "src/models/schema.py",
            "migrations/README.md"
        ],
        "original_requirements": [
            "Items should have properties like name, description, and quantity",
            "The inventory should persist between game sessions"
        ]
    }
]"""

async def analyze_repository(repo_path: Path, key_files: Optional[List[str]] = None) -> str:
    """Analyze the repository and create a summary of its current state"""
    try:
        summary = []
        
        # Define default key files if none provided
        if not key_files:
            key_files = [
                'README.md'
            ]
        
        # Analyze specified key files
        summary.append("Analysis of key files:")
        for file_path in key_files:
            full_path = repo_path / file_path
            if full_path.exists():
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    summary.append(f"\nContents of {file_path}:\n{content}\n")
            else:
                summary.append(f"\nNote: Key file {file_path} not found\n")
        
        return "\n".join(summary)
        
    except Exception as e:
        print_agent_message("error", f"Error analyzing repository: {e}")
        return str(e)

async def create_subtasks(
    project_id: str,
    project_name: str,
    project_description: str,
    repo_url: str = None,
    repo_name: str = None,
    key_files: Optional[List[str]] = None
) -> List[str]:
    """Break down a project into smaller tasks and create them"""
    try:
        # Use provided repo details or fall back to env vars
        repo_url = repo_url or os.getenv('GITHUB_REPO_URL')
        repo_name = repo_name or os.getenv('GITHUB_REPO_NAME')
        
        if not repo_url or not repo_name:
            raise ValueError("Repository URL and name must be provided")
        
        # Initialize automation and analyze repo
        automation = GitHubAutomation()
        if not automation.setup_repository(repo_url, repo_name):
            raise RuntimeError("Failed to setup repository")
        
        print_agent_message("developer", "Analyzing repository...")
        
        # Analyze the repository
        repo_analysis = await analyze_repository(automation.current_repo_path, key_files)
        
        # Create the full context for the AI
        context = f"""Project Request: {project_description}

Repository Analysis:
{repo_analysis}

Please break this project down into smaller, focused tasks that can be implemented independently where possible."""
        
        # Use GPT-4o to break down the project - with consistent timeout handling
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        print(f"GPT-4o Breaking down project into tasks...")
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": PROJECT_MANAGER_PROMPT},
                    {"role": "user", "content": context}
                ],
                temperature=0,
                timeout=30
            )
            print("Received response from OpenAI API")
            
            # Parse the response into tasks with better error handling
            try:
                response_content = response.choices[0].message.content
                print_agent_message("developer", f"GPT Response:\n{response_content}")
                
                # Clean up the response if it contains markdown code blocks
                if response_content.startswith('```'):
                    content_lines = response_content.split('\n')
                    content_lines = [line for line in content_lines 
                                   if not line.startswith('```')]
                    response_content = '\n'.join(content_lines)
                
                tasks = json.loads(response_content)
                
            except json.JSONDecodeError as e:
                print_agent_message("error", f"JSON Parse Error: {e}")
                print_agent_message("error", f"Raw response:\n{response_content}")
                raise RuntimeError(f"Failed to parse GPT response as JSON: {e}")
            
        except Exception as api_error:
            print_agent_message("error", f"OpenAI API Error: {str(api_error)}")
            raise RuntimeError(f"OpenAI API request failed: {str(api_error)}")
        
        if not isinstance(tasks, list):
            raise ValueError(f"Expected list of tasks, got {type(tasks)}")
            
        # Validate task format
        for i, task in enumerate(tasks):
            required_fields = ['task_description', 'detailed_description', 'dependencies']
            missing_fields = [f for f in required_fields if f not in task]
            if missing_fields:
                raise ValueError(f"Task {i} is missing required fields: {missing_fields}")
        
        # Create a mapping of task index to Celery task
        task_mapping = {}
        subtask_ids = []
        
        # Create a cleaner feature branch name using project name
        sanitized_name = sanitize_branch_name(project_name).replace('feature/', '')
        project_branch = f"feature/{sanitized_name}-{project_id[:8]}"
        
        # First pass: Create all tasks but don't start them
        for i, task in enumerate(tasks):
            # Build comprehensive detailed description
            detailed_desc_parts = []
            
            # Add original task description
            detailed_desc_parts.append(f"Task: {task['task_description']}\n")
            
            # Add task's detailed requirements
            detailed_desc_parts.append(f"Requirements:\n{task['detailed_description']}\n")
            
            # Add original requirements this task implements
            if task.get('original_requirements'):
                detailed_desc_parts.append("\nImplementing these requirements from the original project description:")
                for req in task['original_requirements']:
                    detailed_desc_parts.append(f"- {req}")
                detailed_desc_parts.append("")
            
            # Add relevant files
            if task.get('relevant_files'):
                detailed_desc_parts.append("\nRelevant files to consider:")
                for f in task['relevant_files']:
                    detailed_desc_parts.append(f"- {f}")
            
            # Combine all parts
            detailed_desc = "\n".join(detailed_desc_parts)
            
            # Get relevant files for this task
            task_files = task.get('relevant_files', key_files or [])
            
            signature = process_task.signature(
                (
                    task['task_description'],
                    detailed_desc,
                    repo_url,
                    repo_name,
                    project_branch,
                    task_files  # Pass the relevant files
                ),
                immutable=True
            )
            task_mapping[i] = signature
        
        # Second pass: Chain tasks based on dependencies
        for i, task in enumerate(tasks):
            if not task['dependencies']:
                # No dependencies - can start immediately
                result = task_mapping[i].delay()
                subtask_ids.append(result.id)
            else:
                # Create a chain of dependent tasks
                dependent_tasks = [task_mapping[dep] for dep in task['dependencies']]
                # Add the current task to the end of its dependencies
                task_chain = chain(dependent_tasks + [task_mapping[i]])
                result = task_chain.delay()
                subtask_ids.append(result.id)
        
        # Store the project information
        from .api import project_timestamps, project_subtasks
        project_timestamps[project_id] = datetime.utcnow()
        project_subtasks[project_id] = subtask_ids
        
        return subtask_ids
        
    except Exception as e:
        print_agent_message("error", f"Error creating subtasks: {e}")
        raise