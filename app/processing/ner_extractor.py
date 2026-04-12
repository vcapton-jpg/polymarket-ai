"""Named Entity Recognition extractor."""

import json
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
        self._nlp: Optional[spacy.language.Language] = None

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