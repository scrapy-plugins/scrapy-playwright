import setuptools

from scrapy_playwright import __version__


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


setuptools.setup(
    name="scrapy-playwright",
    version=__version__,
    license="BSD",
    description="Playwright integration for Scrapy",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Eugenio Lacuesta",
    author_email="eugenio.lacuesta@gmail.com",
    url="https://github.com/scrapy-plugins/scrapy-playwright",
    packages=["scrapy_playwright"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Framework :: Scrapy",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.10",
    install_requires=[
        "scrapy>=2.7",
        "playwright>=1.40",
    ],
)
