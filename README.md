# Steam Missing Cover Downloader

Downloads missing portrait covers in your library for steam beta.
Covers downloaded from steamgriddb.com

## Getting Started

### Prerequisites

Python 3.7+

Libraries:

* aiohttp
* [steam](https://github.com/ValvePython/steam)

Install using the commands:
```
pip install aiohttp
pip install steam
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



## Troubleshooting

- `ModuleNotFoundError: No module named 'google'`: check if `protobuf` Python library is installed via `pip list`, if not, run

`pip install protobuf`

- `File "asyncio\base_events.py", line 508, in _check_closed`\

  `RuntimeError: Event loop is closed`: Too many images needed to download at once? Try grabbing some images manually from `steamgriddb.com`, and placing them in `Steam\userdata\[user id]\config\grid`\

  Also try running `missing_cover_downloader.py` with the `-m` argument. Start at `20` and work down (so `missing_cover_downloader.py -m 20`, then `missing_cover_downloader.py -m 15`, etc.)

- `Cannot connect to host www.steamgriddb.com:443 ssl:default`: Your proxy settings may be preventing you from downloading images from steamgriddb. In Windows, go to *Internet Options -> Connections -> LAN settings -> Automatic configuration* and check *Automatically detect settings* and under *Proxy Server* uncheck *Use a proxy server for your LAN* 

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
