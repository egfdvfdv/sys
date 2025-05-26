from setuptools import setup, find_packages

setup(
    name="agi_prompt_system",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "typing-extensions>=4.5.0"
    ],
    python_requires=">=3.8",
)
