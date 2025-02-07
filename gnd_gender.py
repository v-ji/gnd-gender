import argparse
import json
import random
import sys
from codecs import decode
from os import EX_IOERR, environ
from typing import Optional, Set, TypedDict

import requests
from atproto import Client
from atproto_client.utils import TextBuilder
from lxml import etree

GENDER_VOCAB_URL = "https://d-nb.info/standards/vocab/gnd/gender"
EXIT_CODE_CHANGES_DETECTED = 99


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


class GenderConceptsResult(TypedDict):
    version_iri: Optional[str]  # The stable address of the vocabulary
    added_concepts: Set[str]
    removed_concepts: Set[str]


def check_gender_concepts() -> GenderConceptsResult:
    session = create_session()

    try:
        res = session.get(GENDER_VOCAB_URL, headers={"Accept": "application/rdf+xml"})
        res.raise_for_status()  # Raise an exception for HTTP errors
        doc = etree.fromstring(res.content)
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch GND gender vocabulary: {e}")
        sys.exit(1)
    except etree.XMLSyntaxError as e:
        print(f"Failed to parse XML content: {e}")
        sys.exit(1)

    concepts_expected = {
        "https://d-nb.info/standards/vocab/gnd/gender#female",
        "https://d-nb.info/standards/vocab/gnd/gender#male",
        "https://d-nb.info/standards/vocab/gnd/gender#notKnown",
    }
    namespaces = {k: v for k, v in doc.nsmap.items() if k is not None}
    concepts = set(doc.xpath("//skos:Concept/@rdf:about", namespaces=namespaces))
    version_iri = doc.xpath(
        "//skos:ConceptScheme//owl:versionIRI/@rdf:resource", namespaces=namespaces
    )

    return {
        "version_iri": version_iri[0] if version_iri else None,
        "added_concepts": concepts - concepts_expected,
        "removed_concepts": concepts_expected - concepts,
    }


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
    # Draw from filtered pool or original pool if filtered pool is empty
    phrase = random.choice(pool_filtered or pool)
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
    recent_posts: Set[str] = set()
    if not args.dry_run:
        print("Performing ATProto login...")
        client = Client()
        # Check environment variables for login credentials
        atproto_handle, atproto_password = (
            environ.get("ATPROTO_HANDLE"),
            environ.get("ATPROTO_PASSWORD"),
        )
        if not atproto_handle:
            print("Environment variable ATPROTO_HANDLE is not set. Exiting.")
            sys.exit(1)
        if not atproto_password:
            print("Environment variable ATPROTO_PASSWORD is not set. Exiting.")
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
    gender_concepts = check_gender_concepts()
    (added_concepts, removed_concepts) = (
        gender_concepts["added_concepts"],
        gender_concepts["removed_concepts"],
    )
    has_changes = bool(added_concepts) or bool(removed_concepts)

    if not has_changes:
        print("Found no concept changes.")
        if post_negative:
            phrase = get_random_phrase(forbid=recent_posts)
            print_and_post(phrase, client)
    else:
        # IT’S HAPPENING
        indent = 4 * " "
        if added_concepts:
            print("Found unexpected concepts!")
            for concept in added_concepts:
                print(indent + concept)
        if removed_concepts:
            print("Missing expected concepts!")
            for concept in removed_concepts:
                print(indent + concept)

        if post_positive:
            url = gender_concepts["version_iri"] or GENDER_VOCAB_URL
            text = f"Maybe? {url}"
            print_and_post(text, client)

        # Exit with error code so GitHub Actions sends a notification
        sys.exit(EXIT_CODE_CHANGES_DETECTED)


if __name__ == "__main__":
    main()
