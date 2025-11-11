from setuptools import setup, find_packages

setup(
    name="herald",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "arxiv>=1.4.8",
        "nltk>=3.8.1",
        "sentence-transformers>=2.2.2",
        "torch>=2.1.0",
        "scikit-learn>=1.3.0",
        "numpy>=1.24.3",
        "requests>=2.31.0",
        "pyyaml>=6.0",
    ],
    python_requires=">=3.8",
    entry_points={
        'console_scripts': [
            'herald=src.pipeline:main',
        ],
    },
) 