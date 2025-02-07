import argparse
import json
import random
import sys
from codecs import decode
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
            "Specify when to post: Only on positive outcome (changes detected), only on negative outcome (no changes detected), or on any outcome"
        ),
        required=True,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not authenticate with ATProto and do not post",
    )
    return parser


def create_session() -> requests.Session:
    # Set a user agent because we’re a good bot
    version = environ.get("GITHUB_SHA", "dev")[:7]  # Shorten commit hash
    user_agent = f"gnd-gender/{version} (bot; https://github.com/v-ji/gnd-gender) {requests.utils.default_user_agent()}"
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    return session


def check_gender_concepts() -> set[str]:
    session = create_session()
    res = session.get(gender_vocab_url, headers={"Accept": "application/rdf+xml"})
    doc = etree.fromstring(res.content)
    concepts_expected = {
        "https://d-nb.info/standards/vocab/gnd/gender#female",
        "https://d-nb.info/standards/vocab/gnd/gender#male",
        "https://d-nb.info/standards/vocab/gnd/gender#notKnown",
    }
    namespaces = {k: v for k, v in doc.nsmap.items() if k is not None}
    concepts = set(doc.xpath("//skos:Concept/@rdf:about", namespaces=namespaces))
    return concepts - concepts_expected


def get_random_phrase(forbid=set()) -> str:
    with open("phrases.json", "r", encoding="utf-8") as f:
        phrases = json.loads(decode(f.read(), "\u0072\u006f\u0074\u0031\u0033"))

    # Pick a phrase pool based on weights in the JSON keys
    weights = phrases.keys()
    pool = random.choices(
        list(phrases.values()),
        weights=[int(weight) for weight in weights],
    )[0]

    # Filter out forbidden phrases from the pool
    pool_filtered = [phrase for phrase in pool if phrase not in forbid]
    # Revert to original pool if filtered pool is empty
    pool_filtered = pool_filtered or pool
    phrase = random.choice(pool_filtered)
    return phrase


def print_and_post(text: str | TextBuilder, client: Client | None):
    # Get string representation for TextBuilder
    text_str = text if type(text) is not TextBuilder else text.build_text()

    print(f"{'Posting:' if client else 'Dry run, would post:'} '{text_str}'")
    if client:
        client.send_post(text, langs=["en"])


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
    recent_posts = set()
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
        print(f"Logged in as: '{profile.display_name}'")

        # Get recent posts so we can exclude them from the random phrase pool
        recent_limit = 3
        profile_feed = client.get_author_feed(
            atproto_handle, filter="posts_no_replies", limit=recent_limit
        )
        recent_posts = set(
            map(lambda x: x.post.record.text, profile_feed.feed)  # type: ignore / Types are incomplete
        )

    else:
        print("Dry run, skipping ATProto login.")

    print("Fetching GND gender information...")
    new_concepts = check_gender_concepts()
    found_concepts = bool(new_concepts)

    if not found_concepts:
        print("Found no new concepts.")
        if post_negative:
            phrase = get_random_phrase(forbid=recent_posts)
            print_and_post(phrase, client)
    else:
        # IT’S HAPPENING
        print("Found unexpected concepts!")
        print("\n".join(new_concepts))
        if post_positive:
            text = client_utils.TextBuilder().link("Maybe?", gender_vocab_url)
            print_and_post(text, client)

        sys.exit(99)  # Exit with error code so GitHub Actions sends a notification


if __name__ == "__main__":
    main()
