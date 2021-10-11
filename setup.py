import setuptools

from scrapy_playwright import __version__


with open("README.md", "r") as fh:
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
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Framework :: Scrapy",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    install_requires=[
        "scrapy>=2.0,!=2.4.0",
        "playwright>=1.8.0a1",
    ],
)
