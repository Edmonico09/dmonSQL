"""
setup.py - Installation de dmonSQL
"""
from setuptools import setup, find_packages
import os

# Lire le README
try:
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()
except FileNotFoundError:
    long_description = "Système de Gestion de Base de Données Relationnelle en Python"

# Lire les requirements
try:
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]
except FileNotFoundError:
    requirements = ["numpy>=1.19.0"]

setup(
    name="dmonSQL",
    version="1.0.0",
    author="Edmonico Velonjara",
    author_email="contact@dmonsql.dev",
    description="Système de Gestion de Base de Données Relationnelle en Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dmonsql/dmonsql",
    packages=find_packages(exclude=["tests", "examples"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Database",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.9",
            "mypy>=0.910",
        ],
        "full": [
            "cryptography>=3.0",
            "lz4>=3.0",
            "matplotlib>=3.0",
            "pandas>=1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            # Fixed: Points to the actual main function in your dmonsql_main.py
            "dmonsql=dmonSQL.dmonsql_main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "dmonSQL": ["data/templates/*", "data/config/*.ini"],
    },
    zip_safe=False,
    keywords="database relational sql nosql matrix json",
    project_urls={
        "Bug Reports": "https://github.com/dmonsql/dmonsql/issues",
        "Documentation": "https://dmonsql.readthedocs.io",
        "Source": "https://github.com/dmonsql/dmonsql",
    },
)