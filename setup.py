from setuptools import find_packages, setup


setup(
    name="strinks",
    version="0.0.1",
    description="Beer cost-performance monitoring",
    url="https://github.com/Zeletochoy/strinks",
    author="Antoine Lecubin",
    author_email="antoinelecubin@msn.com",
    packages=find_packages(),
    license="beerware",
    install_requires=[
        "Flask>=1.1.2",
        "attrs>=20.2.0",
        "beautifulsoup4>=4.9.2",
        "click>=6.7",
        "cloudscraper>=1.2.48",
        "editdistance>=0.5.3",
        "pykakasi>=2.0.8",
        "requests>=2.24.0",
        "sqlalchemy-stubs>=0.3",
        "sqlalchemy-utils>=0.38.2",
        "sqlalchemy>=1.3.19",
        "unidecode>=1.1.1",
    ],
    entry_points={
        "console_scripts": [
            "strinks-init-db = strinks.cli.init_db:cli",
            "strinks-scrape = strinks.cli.scrape:cli",
        ],
    },
)
