from setuptools import setup, find_packages

setup(
    name="herald",
    version="0.3.0",
    packages=find_packages(),
    install_requires=[
        "sentence-transformers>=2.2.2",
        "torch>=2.1.0",
        "scikit-learn>=1.3.0",
        "numpy>=1.24.3",
        "requests>=2.31.0",
        "pyyaml>=6.0",
        "fastapi>=0.110.0",
        "uvicorn>=0.29.0",
        "feedparser>=6.0.10",
        "beautifulsoup4>=4.12.0",
    ],
    python_requires=">=3.9",
)
