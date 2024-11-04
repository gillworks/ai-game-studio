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

2. Add your GitHub Personal Access Token and Anthropic API key to the `.env` file:

   ```
   GITHUB_TOKEN=your_personal_access_token
   ANTHROPIC_API_KEY=your_anthropic_api_key
   GITHUB_REPO_URL=your_repo_url
   GITHUB_REPO_NAME=your_repo_name
   ```

   To create a GitHub Personal Access Token:

   1. Go to GitHub Settings > Developer Settings > Personal Access Tokens
   2. Click "Generate New Token"
   3. Select the necessary scopes (repo, workflow)
   4. Copy the generated token

## Usage

Run the main script:

```bash
python -m ai_game_studio.main
```

### Example Code
