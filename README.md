# GND, are we gender yet?

Bluesky bot to monitor the German National Library’s [GND gender vocabulary](https://d-nb.info/standards/vocab/gnd/gender.html) and check whether any new concepts have been added.

## Why?

The German National Library (DNB) currently limits gender identities to only female and male in their controlled vocabulary, with a third option for “not known”.
This bot runs daily and checks for any additions to this vocabulary.

## How it works

- Fetches the GND gender vocabulary RDF file
- Checks for any concepts beyond female, male, and “not known”
- Posts result to Bluesky
- Runs daily via GitHub Actions

## Installation

```bash
pip install -r requirements.txt
```

To enable posting, set the following environment variables:

- `ATPROTO_HANDLE`: Bluesky handle
- `ATPROTO_PASSWORD`: Bluesky app password

## Usage

```
usage: gnd_gender.py [-h] --post {any,positive,negative} [--dry-run]

Check GND gender vocabulary and post to Bluesky

options:
  -h, --help            show this help message and exit
  --post {any,positive,negative}
                        Specify when to post: Only on positive outcome
                        (changes detected), only on negative outcome (no
                        changes detected), or on any outcome
  --dry-run             Do not authenticate with ATProto and do not post
```

The `--post` option allows the bot to check for changes every hour without flooding the feed with “No.” posts. It posts any updates once a day with `--post any` and only positive updates hourly with `--post positive`.

The script exits with code 0 if no changes are detected, and with code 99 if new concepts are found.
