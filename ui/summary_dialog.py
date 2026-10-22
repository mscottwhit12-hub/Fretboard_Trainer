"""
ui/summary_dialog.py

End-of-quiz summary: accuracy, answers, average response time, best
streak, and the list of misses. Shown when the timer runs out (not when
the user presses Stop, which cancels without a summary).
"""

from dataclasses import dataclass

from PyQt6.QtWidgets import QDialog, QLabel, QListWidget, QHBoxLayout, QVBoxLayout

from ui.kit import Card, SkinButton
from ui.theme import skin


@dataclass
class AttemptSummary:
    correct: bool
    response_time_ms: int
    description: str  # shown for misses, e.g. "String 3 fret 5 -- was D, you said E"


def compute_summary(attempts: list[AttemptSummary]) -> dict:
    total = len(attempts)
    correct = sum(1 for a in attempts if a.correct)
    best = run = 0
    for a in attempts:
        run = run + 1 if a.correct else 0
        best = max(best, run)
    return {
        "total": total,
        "correct": correct,
        "accuracy": (correct / total * 100) if total else 0.0,
        "avg_ms": (sum(a.response_time_ms for a in attempts) / total) if total else 0.0,
        "best_streak": best,
        "misses": [a.description for a in attempts if not a.correct],
    }


class QuizSummaryDialog(QDialog):
    def __init__(self, title: str, attempts: list[AttemptSummary], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quiz Summary")
        self.setMinimumWidth(500)
        s = compute_summary(attempts)
        sk = skin()

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        card = Card(title, "yellow")
        stats = QLabel(
            f"Accuracy: {s['accuracy']:.0f}%  ({s['correct']} / {s['total']})\n"
            f"Average response time: {s['avg_ms'] / 1000:.1f}s\n"
            f"Best streak: {s['best_streak']}"
        )
        stats.setFont(sk.font("bold", 16))
        card.body.addWidget(stats)
        root.addWidget(card)

        misses = Card(f"Misses ({len(s['misses'])})" if s["misses"] else "No misses — clean run!",
                      "pink" if s["misses"] else "green")
        if s["misses"]:
            lst = QListWidget()
            lst.addItems(s["misses"])
            lst.setFont(sk.font("body", 14))
            lst.setMinimumHeight(150)
            misses.body.addWidget(lst)
        root.addWidget(misses)

        row = QHBoxLayout()
        row.addStretch()
        close = SkinButton("Close", "primary")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        row.addStretch()
        root.addLayout(row)
