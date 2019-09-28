# Steam Missing Cover Downloader

Downloads missing portrait covers in your library for steam beta.
Covers downloaded from steamgriddb.com

## Getting Started

### Prerequisites

Python 3.7+

Libraries:
*BeautifulSoup
*aiohttp
*[steam](https://github.com/ValvePython/steam)
Note: steam 1.0.0alpha required, PyPI only has 0.9.1
Install using the following command:
```
pip install git+https://github.com/ValvePython/steam#egg=steam
```

### Running

```
python missing_cover_downloader.py
```

## Update History
1.0.0 
*Initial release

1.2.0
*Add support to read data from local appcache.
*Fixed an issue that steamgriddb stopped returning correct covers
*Added Mac support (Thanks to [UKMeng](https://github.com/UKMeng))

1.5.0
*Significantly imporves performance using asychronous requests
*Refactored code
*Added Linux support (Thanks to [KrystianoXPL](https://github.com/KrystianoXPL))
*Fixed a bug that some games in library are not returned.
*Fixed a bug that games in appcache but not in game library are returned.

