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

- `ATPROTO_HANDLE`: Bluesky handle
- `ATPROTO_PASSWORD`: Bluesky [app password](https://bsky.app/settings/app-passwords)

## Usage

```
usage: gnd-gender [-h] --post {any,positive,negative} [--dry-run]

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

The script exits with code `0` if no changes are detected, and with code `99` if new concepts are found.
