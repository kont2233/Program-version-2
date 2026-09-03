from setuptools import setup, find_packages

setup(
    name="ECPypsi",
    version="1.0.0",
    description="Raman Spectroscopy Evaluation Program",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "PySide6>=6.5",
        "matplotlib>=3.5",
        "numpy>=1.21",
        "scipy>=1.7",
        "pydantic>=2.0",
        "scikit-learn>=1.0"
    ],
    entry_points={
        "console_scripts": [
            "ecpypsi=main:main"
        ]
    }
)
