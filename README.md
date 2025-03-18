# GND, are we gender yet?

A bot to monitor the German National Library’s [GND gender vocabulary](https://d-nb.info/standards/vocab/gnd/gender.html) and check whether any new concepts have been added.
Can post updates to Bluesky and Mastodon.

## Why?

The German National Library (DNB) currently limits gender identities to only female and male in their controlled vocabulary, with a third option for “not known”.
This bot runs daily and checks for any additions to this vocabulary.

## How it works

- Fetches the GND gender vocabulary RDF file
- Checks for any concepts beyond female, male, and “not known”
- Posts result to Bluesky and/or Mastodon
- Runs daily via GitHub Actions

## Installation

This project is packaged as a [Nix](https://nixos.org/) [flake](https://nix.dev/manual/nix/2.24/command-ref/new-cli/nix3-flake.html).
You can run the application using:

```bash
nix run github:v-ji/gnd-gender -- --help
```

If you do not have flakes enabled, you must use:

```bash
nix run --extra-experimental-features "flakes nix-command" github:v-ji/gnd-gender -- --help
```

> [!NOTE]
> When using [`nix run`](https://nix.dev/manual/nix/2.24/command-ref/new-cli/nix3-run), any arguments you want to pass to the application must come after `--`.

If you would rather call the application by its command `gnd-gender`, you can enter a Nix shell:

```bash
nix shell github:v-ji/gnd-gender
gnd-gender --help
```

## Authentication

To authenticate with Bluesky and enable posting, set the following environment variables:

### Bluesky

- `ATPROTO_HANDLE`: Bluesky handle
- `ATPROTO_PASSWORD`: Bluesky [app password](https://bsky.app/settings/app-passwords)

### Mastodon

- `MASTODON_API_BASE_URL`: Base URL of your Mastodon instance
- `MASTODON_CLIENT_ID`: Mastodon client ID
- `MASTODON_CLIENT_SECRET`: Mastodon client secret
- `MASTODON_ACCESS_TOKEN`: Mastodon access token

## Usage

```
usage: gnd-gender [-h] [--platform [{bluesky,mastodon} ...]]
                  [--filter [{positive,negative} ...]] [--dry-run]

Check GND gender vocabulary and post to Bluesky and/or Mastodon

options:
  -h, --help            show this help message and exit
  --platform [{bluesky,mastodon} ...]
                        Specify the platform to post to: Bluesky, Mastodon
                        (default: None)
  --filter [{positive,negative} ...]
                        Filter outcomes to post on: positive (changes
                        detected) or negative (no changes detected) (default:
                        Post on both positive and negative outcomes)
  --dry-run             Only authenticate and fetch data, but do not post.
                        Useful for testing authentication
```

### Notes

Use `--platform` to specify whether to post to Bluesky, Mastodon, both or none.
Specifying no platform can be useful if you only want to check for changes without posting.

The `--filter` option allows the bot to check for changes every hour without flooding the feed with “No.” posts.
It posts any updates once a day without filter and only positive updates hourly with `--filter positive`.

The script exits with code `0` if no changes are detected, and with code `99` if new concepts are found.
