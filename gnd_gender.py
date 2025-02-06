import argparse
import sys
from os import environ

import requests
from atproto import Client, client_utils
from atproto_client.utils import TextBuilder
from lxml import etree

gender_vocab_url = "https://d-nb.info/standards/vocab/gnd/gender"


def create_parser():
    parser = argparse.ArgumentParser(
        description="Check GND gender vocabulary and post to Bluesky"
    )
    parser.add_argument(
        "--post",
        choices=["any", "positive", "negative"],
        help=(
            "Specify what outcome to post: 'positive' if new concepts are found, 'negative' if no new concepts are found, or 'any' for both"
        ),
        required=True,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not authenticate with ATProto and do not post",
    )
    return parser


def check_gender_concepts() -> set[str]:
    res = requests.get(gender_vocab_url + ".rdf")
    doc = etree.fromstring(res.content)
    concepts_expected = {
        "https://d-nb.info/standards/vocab/gnd/gender#female",
        "https://d-nb.info/standards/vocab/gnd/gender#male",
        "https://d-nb.info/standards/vocab/gnd/gender#notKnown",
    }
    namespaces = {k: v for k, v in doc.nsmap.items() if k is not None}
    concepts = set(doc.xpath("//skos:Concept/@rdf:about", namespaces=namespaces))
    return concepts - concepts_expected


def main():
    parser = create_parser()
    args = parser.parse_args()

    # Set variables based on --post choice
    post_positive = post_negative = False

    if args.post == "any":
        post_positive = post_negative = True
    elif args.post == "positive":
        post_positive = True
    elif args.post == "negative":
        post_negative = True

    client = None
    if not args.dry_run:
        print("Performing ATProto login...")
        client = Client()
        # Check environment variables for login credentials
        atproto_handle, atproto_password = (
            environ.get("ATPROTO_HANDLE"),
            environ.get("ATPROTO_PASSWORD"),
        )
        if not atproto_handle or not atproto_password:
            print(
                "Please set the environment variables ATPROTO_HANDLE and ATPROTO_PASSWORD. Exiting."
            )
            sys.exit(1)
        profile = client.login(atproto_handle, atproto_password)
        print(f"Logged in as: '${profile.display_name}'")
    else:
        print("Dry run, skipping ATProto login.")

    print("Fetching GND gender information...")
    new_concepts = check_gender_concepts()
    found_concepts = bool(new_concepts)

    if not found_concepts:
        print("Found no new concepts.")
        if post_negative:
            print_and_post("No.", client)
    else:
        print("Found unexpected concepts!")
        print("\n".join(new_concepts))
        if post_positive:
            text = client_utils.TextBuilder().link("Maybe?", gender_vocab_url)
            print_and_post(text, client)

        sys.exit(99)  # Exit with error code so GitHub Actions sends a notification


def print_and_post(text: str | TextBuilder, client: Client | None):
    # Get string representation for TextBuilder
    text_str = text if type(text) is not TextBuilder else text.build_text()

    print(f"{'Posting:' if client else 'Dry run, would post:'} '{text_str}'")
    if client:
        client.send_post(text, langs=["en"])


if __name__ == "__main__":
    main()
