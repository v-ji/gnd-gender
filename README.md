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

## Setup

1. Set repository secrets:
   - `ATPROTO_HANDLE`: Your Bluesky handle
   - `ATPROTO_PASSWORD`: Your Bluesky app password

## Running locally

```bash
export ATPROTO_HANDLE="your.handle"
export ATPROTO_PASSWORD="your-app-password"
python gnd_gender.py
```
