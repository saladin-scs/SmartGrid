"""Entry point reserved for the NLP workflow.

Individual names pass through here before validation. A later NLP step can
normalize or suggest a name, but it must not create ontology properties.
"""


def prepare_individual_name(name: str) -> str:
    return " ".join(name.split())
