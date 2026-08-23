from setuptools import setup, find_packages

setup(
    name="emergentsh",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "PySide6>=6.6.0",
        "openai>=1.12.0",
    ],
    python_requires=">=3.10",
)