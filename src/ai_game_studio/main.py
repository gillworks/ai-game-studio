from pathlib import Path
from .tools.github_tools import GitHubAutomation
from anthropic import Anthropic
from dotenv import load_dotenv
import os
import re

# Load environment variables from .env file
load_dotenv()

def sanitize_branch_name(task_description: str) -> str:
    """Convert task description to valid branch name"""
    # Convert to lowercase and replace spaces/special chars with hyphens
    branch_name = re.sub(r'[^a-zA-Z0-9\s-]', '', task_description.lower())
    branch_name = re.sub(r'\s+', '-', branch_name.strip())
    return f"feature/{branch_name}"

def get_ai_changes(task_description: str, repo_path: Path) -> bool:
    """Use Claude to implement the requested changes"""
    anthropic = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    
    # First, collect documentation files
    doc_files = {}
    code_files = {}
    
    # Priority files to read first (documentation)
    priority_files = ['README.md', 'CONTRIBUTING.md', 'docs/', '.env.example']
    
    # Read priority documentation files first
    for file_pattern in priority_files:
        if '/' in file_pattern:
            # Handle directory patterns
            for file_path in repo_path.rglob(f"{file_pattern}*"):
                if file_path.is_file():
                    try:
                        with open(file_path, 'r') as f:
                            doc_files[str(file_path.relative_to(repo_path))] = f.read()
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
        else:
            # Handle specific files
            file_path = repo_path / file_pattern
            if file_path.is_file():
                try:
                    with open(file_path, 'r') as f:
                        doc_files[str(file_path.relative_to(repo_path))] = f.read()
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
    
    # Then read code files
    for file_path in repo_path.rglob('*'):
        if file_path.is_file() and file_path.suffix in ['.py', '.js', '.ts', '.jsx', '.tsx', '.css', '.html']:
            try:
                with open(file_path, 'r') as f:
                    code_files[str(file_path.relative_to(repo_path))] = f.read()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

    # Prepare the context for Claude with clear sections
    context = f"""Task: {task_description}

Repository Documentation:
-----------------------
"""
    # Add documentation files first
    for filename, content in doc_files.items():
        context += f"\nFile: {filename}\n```\n{content}\n```\n"

    context += "\nRepository Code Structure:\n-------------------------\n"
    # Add code files
    for filename, content in code_files.items():
        context += f"\nFile: {filename}\n```\n{content}\n```\n"

    # Update the system prompt to emphasize reading documentation first
    system_prompt = """You are an expert software developer. Follow these steps:
1. First, carefully read the repository documentation (README.md and other docs) to understand:
   - The project's purpose and structure
   - Any coding conventions or guidelines
   - The development workflow
2. Analyze the existing code structure and patterns
3. Implement the requested changes following the project's conventions
4. Return ONLY the file changes needed, formatted as:
   FILE:path/to/file   ```
   New content   ```
"""

    # Get AI response
    message = anthropic.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=4096,
        temperature=0,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": context + "\n\nPlease implement the requested changes following the project's conventions. Return only the file changes needed."
        }]
    )

    # Process and apply changes
    try:
        response = message.content[0].text
        file_changes = response.split('FILE:')[1:]  # Skip the first empty split
        
        for change in file_changes:
            file_path_end = change.find('\n```\n')
            file_path = change[:file_path_end].strip()
            content_start = change.find('\n```\n') + 5
            content_end = change.find('\n```', content_start)
            new_content = change[content_start:content_end]
            
            full_path = repo_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(new_content)
        
        return True
    except Exception as e:
        print(f"Error applying AI changes: {e}")
        return False

def main():
    # Get task description from command line or other input method
    task_description = input("Enter the task description: ")
    
    # Initialize the automation tool
    automation = GitHubAutomation()
    
    # Get environment variables with error checking
    repo_url = os.getenv('GITHUB_REPO_URL')
    repo_name = os.getenv('GITHUB_REPO_NAME')
    
    if not repo_url or not repo_name:
        print("Error: GITHUB_REPO_URL and GITHUB_REPO_NAME must be set in .env file")
        return
    
    branch_name = sanitize_branch_name(task_description)
    
    # Setup repository
    if automation.setup_repository(repo_url, repo_name):
        print(f"Repository setup successful")
        
        # Create feature branch
        if automation.create_feature_branch(branch_name):
            print(f"Created and checked out branch: {branch_name}")
            
            # Implement AI-driven changes
            if get_ai_changes(task_description, automation.current_repo_path):
                print("AI changes implemented successfully")
                
                # Commit changes
                if automation.commit_changes(f"AI Implementation: {task_description}"):
                    print("Changes committed successfully")
                    
                    # Push changes
                    if automation.push_changes():
                        print("Changes pushed successfully")
                    else:
                        print("Failed to push changes")
                else:
                    print("No changes to commit or commit failed")
            else:
                print("Failed to implement AI changes")
        else:
            print("Failed to create feature branch")
    else:
        print("Failed to setup repository")

if __name__ == "__main__":
    main() 