"""
setup.py - Installation de dmonSQL
"""

from setuptools import setup, find_packages
import os

# Lire le README
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Lire les requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="dmonSQL",
    version="1.0.0",
    author="Edmonico Velonjara",
    author_email="edmonicovelonjara493@gmail.com",
    description="Système de Gestion de Base de Données Relationnelle en Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Edmonico09/dmonSQL",
    packages=find_packages(exclude=["tests", "examples"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Database",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
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
            "cryptography>=3.0",
            "lz4>=3.0",
            "matplotlib>=3.0",  # Pour les visualisations
            "pandas>=1.0",  # Pour l'import/export
        ],
    },
    entry_points={
        "console_scripts": [
            "dmonSQL=dmonSQL.cli.shell:main",
            "dmonSQL-server=dmonSQL.network.server:main",
        ],
    },
    include_package_data=True,
    package_data={
        "dmonSQL": ["data/templates/*", "data/config/*.ini"],
    },
    zip_safe=False,
    keywords="database relational sql nosql matrix json",
    project_urls={
        "Bug Reports": "https://github.com/dmonSQL/dmonSQL/issues",
        "Documentation": "https://dmonSQL.readthedocs.io",
        "Source": "https://github.com/dmonSQL/dmonSQL",
    },
)
