"""Named Entity Recognition extractor."""

import logging
from typing import Optional

import spacy

logger = logging.getLogger(__name__)

# Entity types to extract
RELEVANT_ENTITY_TYPES = {"PERSON", "GPE", "ORG", "EVENT", "DATE", "FAC"}


class NERExtractor:
    """Named Entity Recognition using spaCy."""

    def __init__(self, model_name: str = "en_core_web_lg"):
        """Initialize the NER extractor.

        Args:
            model_name: Name of the spaCy model to use.
        """
        self.model_name = model_name
        self._nlp: spacy.language.Language | None = None

    def _load_model(self) -> spacy.language.Language:
        """Load the spaCy model."""
        if self._nlp is None:
            try:
                self._nlp = spacy.load(self.model_name)
            except OSError:
                logger.warning(
                    f"Model {self.model_name} not found, downloading..."
                )
                from spacy.cli import download

                download(self.model_name)
                self._nlp = spacy.load(self.model_name)

        return self._nlp

    def extract_entities(self, text: str) -> list[dict]:
        """Extract named entities from text.

        Args:
            text: Input text.

        Returns:
            List of extracted entities with type and value.
        """
        if not text:
            return []

        nlp = self._load_model()
        doc = nlp(text[:100000])  # Limit text length

        entities = []
        for ent in doc.ents:
            if ent.label_ in RELEVANT_ENTITY_TYPES:
                entities.append(
                    {
                        "entity_type": ent.label_,
                        "entity_value": ent.text,
                        "start": ent.start_char,
                        "end": ent.end_char,
                    }
                )

        return entities

    def extract_persons(self, text: str) -> list[str]:
        """Extract person entities.

        Args:
            text: Input text.

        Returns:
            List of person names.
        """
        entities = self.extract_entities(text)
        return [e["entity_value"] for e in entities if e["entity_type"] == "PERSON"]

    def extract_locations(self, text: str) -> list[str]:
        """Extract GPE (Geo-Political Entity) locations.

        Args:
            text: Input text.

        Returns:
            List of location names.
        """
        entities = self.extract_entities(text)
        return [e["entity_value"] for e in entities if e["entity_type"] == "GPE"]

    def extract_organizations(self, text: str) -> list[str]:
        """Extract organization entities.

        Args:
            text: Input text.

        Returns:
            List of organization names.
        """
        entities = self.extract_entities(text)
        return [e["entity_value"] for e in entities if e["entity_type"] == "ORG"]

    def extract_events(self, text: str) -> list[str]:
        """Extract event entities.

        Args:
            text: Input text.

        Returns:
            List of event names.
        """
        entities = self.extract_entities(text)
        return [e["entity_value"] for e in entities if e["entity_type"] == "EVENT"]

    def extract_key_entities(self, text: str) -> dict:
        """Extract all relevant entities as a structured dict.

        Args:
            text: Input text.

        Returns:
            Dictionary with organized entities.
        """
        return {
            "persons": self.extract_persons(text),
            "locations": self.extract_locations(text),
            "organizations": self.extract_organizations(text),
            "events": self.extract_events(text),
        }


def create_ner_extractor() -> NERExtractor:
    """Create an NER extractor instance.

    Returns:
        Configured NERExtractor.
    """
    return NERExtractor()


# Module-level singleton — see `get_ner_extractor()` for the rationale.
_ner_singleton: Optional["NERExtractor"] = None


def get_ner_extractor() -> "NERExtractor":
    """Return the process-wide `NERExtractor` singleton.

    Why a singleton (and why this matters for memory):

    `en_core_web_lg` is ~750 MB resident once spaCy materializes the
    word vectors and pipeline components. Instantiating a fresh
    `NERExtractor` per `process_article` task — which the previous
    code did — meant every task allocated a brand-new
    `spacy.language.Language` object on first use. Python's GC does
    not deterministically reclaim the previous one (asyncpg
    connections, the SQLAlchemy identity map, and the spaCy `Vocab`
    string store all hold references that survive the local
    `ner = NERExtractor()` going out of scope), so the resident model
    accumulated across tasks until the worker hit the 3 GB cgroup
    limit and the kernel SIGKILLed it.

    Diagnosed 2026-05-05 — the worker-pipeline-1/2 crash loop kept
    firing OOMs at ~7-13 min uptime even after PRs #37/#40/#41/#42/#43
    closed every other suspected leak. The pattern was a fresh worker
    starting at ~94 MB RSS and climbing to 2.7 GB+ in a handful of
    `process_article` calls — exactly what "load 750 MB per task and
    fail to free it" looks like.

    A single shared `NERExtractor` lazy-loads the model once and reuses
    it for every subsequent task. The recycle from PR #42 still kicks
    in after 100 finished tasks, which gives spaCy's `Vocab.strings`
    cache (the residual creep) a clean restart roughly every 30-50 min
    in our throughput band.
    """
    global _ner_singleton
    if _ner_singleton is None:
        _ner_singleton = NERExtractor()
    return _ner_singleton
