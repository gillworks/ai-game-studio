from pathlib import Path
from .tools.github_tools import GitHubAutomation
from openai import OpenAI
from dotenv import load_dotenv
import os
import re

# Load environment variables from .env file
load_dotenv()

# ANSI color codes for different agents
ANSI_BLUE = "\033[94m"      # Developer agent
ANSI_GREEN = "\033[92m"     # Reviewer agent
ANSI_RED = "\033[91m"       # Error messages
ANSI_YELLOW = "\033[93m"    # Warnings
ANSI_RESET = "\033[0m"
ANSI_CYAN_BG = "\033[46m"
ANSI_BLACK = "\033[30m"

# Maximum attempts for the developer agent
MAX_ATTEMPTS = 3

DEVELOPER_PROMPT = """You are an expert software developer. When modifying files:

1. COPY THE ENTIRE FILE LINE BY LINE:
   - Start with the very first line of the file
   - Copy each line exactly as it appears
   - Continue until you reach the very last line
   - Do not skip any lines
   - Do not summarize any sections
   - Do not use placeholders or comments like "existing code here" or "this stays the same"
   - Do not redact any code
   - Do not remove any existing comments unless they are related to the changes you are making

2. MAKE YOUR CHANGES:
   - Only modify the specific lines that need to change
   - Keep all other lines exactly as they are
   - Do not add comments about unchanged sections
   - Do not use placeholders or ellipsis

3. FORMAT YOUR RESPONSE:
FILE:path/to/file
```language
<ENTIRE FILE CONTENT FROM FIRST LINE TO LAST LINE>
```

ABSOLUTELY FORBIDDEN:
❌ DO NOT USE comments like:
   - "// Rest of the code remains the same"
   - "<!-- Previous code unchanged -->"
   - "/* Existing implementation */"
❌ DO NOT USE ellipsis (...) to skip code
❌ DO NOT USE placeholders or summaries
❌ DO NOT SKIP any part of the file"""

REVIEWER_PROMPT = """You are a meticulous code reviewer. Your job is to:

1. Check if the developer's changes follow ALL these rules:
   - No placeholder comments like "existing code here" or "rest of code remains the same"
   - No ellipsis (...) used to skip code
   - No summarized or abbreviated code sections
   - Complete file content is present from start to finish
   - No sections of code are missing or skipped

2. If you find ANY violations:
   - List each specific violation
   - Quote the problematic code
   - Explain why it violates the rules
   - Suggest how to fix it

3. Format your response exactly like this:
   If code passes review:
   REVIEW_PASSED: No violations found.

   If code has violations:
   REVIEW_FAILED:
   - Violation 1: <description>
     Line: <problematic code>
     Fix: <suggestion>
   - Violation 2: <description>
     Line: <problematic code>
     Fix: <suggestion>
   ...etc."""

def print_agent_message(agent_type: str, message: str):
    """Print a message with the appropriate agent color"""
    color = {
        "developer": ANSI_BLUE,
        "reviewer": ANSI_GREEN,
        "error": ANSI_RED,
        "warning": ANSI_YELLOW
    }.get(agent_type, ANSI_RESET)
    
    print(f"{color}{message}{ANSI_RESET}")

def review_changes(response: str) -> tuple[bool, str]:
    """Use GPT-4o to review the code changes"""
    try:
        print_agent_message("reviewer", "\nReviewing code changes...")
        
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        message = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": REVIEWER_PROMPT},
                {"role": "user", "content": f"Review this code change:\n\n{response}"}
            ],
            temperature=0
        )
        
        review_response = message.choices[0].message.content
        print_agent_message("reviewer", f"\nReview result:\n{review_response}")
        
        passed = review_response.startswith("REVIEW_PASSED")
        return passed, review_response
        
    except Exception as e:
        print_agent_message("error", f"\nError during code review: {str(e)}")
        return False, str(e)

def get_ai_changes(task_description: str, repo_path: Path, attempt: int = 1, previous_feedback: str = None) -> bool:
    """Use GPT-4o to implement the requested changes"""
    try:
        print("\nAttempt", attempt, "of", MAX_ATTEMPTS)  # Neutral color for system messages
        
        if attempt > MAX_ATTEMPTS:
            print_agent_message("error", "\nMaximum attempts reached. Aborting.")
            return False
        
        # If there's previous feedback, show it to the developer
        if previous_feedback:
            print_agent_message("reviewer", "\nPrevious Review Feedback:")
            print_agent_message("reviewer", previous_feedback)
            print_agent_message("developer", "\nAttempting to fix the issues...")
        
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        print("\n1. Reading repository files...")  # Neutral color for system messages
        doc_files = {}
        code_files = {}
        
        # Priority files to read first (documentation)
        priority_files = ['README.md', 'CONTRIBUTING.md', 'docs/', '.env.example']
        
        file_count = 0
        # Read priority documentation files first
        for file_pattern in priority_files:
            if '/' in file_pattern:
                # Handle directory patterns
                for file_path in repo_path.rglob(f"{file_pattern}*"):
                    if file_path.is_file():
                        try:
                            with open(file_path, 'r') as f:
                                doc_files[str(file_path.relative_to(repo_path))] = f.read()
                                file_count += 1
                                print(f"   - Read documentation file: {file_path.name}")
                        except Exception as e:
                            print_agent_message("error", f"   ⚠️  Error reading {file_path}: {e}")
            else:
                # Handle specific files
                file_path = repo_path / file_pattern
                if file_path.is_file():
                    try:
                        with open(file_path, 'r') as f:
                            doc_files[str(file_path.relative_to(repo_path))] = f.read()
                            file_count += 1
                            print(f"   - Read documentation file: {file_path.name}")
                    except Exception as e:
                        print_agent_message("error", f"   ⚠️  Error reading {file_path}: {e}")
        
        print("\n2. Reading code files...")  # Neutral color for system messages
        # Then read code files
        for file_path in repo_path.rglob('*'):
            if file_path.is_file() and file_path.suffix in ['.py', '.js', '.ts', '.jsx', '.tsx', '.css', '.html']:
                try:
                    with open(file_path, 'r') as f:
                        code_files[str(file_path.relative_to(repo_path))] = f.read()
                        file_count += 1
                        print(f"   - Read code file: {file_path.name}")
                except Exception as e:
                    print_agent_message("error", f"   ⚠️  Error reading {file_path}: {e}")

        print(f"\nTotal files read: {file_count}")  # Neutral color for system messages
        print("\n3. Preparing context for AI analysis...")  # Neutral color for system messages
        
        # Prepare the context for GPT-4 with clear sections
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

        print("\n4. Sending request to GPT-4o...")  # Neutral color for system messages
        print("   This may take a few minutes depending on the complexity of the task...")  # Neutral color for system messages
        print("   The AI is analyzing the codebase and preparing changes...")  # Neutral color for system messages
        
        # Update the task description to include previous feedback if any
        full_task = task_description
        if previous_feedback:
            full_task = f"""Task: {task_description}

Previous code review found these issues that need to be fixed:
{previous_feedback}

Please fix ALL these issues and ensure your response includes the COMPLETE file content with NO placeholders or summaries."""
        
        message = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": DEVELOPER_PROMPT},
                {"role": "user", "content": context + "\n\n" + full_task}
            ],
            temperature=0
        )

        print_agent_message("developer", "\n5. Processing AI response...")
        response = message.choices[0].message.content
        
        # Debug: Print the raw response length and content
        print_agent_message("developer", f"\nDebug - AI Response length: {len(response)} characters")
        print_agent_message("developer", f"\nAI Response:")
        print_agent_message("developer", f"{response}")
        print_agent_message("developer", f"End AI Response")
        
        # Review the changes
        passed, review_response = review_changes(response)
        if not passed:
            print_agent_message("warning", "\nCode review failed. Retrying with feedback...")
            # Retry with the review feedback
            return get_ai_changes(
                task_description,
                repo_path,
                attempt + 1,
                review_response  # Pass the review feedback to the next attempt
            )
        
        # Split response into file sections and process each one
        file_sections = response.split('FILE:')
        if len(file_sections) <= 1:
            print_agent_message("error", "No file changes found in AI response")
            return False
            
        print_agent_message("developer", "\n6. Applying changes to files...")
        changes_made = False
        
        # Skip the first empty section before 'FILE:'
        for section in file_sections[1:]:
            try:
                # Extract file path (everything up to the first code block)
                lines = section.strip().split('\n')
                file_path = lines[0].strip()
                
                # Find the code block markers
                start_marker = '```'
                end_marker = '```'
                
                content_start = section.find(start_marker)
                if content_start == -1:
                    print_agent_message("warning", f"   ⚠️  No code block found for {file_path}")
                    continue
                
                # Skip the language identifier line
                content_start = section.find('\n', content_start) + 1
                content_end = section.find(end_marker, content_start)
                
                if content_end == -1:
                    print_agent_message("warning", f"   ⚠️  Unclosed code block for {file_path}")
                    # Try to find the next FILE: marker as a fallback end point
                    next_file = section.find('\nFILE:', content_start)
                    if next_file != -1:
                        content_end = next_file
                    else:
                        # If no next FILE: marker, use the rest of the section
                        content_end = len(section)
                
                # Extract and clean the content
                new_content = section[content_start:content_end].strip()
                
                if not new_content:
                    print_agent_message("warning", f"   ⚠️  Empty content for {file_path}")
                    continue
                
                # Create the full path and ensure the directory exists
                full_path = repo_path / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write the changes
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print_agent_message("developer", f"   ✓ Updated file: {file_path}")
                changes_made = True
                
            except Exception as e:
                print_agent_message("error", f"   ⚠️  Error processing {file_path}: {str(e)}")
                continue
        
        if changes_made:
            print_agent_message("developer", "\n✨ AI implementation completed successfully!")
            return True
        else:
            print_agent_message("warning", "\n⚠️  No valid changes were made")
            return False
        
    except Exception as e:
        print_agent_message("error", f"\n❌ Error during AI implementation: {str(e)}")
        return False

def sanitize_branch_name(task_description: str) -> str:
    """Convert task description to valid branch name"""
    # Convert to lowercase and replace spaces/special chars with hyphens
    branch_name = re.sub(r'[^a-zA-Z0-9\s-]', '', task_description.lower())
    branch_name = re.sub(r'\s+', '-', branch_name.strip())
    return f"feature/{branch_name}"

def main():
    # Get task description from command line or other input method
    print("\nAI Game Studio - Developer Agent")  # Neutral color for system messages
    task_description = input("Enter the task description: ")
    
    # Initialize the automation tool
    automation = GitHubAutomation()
    
    # Get environment variables with error checking
    repo_url = os.getenv('GITHUB_REPO_URL')
    repo_name = os.getenv('GITHUB_REPO_NAME')
    
    if not repo_url or not repo_name:
        print_agent_message("error", "Error: GITHUB_REPO_URL and GITHUB_REPO_NAME must be set in .env file")
        return
    
    branch_name = sanitize_branch_name(task_description)
    
    # Setup repository
    if automation.setup_repository(repo_url, repo_name):
        print("Repository setup successful")  # Changed to neutral color
        
        # Create feature branch
        if automation.create_feature_branch(branch_name):
            print(f"Created and checked out branch: {branch_name}")  # Changed to neutral color
            
            # Implement AI-driven changes
            if get_ai_changes(task_description, automation.current_repo_path):
                print_agent_message("developer", "AI changes implemented successfully")
                
                # Commit changes
                if automation.commit_changes(f"AI Implementation: {task_description}"):
                    print_agent_message("developer", "Changes committed successfully")
                    
                    # Push changes
                    if automation.push_changes():
                        print_agent_message("developer", "Changes pushed successfully")
                    else:
                        print_agent_message("error", "Failed to push changes")
                else:
                    print_agent_message("warning", "No changes to commit or commit failed")
            else:
                print_agent_message("error", "Failed to implement AI changes")
        else:
            print_agent_message("error", "Failed to create feature branch")
    else:
        print_agent_message("error", "Failed to setup repository")

if __name__ == "__main__":
    main() 