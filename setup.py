from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="ai-benchmark",
    version="1.0.0",
    description="Cross-platform AI system benchmark — compare hardware, not models",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    install_requires=[
        "typer>=0.12.0",
        "ollama>=0.4.0",
        "psutil>=5.9.0",
        "requests>=2.31.0",
        "rich>=13.7.0",
    ],
    entry_points={
        "console_scripts": [
            "ai-benchmark = ai_benchmark.cli:app",
        ],
    },
)
