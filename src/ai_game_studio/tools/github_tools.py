from git import Repo
import os
from typing import Optional
from pathlib import Path

class GitHubAutomation:
    def __init__(self, base_path: str = "./repos"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        self._repo: Optional[Repo] = None
        self.current_repo_path: Optional[Path] = None

    def setup_repository(self, repo_url: str, repo_name: str) -> bool:
        """Clone or setup a repository for automation"""
        try:
            # Insert GitHub token into the URL for authentication
            github_token = os.getenv('GITHUB_TOKEN')
            if not github_token:
                raise ValueError("GITHUB_TOKEN environment variable is not set")
                
            # Convert HTTPS URL to include token
            if repo_url.startswith('https://'):
                auth_url = repo_url.replace('https://', f'https://{github_token}@')
            else:
                auth_url = repo_url
                
            self.current_repo_path = self.base_path / repo_name
            if self.current_repo_path.exists():
                self._repo = Repo(self.current_repo_path)
                # Ensure we're up to date
                origin = self._repo.remotes.origin
                # Update the remote URL with authentication
                origin.set_url(auth_url)
                
                # Fetch all branches
                origin.fetch()
                
                # Try to determine and checkout the default branch
                try:
                    # First try to get the default branch from remote HEAD
                    default_branch = self._repo.git.symbolic_ref('refs/remotes/origin/HEAD').split('/')[-1]
                except:
                    # Fallback to 'main' or 'master'
                    for branch in ['main', 'master']:
                        if f'origin/{branch}' in [ref.name for ref in origin.refs]:
                            default_branch = branch
                            break
                    else:
                        default_branch = 'main'  # Final fallback
                
                # Force checkout the default branch
                try:
                    self._repo.git.checkout('-B', default_branch, f'origin/{default_branch}')
                except Exception as e:
                    print(f"Warning: Could not checkout default branch: {e}")
                    # Clean up any potential mess
                    self._repo.git.reset('--hard')
                    self._repo.git.clean('-fd')
            else:
                # For new clones, specify the branch
                self._repo = Repo.clone_from(auth_url, self.current_repo_path)
                # Fetch all remote branches
                origin = self._repo.remotes.origin
                origin.fetch()
            return True
        except Exception as e:
            print(f"Error setting up repository: {e}")
            return False

    def create_feature_branch(self, branch_name: str) -> bool:
        """Create and checkout a new feature branch"""
        try:
            if not self._repo:
                raise ValueError("Repository not initialized")
            
            # Get the default branch name
            default_branch = None
            for ref in self._repo.refs:
                if ref.name in ['main', 'master']:
                    default_branch = ref.name
                    break
            
            if not default_branch:
                # If neither main nor master exists, try to get the default branch from remote
                try:
                    default_branch = self._repo.active_branch.name
                except:
                    print("Could not determine default branch")
                    return False
            
            # Checkout the default branch
            self._repo.git.checkout(default_branch)
            
            # Create and checkout new branch
            if branch_name not in self._repo.refs:
                current = self._repo.create_head(branch_name)
                current.checkout()
            else:
                self._repo.git.checkout(branch_name)
            return True
        except Exception as e:
            print(f"Error creating branch: {e}")
            return False

    def commit_changes(self, commit_message: str) -> bool:
        """Stage and commit all changes"""
        try:
            if not self._repo:
                raise ValueError("Repository not initialized")
            
            # Stage all changes
            self._repo.git.add(A=True)
            
            # Only commit if there are changes
            if self._repo.is_dirty(untracked_files=True):
                self._repo.index.commit(commit_message)
                return True
            return False
        except Exception as e:
            print(f"Error committing changes: {e}")
            return False

    def push_changes(self) -> bool:
        """Push changes to remote repository"""
        try:
            if not self._repo:
                raise ValueError("Repository not initialized")
            
            current_branch = self._repo.active_branch
            origin = self._repo.remote(name='origin')
            origin.push(current_branch)
            return True
        except Exception as e:
            print(f"Error pushing changes: {e}")
            return False 