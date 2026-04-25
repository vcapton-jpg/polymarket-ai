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

DEFAULT_TRAINING_DATA = {
    "politics": [
        "election vote ballot political party congress senate house representatives",
        "president prime minister government legislation executive order signed",
        "congressional vote policy bill amendment filibuster veto override",
        "political campaign candidate voter registration swing state",
        "democrat republican parliament coalition majority opposition",
        "governor state legislature redistricting gerrymandering recall",
        "supreme court ruling nomination confirmation hearing judiciary",
        "impeachment proceedings articles charges acquittal conviction",
        "midterm election primary caucus delegate count convention",
        "approval rating polls favorability incumbent challenger runoff",
        "trump biden desantis harris presidential nominee campaign rally",
        "speaker of the house majority leader minority whip caucus",
        "executive order presidential directive policy reversal administration",
        "political scandal corruption indictment investigation subpoena testimony",
        "cabinet appointment secretary confirmation bipartisan gridlock",
    ],
    "economics": [
        "economy inflation gdp interest rate federal reserve monetary policy",
        "stock market trade unemployment jobs report labor statistics",
        "economic growth recession fiscal stimulus spending package",
        "federal reserve interest rates economic data fomc meeting",
        "trade deficit fiscal policy budget surplus government spending",
        "consumer price index cpi producer price ppi core inflation",
        "treasury yield bond market credit rating downgrade upgrade",
        "oil price barrel opec production cut supply demand commodity",
        "housing market mortgage rates home sales real estate prices",
        "manufacturing pmi services sector industrial production output",
        "banking crisis liquidity intervention bailout deposit insurance",
        "tariff trade war import export duty commercial sanctions",
        "nasdaq dow jones sp500 market rally correction bear bull",
        "gdp growth quarterly annual revision economic forecast outlook",
        "wage growth minimum wage salary compensation benefits labor",
    ],
    "crypto": [
        "bitcoin btc price surge crash rally all time high cryptocurrency",
        "ethereum eth upgrade merge smart contract gas fees blockchain",
        "cryptocurrency exchange binance coinbase kraken trading volume",
        "defi decentralized finance yield farming liquidity pool protocol",
        "nft non fungible token digital art collectibles marketplace opensea",
        "stablecoin usdt usdc tether peg depeg regulation reserves",
        "solana sol network outage tps transactions per second chain",
        "crypto regulation sec enforcement action lawsuit securities fraud",
        "bitcoin halving mining difficulty hash rate energy consumption",
        "dogecoin doge meme coin shiba inu pepe memecoin pump",
        "crypto wallet private key seed phrase cold storage hardware",
        "blockchain layer 2 rollup scaling solution zk proof optimistic",
        "altcoin season rotation dominance market cap cardano polkadot",
        "crypto etf approval spot bitcoin fund institutional adoption",
        "ripple xrp lawsuit sec settlement ruling cross border payments",
    ],
    "sports": [
        "nba basketball game score points rebounds assists playoffs finals",
        "nfl football touchdown quarterback passing yards super bowl",
        "mlb baseball home run pitcher strikeout world series standings",
        "premier league soccer football goal assist transfer window epl",
        "champions league uefa europa match draw group stage knockout",
        "world cup fifa tournament qualification host nation international",
        "nhl hockey goal save shutout stanley cup playoffs hat trick",
        "tennis grand slam wimbledon us open french australian match",
        "formula 1 f1 grand prix race qualifying pole position lap",
        "boxing ufc mma fight knockout decision title belt champion",
        "olympic games medal gold silver bronze athlete competition",
        "mvp award all star selection rookie of the year defensive",
        "player trade free agent signing contract extension salary cap",
        "injury report concussion protocol suspension banned substance",
        "championship series division finals conference semifinal bracket",
    ],
    "science": [
        "scientific research study published journal peer reviewed findings",
        "nasa space mission launch satellite orbit exploration mars moon",
        "spacex rocket launch landing reusable starship falcon crew dragon",
        "vaccine clinical trial fda approval efficacy side effects dosage",
        "climate change global warming temperature emissions carbon dioxide",
        "artificial intelligence machine learning deep neural network model",
        "quantum computing qubit entanglement supremacy error correction",
        "gene therapy crispr genome editing dna rna genetic mutation",
        "disease outbreak pandemic epidemic virus variant strain mutation",
        "telescope observatory discovery exoplanet galaxy nebula star",
        "renewable energy solar wind battery storage grid power plant",
        "drug development pharmaceutical compound molecule treatment cure",
        "environmental protection biodiversity conservation endangered species",
        "medical breakthrough surgery technique imaging diagnostic mri",
        "fusion energy reactor tokamak plasma confinement experiment",
    ],
    "geopolitics": [
        "war military conflict troops border invasion territorial dispute",
        "international relations nato alliance defense pact mutual security",
        "sanctions economic embargo trade restrictions diplomatic isolation",
        "ceasefire peace deal agreement negotiations talks summit meeting",
        "military deployment forces operations strike bombing raid patrol",
        "nuclear weapons program enrichment missile launch test warhead",
        "russia ukraine frontline counteroffensive territory annexed crimea",
        "china taiwan strait tensions military exercises reunification",
        "iran nuclear deal enrichment iaea inspections proxy forces",
        "north korea kim jong un icbm test denuclearization talks",
        "middle east conflict israel palestine hamas hezbollah gaza",
        "coup regime change overthrow junta civilian government military",
        "refugee crisis displacement humanitarian aid corridor evacuation",
        "espionage intelligence spy agency foreign interference election",
        "territorial waters south china sea disputed islands sovereignty claim",
    ],
    # Audit follow-up: the "other" bucket previously had ZERO training
    # examples, so the model could never predict it — irrelevant content
    # got force-assigned to one of the 6 real topics, polluting clusters.
    # These cover the irrelevant content the ingestion pipeline actually
    # sees: lifestyle, celebrity, weather, local human-interest, recipes,
    # entertainment — content that has no prediction-market relevance.
    "other": [
        "celebrity wedding paparazzi photos red carpet gown designer hollywood",
        "movie premiere box office opening weekend trailer release sequel",
        "music album release tour concert tickets streaming chart top hits",
        "fashion week runway show designer collection model brand luxury",
        "travel destination vacation resort beach hotel review tourism guide",
        "recipe cooking ingredients dish chef restaurant menu dining cuisine",
        "horoscope zodiac astrology star sign reading prediction tarot card",
        "weather forecast rain snow temperature storm hurricane warning local",
        "lifestyle wellness yoga meditation mindfulness self care routine tips",
        "viral video meme tiktok trend social media post likes shares funny",
        "garden plants flowers landscaping diy home improvement decor inspiration",
        "pet dog cat animal rescue adoption shelter veterinarian breed grooming",
        "wedding engagement honeymoon ceremony reception bridal party venue",
        "obituary memorial funeral remembrance tribute legacy beloved community",
        "human interest local community charity event fundraiser volunteer story",
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