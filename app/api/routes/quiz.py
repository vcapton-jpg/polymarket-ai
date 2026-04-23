"""Quiz routes — 3 risk questions. Passing 3/3 unlocks UserLimits.quiz_passed."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.routes.auth import get_current_user  # NOT app.api.deps
from app.api.schemas.learn_and_trade import (
    QuizQuestionOut,
    QuizResultOut,
    QuizSubmitIn,
)
from app.content.quiz_questions import PASS_THRESHOLD, QUIZ_QUESTIONS
from app.db.database import get_session_factory
from app.db.models import OnboardingProgress, QuizAttempt, UserLimits, UserProfile

router = APIRouter(prefix="/quiz", tags=["quiz"])


class QuizQuestionsOut(BaseModel):
    questions: list[QuizQuestionOut]


@router.get("/questions", response_model=QuizQuestionsOut)
async def get_quiz_questions(
    user: UserProfile = Depends(get_current_user),
) -> QuizQuestionsOut:
    return QuizQuestionsOut(
        questions=[
            QuizQuestionOut(id=q.id, question=q.question, choices=list(q.choices))
            for q in QUIZ_QUESTIONS
        ]
    )


@router.post("/submit", response_model=QuizResultOut)
async def submit_quiz(
    body: QuizSubmitIn,
    user: UserProfile = Depends(get_current_user),
) -> QuizResultOut:
    score = sum(
        1 for q in QUIZ_QUESTIONS if body.answers.get(q.id) == q.correct_idx
    )
    total = len(QUIZ_QUESTIONS)
    passed = score >= PASS_THRESHOLD

    factory = get_session_factory()
    async with factory() as s:
        s.add(
            QuizAttempt(
                user_id=user.id,
                answers=dict(body.answers),
                score=score,
                passed=passed,
            )
        )

        if passed:
            limits = await s.get(UserLimits, user.id)
            if limits is None:
                limits = UserLimits(user_id=user.id)
                s.add(limits)
            limits.quiz_passed = True

            onb = await s.get(OnboardingProgress, user.id)
            if onb is None:
                onb = OnboardingProgress(user_id=user.id)
                s.add(onb)
            onb.quiz_done = True

        await s.commit()

    return QuizResultOut(score=score, total=total, passed=passed)
