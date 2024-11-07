from setuptools import setup, find_packages


with open("README.md", "r", encoding="utf-8") as f:
    more_description = f.read()


setup(
    name="fsm",
    version="2.2.5",
    author="Antonio Rodrigues",
    author_email="antonio.projects.studio@gmail.com",
    description="Library for working with finite state machines",
    long_description=more_description,
    long_description_content_type="text/markdown",
    url="https://github.com/antonio-projects-studio/fsm",
    packages=find_packages(),
    install_requires=[
        "PyYAML",
        "python-frontmatter",
        "terminal_app @ git+https://github.com/antonio-projects-studio/terminal_app.git@75591667384f3789445c181935be56a6ba63105c",
        "markdown_reader @ git+https://github.com/antonio-projects-studio/markdown_reader.git@b8cec46c192a68346f63fb8b5bd5efd7afc1be61",
    ],
)
