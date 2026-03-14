from setuptools import setup, find_packages

setup(
    name="k8s-aiagent",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "langgraph",
        "kubernetes",
        "pydantic",
        "python-dotenv",
        "requests"
    ],
    python_requires=">=3.12",
)