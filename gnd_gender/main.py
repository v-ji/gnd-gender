import argparse
import json
import logging
import random
import sys
from codecs import decode
from enum import Enum
from os import environ, path
from typing import Optional, Set, TypedDict, Union, cast

import requests
from atproto import Client
from lxml import etree
from mastodon import Mastodon

# Constants
GENDER_VOCAB_URL = "https://d-nb.info/standards/vocab/gnd/gender"
EXIT_CODE_CHANGES_DETECTED = 99


class Platform(Enum):
    BLUESKY = "bluesky"
    MASTODON = "mastodon"


logging.basicConfig(format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def create_parser():
    parser = argparse.ArgumentParser(
        description="Check GND gender vocabulary and post to Bluesky and/or Mastodon"
    )
    parser.add_argument(
        "--platform",
        choices=[p.value for p in Platform],
        default=None,
        nargs="*",
        help="Specify the platform to post to: Bluesky, Mastodon (default: %(default)s)",
    )
    parser.add_argument(
        "--filter",
        choices=["positive", "negative"],
        default=["positive", "negative"],
        nargs="*",
        help=(
            """
            Filter outcomes to post on: positive (changes detected) or negative (no changes detected)
            (default: Post on both positive and negative outcomes)
            """
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only authenticate and fetch data, but do not post. Useful for testing authentication",
    )
    return parser


def create_session() -> requests.Session:
    # Set a user agent because we’re a good bot
    version = environ.get("GITHUB_SHA", "dev")[:7]  # Shorten commit hash
    user_agent = f"gnd-gender/{version} (bot; https://github.com/v-ji/gnd-gender) {requests.utils.default_user_agent()}"
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    return session


def get_required_env_vars(platform: Platform) -> dict[str, str]:
    """
    Get all required environment variables for a specific platform.
    Exits the program if any required variable is missing.
    """
    required_vars = {
        Platform.BLUESKY: ["ATPROTO_HANDLE", "ATPROTO_PASSWORD"],
        Platform.MASTODON: [
            "MASTODON_API_BASE_URL",
            "MASTODON_CLIENT_ID",
            "MASTODON_CLIENT_SECRET",
            "MASTODON_ACCESS_TOKEN",
        ],
    }

    result = {}
    platform_vars = required_vars.get(platform, [])

    for var_name in platform_vars:
        value = environ.get(var_name)
        if not value:
            logger.error(
                f"Required environment variable {var_name} for {platform.value} is not set. Exiting."
            )
            sys.exit(1)
        result[var_name] = value

    return result


def setup_platform_clients(
    platforms: list[Platform],
) -> dict[Platform, Union[Client, Mastodon]]:
    """
    Setup clients for each requested platform with proper validation of environment variables.
    Returns a dictionary of clients keyed by Platform enum.
    """
    clients = {}

    for platform in platforms:
        env_vars = get_required_env_vars(platform)
        logger.info(f"({platform.value}) Performing login...")

        if platform == Platform.BLUESKY:
            client = Client()
            profile = client.login(
                env_vars["ATPROTO_HANDLE"], env_vars["ATPROTO_PASSWORD"]
            )
            clients[platform] = client
            logger.info(
                f"({platform.value}) Logged in as: '{profile.display_name}' ({profile.handle})"
            )

        elif platform == Platform.MASTODON:
            client = Mastodon(
                api_base_url=env_vars["MASTODON_API_BASE_URL"],
                client_id=env_vars["MASTODON_CLIENT_ID"],
                client_secret=env_vars["MASTODON_CLIENT_SECRET"],
                access_token=env_vars["MASTODON_ACCESS_TOKEN"],
            )
            clients[platform] = client
            profile = client.me()
            logger.info(
                f"({platform.value}) Logged in as: '{profile.display_name}' (@{profile.acct})"
            )

    return clients


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
        logger.error(f"Failed to fetch GND gender vocabulary: {e}")
        sys.exit(1)
    except etree.XMLSyntaxError as e:
        logger.error(f"Failed to parse XML content: {e}")
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
    script_dir = path.dirname(path.abspath(__file__))
    phrases_path = path.join(script_dir, "phrases.json")

    with open(phrases_path, "r", encoding="utf-8") as f:
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


def get_recent_posts(clients: dict[Platform, Union[Client, Mastodon]]) -> set[str]:
    # Get recent posts so we can exclude them from the random phrase pool (if Bluesky is available)
    recent_posts: Set[str] = set()
    if Platform.BLUESKY in clients:
        atproto_client = cast(Client, clients[Platform.BLUESKY])

        recent_limit = 3
        atproto_handle = environ.get("ATPROTO_HANDLE")
        if not atproto_handle:
            raise ValueError("ATPROTO_HANDLE environment variable is not set.")

        profile_feed = atproto_client.get_author_feed(
            atproto_handle, filter="posts_no_replies", limit=recent_limit
        )
        recent_posts = set(
            map(lambda x: x.post.record.text, profile_feed.feed)  # type: ignore / Types are incomplete
        )
    return recent_posts


def print_and_post(
    text: str, clients: dict[Platform, Union[Client, Mastodon]], dry_run=False
):
    logger.info(f"Verdict: '{text}'")
    if dry_run:
        logger.info("Dry run enabled. Skipping post.")
        return

    for platform, client in clients.items():
        if platform == Platform.BLUESKY:
            atproto_client = cast(Client, client)
            atproto_client.send_post(text, langs=["en"])

        elif platform == Platform.MASTODON:
            mastodon_client = cast(Mastodon, client)
            mastodon_client.status_post(text, language="en")

        logger.info(f"({platform.value}) Post sent.")


def main():
    parser = create_parser()
    args = parser.parse_args()

    # Set variables based on --filter choice
    post_positive = "positive" in args.filter
    post_negative = "negative" in args.filter

    # Convert platform strings from args to Platform enum values
    platforms = [Platform(p) for p in args.platform] if args.platform else []

    logger.info("Fetching GND gender information...")
    gender_concepts = check_gender_concepts()
    (added_concepts, removed_concepts) = (
        gender_concepts["added_concepts"],
        gender_concepts["removed_concepts"],
    )
    has_changes = bool(added_concepts) or bool(removed_concepts)

    # Setup clients for selected platforms
    clients = setup_platform_clients(platforms)

    phrase = ""
    if not has_changes:
        logger.info("Found no concept changes.")
        if post_negative:
            recent_posts = get_recent_posts(clients)
            phrase = get_random_phrase(forbid=recent_posts)
    else:
        # IT’S HAPPENING
        if added_concepts:
            logger.info("Found unexpected concepts!")
            for concept in added_concepts:
                logger.info(f"    - {concept}")
        if removed_concepts:
            logger.info("Missing expected concepts!")
            for concept in removed_concepts:
                logger.info(f"    - {concept}")

        if post_positive:
            url = gender_concepts["version_iri"] or GENDER_VOCAB_URL
            phrase = f"Maybe? {url}"

    if platforms and (
        (has_changes and post_positive) or (not has_changes and post_negative)
    ):
        print_and_post(phrase, clients, dry_run=args.dry_run)

    if has_changes:
        sys.exit(EXIT_CODE_CHANGES_DETECTED)


if __name__ == "__main__":
    main()
