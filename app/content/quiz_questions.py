"""3 questions du quiz de risque. FR. Index de la bonne réponse dans `correct_idx`."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuizQuestion:
    id: str
    question: str
    choices: tuple[str, ...]
    correct_idx: int


QUIZ_QUESTIONS: tuple[QuizQuestion, ...] = (
    QuizQuestion(
        id="q1_loss_risk",
        question="Si je mise 10€ sur un marché prédictif et que ma prédiction est fausse, combien je perds au maximum ?",
        choices=(
            "Rien, c'est remboursé",
            "Une partie de la mise selon le prix",
            "La totalité de la mise (10€)",
        ),
        correct_idx=2,
    ),
    QuizQuestion(
        id="q2_signal_meaning",
        question="Un signal à score élevé signifie-t-il que je vais gagner de l'argent à coup sûr ?",
        choices=(
            "Oui, c'est garanti",
            "Non, c'est une analyse d'intérêt, jamais une garantie",
            "Oui si je mise gros",
        ),
        correct_idx=1,
    ),
    QuizQuestion(
        id="q3_budget_rule",
        question="Quelle est la règle d'or avant de miser de l'argent réel sur un marché prédictif ?",
        choices=(
            "Miser au moins 100€ pour que ça en vaille la peine",
            "Ne jamais miser plus que ce que je peux me permettre de perdre",
            "Toujours suivre le signal le plus fort",
        ),
        correct_idx=1,
    ),
)

PASS_THRESHOLD = 3  # on exige 3/3 pour passer
