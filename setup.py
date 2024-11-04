from setuptools import setup, find_packages

setup(
    name="ai-game-studio",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "gitpython>=3.1.41",
        "anthropic>=0.9.0",
        "python-dotenv>=1.0.1",
    ],
    python_requires=">=3.8",
) 