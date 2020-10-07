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
        "aiohttp[speedups]>=3.6.2",
        "attrs>=20.2.0",
        "beautifulsoup4>=4.9.2",
        "certifi>=2020.6.20",
        "click>=6.7",
    ],
    entry_points={
        "console_scripts": [
        ],
    },
)
