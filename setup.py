from setuptools import setup, find_packages

setup(
    name="ai-game-studio",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "gitpython>=3.1.41",
        "openai>=1.0.0",
        "python-dotenv>=1.0.1",
        "fastapi>=0.109.0",
        "uvicorn>=0.27.0",
        "pydantic>=2.0.0",
    ],
    python_requires=">=3.8",
) 