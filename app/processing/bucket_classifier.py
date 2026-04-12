"""Bucket classifier for topic categorization."""

import logging
from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)

# Topic buckets
BUCKETS = [
    "politics",
    "economics",
    "crypto",
    "sports",
    "science",
    "geopolitics",
    "other",
]

# Training data (would be replaced with actual labeled data in production)
DEFAULT_TRAINING_DATA = {
    "politics": [
        "election vote ballot political party congress senate",
        "president prime minister government legislation",
        "congressional vote policy bill amendment",
        "political campaign candidate voter",
        "democrat republican parliament",
    ],
    "economics": [
        "economy inflation gdp interest rate federal reserve",
        "stock market trade unemployment jobs",
        "economic growth recession monetary policy",
        "federal reserve interest rates economic data",
        "trade deficit fiscal policy",
    ],
    "crypto": [
        "bitcoin ethereum cryptocurrency blockchain crypto",
        "ethereum token nft defi",
        "cryptocurrency exchange bitcoin price",
        "digital currency blockchain transaction",
        "crypto market cap token",
    ],
    "sports": [
        "game match team player score win",
        "championship tournament league season",
        "football basketball soccer baseball",
        "nfl nba mlb player stats",
        "sports team victory defeat",
    ],
    "science": [
        "research study scientist discovery",
        "study experiment laboratory findings",
        "scientific research breakthrough",
        "climate environment space nasa",
        "technology innovation research",
    ],
    "geopolitics": [
        "war military conflict troops border",
        "international relations nato alliance",
        "country government sanctions treaty",
        "military conflict diplomacy",
        "geopolitical tension conflict",
    ],
}


class BucketClassifier:
    """Topic bucket classifier using TF-IDF and logistic regression."""

    def __init__(self):
        """Initialize the bucket classifier."""
        self._pipeline: Optional[Pipeline] = None
        self._trained = False

    def _create_pipeline(self) -> Pipeline:
        """Create the classification pipeline.

        Returns:
            Configured sklearn pipeline.
        """
        pipeline = Pipeline(
            [
                ("tfidf", TfidfVectorizer(
                    max_features=5000,
                    ngram_range=(1, 2),
                    stop_words="english",
                )),
                ("clf", LogisticRegression(
                    max_iter=1000,
                    multi_class="multinomial",
                    solver="lbfgs",
                    class_weight="balanced",
                )),
            ]
        )
        return pipeline

    def _create_training_data(self) -> tuple[list[str], list[str]]:
        """Create training data from default examples.

        Returns:
            Tuple of (texts, labels).
        """
        texts = []
        labels = []

        for bucket, examples in DEFAULT_TRAINING_DATA.items():
            for example in examples:
                texts.append(example)
                labels.append(bucket)

        return texts, labels

    def train(self) -> None:
        """Train the classifier."""
        if self._trained:
            return

        texts, labels = self._create_training_data()
        self._pipeline = self._create_pipeline()
        self._pipeline.fit(texts, labels)
        self._trained = True
        logger.info("Bucket classifier trained")

    def predict(self, text: str) -> str:
        """Predict the bucket for text.

        Args:
            text: Input text.

        Returns:
            Predicted bucket.
        """
        if not self._trained:
            self.train()

        if not text:
            return "other"

        try:
            prediction = self._pipeline.predict([text])[0]
            return prediction
        except Exception as e:
            logger.error(f"Classification error: {e}")
            return "other"

    def predict_proba(self, text: str) -> dict[str, float]:
        """Get prediction probabilities.

        Args:
            text: Input text.

        Returns:
            Dictionary of bucket probabilities.
        """
        if not self._trained:
            self.train()

        if not text:
            return {bucket: 0.0 for bucket in BUCKETS}

        try:
            probas = self._pipeline.predict_proba([text])[0]
            return dict(zip(self._pipeline.classes_, probas))
        except Exception as e:
            logger.error(f"Probability error: {e}")
            return {bucket: 0.0 for bucket in BUCKETS}

    def is_relevant(self, text: str, threshold: float = 0.6) -> bool:
        """Check if text is relevant (not classified as "other").

        Args:
            text: Input text.
            threshold: Threshold for relevance.

        Returns:
            True if relevant.
        """
        probs = self.predict_proba(text)
        max_prob = max(probs.values())
        return max_prob >= threshold


# Global classifier instance
_classifier: Optional[BucketClassifier] = None


def create_bucket_classifier() -> BucketClassifier:
    """Create a bucket classifier instance.

    Returns:
        Configured BucketClassifier.
    """
    return BucketClassifier()


def get_bucket_classifier() -> BucketClassifier:
    """Get global classifier instance.

    Returns:
        Global BucketClassifier.
    """
    global _classifier
    if _classifier is None:
        _classifier = create_bucket_classifier()
    return _classifier