# Steam Missing Cover Downloader

Downloads missing portrait covers in your library for steam beta.
Covers downloaded from steamgriddb.com

## Getting Started

### Prerequisites

Python 3.7+

Libraries:

* aiohttp
* [steam](https://github.com/ValvePython/steam)
Note: steam 1.0.0alpha required, PyPI only has 0.9.1
Install using the following command:
```
pip install git+https://github.com/ValvePython/steam#egg=steam
```

### Running

```
python missing_cover_downloader.py
```

#### Command Line Options
```
usage: missing_cover_downloader.py [-h] [-l] [-r] [-m MIN_SCORE] [-s STYLES]
                                   [-o] [-d]

Downloads missing covers for new steam UI. Covers are downloaded from
steamgriddb.com

optional arguments:
  -h, --help            show this help message and exit
  -l, --local           Local mode, this is the default operation.
  -r, --remote          Remote mode, if both local and remote are specified,
                        will try local mode first.
  -m MIN_SCORE, --minscore MIN_SCORE
                        Set min score for a cover to be downloaded.
  -s STYLES, --styles STYLES
                        Set styles of cover, can be comma separated list of
                        alternate, blurred, white_logo, material or no_logo.
  -o, --overwrite       Overwrite covers that are already present in local
                        steam grid path.
  -d, --delete-local    Delete local covers for games that already have
                        official ones.
```

## Update History
1.0.0 
* Initial release

1.2.0
* Added support to read data from local appcache.
* Fixed an issue that steamgriddb stopped returning correct covers
* Added Mac support (Thanks to [UKMeng](https://github.com/UKMeng))

1.5.0
* Significantly imporves performance using asychronous requests
* Refactored code
* Added Linux support (Thanks to [KrystianoXPL](https://github.com/KrystianoXPL))
* Fixed a bug that some games in library are not returned.
* Fixed a bug that games in appcache but not in game library are returned.

1.6.0
* The script now uses SGDB API 2.3.0, which supports filtering by size. Scrapping the site is no longer needed.
* Added support for switching between local and remote mode.
* Added support to set the minimum score for a cover to be downloaded.

1.6.2
* Added option to overwrite existing covers.
* Added option to select cover styles.
* Added option to delete custom covers when official covers are available.