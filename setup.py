"""Setup configuration for UnknownLang."""

from setuptools import setup

setup(
    package_dir={"": "."},
    packages=["src", "src.language", "src.execution", "src.challenge", 
              "src.oracle", "src.models", "src.benchmark"],
)
