import sys
from os import environ

import requests
from atproto import Client, client_utils
from lxml import etree

gender_vocab_url = "https://d-nb.info/standards/vocab/gnd/gender"


def check_gender_concepts() -> set[str]:
    res = requests.get(gender_vocab_url + ".rdf")
    doc = etree.fromstring(res.content)

    concepts_expected = {
        "https://d-nb.info/standards/vocab/gnd/gender#female",
        "https://d-nb.info/standards/vocab/gnd/gender#male",
        "https://d-nb.info/standards/vocab/gnd/gender#notKnown",
    }

    # Ensure there are no `None` keys
    namespaces = {k: v for k, v in doc.nsmap.items() if k is not None}
    concepts = set(doc.xpath("//skos:Concept/@rdf:about", namespaces=namespaces))
    return concepts - concepts_expected


def main():
    print("Performing ATProto login...")
    client = Client()
    profile = client.login(
        environ.get("ATPROTO_HANDLE"), environ.get("ATPROTO_PASSWORD")
    )
    print("Logged in as:", profile.display_name)

    print("Fetching GND gender information...")
    new_concepts = check_gender_concepts()

    if not new_concepts:
        print("Found no new concepts.")
        client.send_post(text="No.")
    else:
        # IT’S HAPPENING
        print("Found unexpected concepts!")
        print("\n".join(new_concepts))

        text = client_utils.TextBuilder().link("Maybe?", gender_vocab_url)
        client.send_post(text)

        sys.exit(1)  # Exit with error code, so GitHub Actions sends a notification


if __name__ == "__main__":
    main()
