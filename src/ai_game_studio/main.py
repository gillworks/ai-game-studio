from pathlib import Path
from .tools.github_tools import GitHubAutomation
from anthropic import Anthropic
from dotenv import load_dotenv
import os
import re

# Load environment variables from .env file
load_dotenv()

# Add these constants at the top with other imports
ANSI_BLUE = "\033[94m"
ANSI_RESET = "\033[0m"
ANSI_CYAN_BG = "\033[46m"
ANSI_BLACK = "\033[30m"

# Add this after the imports and before the functions
SYSTEM_PROMPT = """You are an expert software developer. When modifying files:

1. COPY THE ENTIRE FILE LINE BY LINE:
   - Start with the very first line of the file
   - Copy each line exactly as it appears
   - Continue until you reach the very last line
   - Do not skip any lines
   - Do not summarize any sections
   - Do not use placeholders or comments like "existing code here" or "this stays the same"
   - Do not redact any code

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
❌ DO NOT SKIP any part of the file

Example - INCORRECT:
FILE:game.html
```html
<div id="status-bar">
    <!-- Previous status elements -->
    <div>New Element: <span id="new-value"></span></div>
    <!-- Rest of the status bar -->
</div>
```

Example - CORRECT:
FILE:game.html
```html
<div id="status-bar">
    <div>Health: <span id="health">100</span></div>
    <div>Score: <span id="score">0</span></div>
    <div>Position: (<span id="position-x">0</span>, <span id="position-y">0</span>)</div>
    <div>New Element: <span id="new-value"></span></div>
    <div>Player: <span id="player-name">Player1</span></div>
</div>
```

Remember: The output must be an EXACT copy of the original file with ONLY your specific changes applied. Every single line must be present."""

def sanitize_branch_name(task_description: str) -> str:
    """Convert task description to valid branch name"""
    # Convert to lowercase and replace spaces/special chars with hyphens
    branch_name = re.sub(r'[^a-zA-Z0-9\s-]', '', task_description.lower())
    branch_name = re.sub(r'\s+', '-', branch_name.strip())
    return f"feature/{branch_name}"

def get_ai_changes(task_description: str, repo_path: Path) -> bool:
    """Use Claude to implement the requested changes"""
    try:
        print("\nStarting AI implementation process...")
        
        anthropic = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        
        print("1. Reading repository files...")
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
                            print(f"   ⚠️  Error reading {file_path}: {e}")
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
                        print(f"   ⚠️  Error reading {file_path}: {e}")
        
        print("\n2. Reading code files...")
        # Then read code files
        for file_path in repo_path.rglob('*'):
            if file_path.is_file() and file_path.suffix in ['.py', '.js', '.ts', '.jsx', '.tsx', '.css', '.html']:
                try:
                    with open(file_path, 'r') as f:
                        code_files[str(file_path.relative_to(repo_path))] = f.read()
                        file_count += 1
                        print(f"   - Read code file: {file_path.name}")
                except Exception as e:
                    print(f"   ⚠️  Error reading {file_path}: {e}")

        print(f"\nTotal files read: {file_count}")
        print("\n3. Preparing context for AI analysis...")
        
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

        print("\n4. Sending request to Claude...")
        print("   This may take a few minutes depending on the complexity of the task...")
        print("   The AI is analyzing the codebase and preparing changes...")
        
        # Increase max_tokens for larger responses
        message = anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8192,  # Increased from 4096
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": context + "\n\nPlease implement the requested changes following the project's conventions. Return only the file changes needed."
            }]
        )

        print("\n5. Processing AI response...")
        response = message.content[0].text
        
        # Debug: Print the raw response length and content
        print(f"\nDebug - AI Response length: {len(response)} characters")
        print(f"\n{ANSI_CYAN_BG}{ANSI_BLACK}AI Response:{ANSI_RESET}")
        print(f"{ANSI_BLUE}{response}{ANSI_RESET}")
        print(f"\n{ANSI_CYAN_BG}{ANSI_BLACK}End AI Response{ANSI_RESET}")
        
        # Split response into file sections and process each one
        file_sections = response.split('FILE:')
        if len(file_sections) <= 1:
            print("No file changes found in AI response")
            return False
            
        print("\n6. Applying changes to files...")
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
                    print(f"   ⚠️  No code block found for {file_path}")
                    continue
                
                # Skip the language identifier line
                content_start = section.find('\n', content_start) + 1
                content_end = section.find(end_marker, content_start)
                
                if content_end == -1:
                    print(f"   ⚠️  Unclosed code block for {file_path}")
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
                    print(f"   ⚠️  Empty content for {file_path}")
                    continue
                
                # Create the full path and ensure the directory exists
                full_path = repo_path / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write the changes
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"   ✓ Updated file: {file_path}")
                changes_made = True
                
            except Exception as e:
                print(f"   ⚠️  Error processing {file_path}: {str(e)}")
                continue
        
        if changes_made:
            print("\n✨ AI implementation completed successfully!")
            return True
        else:
            print("\n⚠️  No valid changes were made")
            return False
        
    except Exception as e:
        print(f"\n❌ Error during AI implementation: {str(e)}")
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