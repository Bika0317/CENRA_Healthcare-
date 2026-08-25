"""
SQLite repository：tasks / task_evidence / task_reviews / task_outcomes。
所有寫入操作用 transaction；review/outcome 與 task.status 一起寫，任一失敗不部分寫入。
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime

from domain.models import (
    ActionMode, DailyPlan, Evidence, EvidenceStrength, ExecutionStatus, FixedAppointment,
    InvalidTransitionError, OutcomeType, ReviewDecision, Task, TaskOutcome, TaskReview, TaskStatus,
    TargetType, TaskType, apply_outcome_to_task, schedule_task, transition, validate_outcome,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    generation_key TEXT UNIQUE,
    generated_at TEXT, task_date TEXT, rep_id TEXT, target_type TEXT, target_id TEXT,
    target_name TEXT, task_type TEXT, title TEXT, why_now TEXT, objective TEXT,
    action_mode TEXT, estimated_minutes INTEGER,
    signal_score REAL, business_value_score REAL, urgency_score REAL, evidence_score REAL,
    strategy_fit_score REAL, cost_penalty REAL, value_score REAL,
    evidence_strength TEXT, uncertainty_note TEXT, data_updated_at TEXT,
    lat REAL, lon REAL, model_version TEXT, status TEXT
);
CREATE TABLE IF NOT EXISTS task_evidence (
    evidence_id TEXT PRIMARY KEY, task_id TEXT, code TEXT, label TEXT, display_value TEXT,
    source_type TEXT, source_id TEXT, occurred_at TEXT, strength TEXT
);
CREATE TABLE IF NOT EXISTS task_reviews (
    review_id TEXT PRIMARY KEY, task_id TEXT, decision TEXT,
    original_objective TEXT, modified_objective TEXT,
    original_action_mode TEXT, modified_action_mode TEXT,
    reason_code TEXT, reason_note TEXT, deferred_to TEXT, actor_rep_id TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS task_outcomes (
    outcome_id TEXT PRIMARY KEY, task_id TEXT, execution_status TEXT, outcome_type TEXT,
    note TEXT, next_step TEXT, next_date TEXT, completed_at TEXT, actor_rep_id TEXT
);
"""


def _row_to_task(row: sqlite3.Row, evidences: list[Evidence]) -> Task:
    return Task(
        task_id=row["task_id"], generation_key=row["generation_key"],
        generated_at=datetime.fromisoformat(row["generated_at"]),
        task_date=date.fromisoformat(row["task_date"]), rep_id=row["rep_id"],
        target_type=TargetType(row["target_type"]), target_id=row["target_id"],
        target_name=row["target_name"], task_type=TaskType(row["task_type"]),
        title=row["title"], why_now=row["why_now"], objective=row["objective"],
        action_mode=ActionMode(row["action_mode"]), estimated_minutes=row["estimated_minutes"],
        signal_score=row["signal_score"], business_value_score=row["business_value_score"],
        urgency_score=row["urgency_score"], evidence_score=row["evidence_score"],
        strategy_fit_score=row["strategy_fit_score"], cost_penalty=row["cost_penalty"],
        value_score=row["value_score"], evidence_strength=EvidenceStrength(row["evidence_strength"]),
        uncertainty_note=row["uncertainty_note"],
        data_updated_at=datetime.fromisoformat(row["data_updated_at"]),
        lat=row["lat"], lon=row["lon"], model_version=row["model_version"],
        status=TaskStatus(row["status"]), evidences=evidences,
    )


class TaskRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self):
        self._conn.close()

    # -- write: task generation (idempotent) --------------------------------
    def save_tasks(self, tasks: list[Task]) -> int:
        """依 generation_key idempotent 寫入；同一批次已存在的 key 會被跳過。回傳新增筆數。"""
        cur = self._conn.cursor()
        inserted = 0
        try:
            for t in tasks:
                cur.execute("SELECT 1 FROM tasks WHERE generation_key = ?", (t.generation_key,))
                if cur.fetchone():
                    continue
                cur.execute(
                    """INSERT INTO tasks (task_id, generation_key, generated_at, task_date, rep_id,
                        target_type, target_id, target_name, task_type, title, why_now, objective,
                        action_mode, estimated_minutes, signal_score, business_value_score,
                        urgency_score, evidence_score, strategy_fit_score, cost_penalty, value_score,
                        evidence_strength, uncertainty_note, data_updated_at, lat, lon, model_version, status)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (t.task_id, t.generation_key, t.generated_at.isoformat(), t.task_date.isoformat(),
                     t.rep_id, t.target_type.value, t.target_id, t.target_name, t.task_type.value,
                     t.title, t.why_now, t.objective, t.action_mode.value, t.estimated_minutes,
                     t.signal_score, t.business_value_score, t.urgency_score, t.evidence_score,
                     t.strategy_fit_score, t.cost_penalty, t.value_score, t.evidence_strength.value,
                     t.uncertainty_note, t.data_updated_at.isoformat(), t.lat, t.lon,
                     t.model_version, t.status.value),
                )
                for e in t.evidences:
                    cur.execute(
                        """INSERT INTO task_evidence (evidence_id, task_id, code, label, display_value,
                            source_type, source_id, occurred_at, strength) VALUES (?,?,?,?,?,?,?,?,?)""",
                        (e.evidence_id, t.task_id, e.code, e.label, e.display_value, e.source_type,
                         e.source_id, e.occurred_at.isoformat() if e.occurred_at else None, e.strength.value),
                    )
                inserted += 1
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return inserted

    # -- read -----------------------------------------------------------------
    def _load_evidences(self, task_id: str) -> list[Evidence]:
        rows = self._conn.execute("SELECT * FROM task_evidence WHERE task_id = ?", (task_id,)).fetchall()
        return [Evidence(
            evidence_id=r["evidence_id"], task_id=r["task_id"], code=r["code"], label=r["label"],
            display_value=r["display_value"], source_type=r["source_type"], source_id=r["source_id"],
            occurred_at=datetime.fromisoformat(r["occurred_at"]) if r["occurred_at"] else None,
            strength=EvidenceStrength(r["strength"]),
        ) for r in rows]

    def get_candidate_tasks(self, rep_id: str, task_date: date) -> list[Task]:
        rows = self._conn.execute(
            "SELECT * FROM tasks WHERE rep_id = ? AND task_date = ? ORDER BY value_score DESC",
            (rep_id, task_date.isoformat()),
        ).fetchall()
        return [_row_to_task(r, self._load_evidences(r["task_id"])) for r in rows]

    def get_task(self, task_id: str) -> Task:
        row = self._conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"task {task_id} not found")
        return _row_to_task(row, self._load_evidences(task_id))

    def get_review_history(self, task_id: str) -> list[TaskReview]:
        rows = self._conn.execute(
            "SELECT * FROM task_reviews WHERE task_id = ? ORDER BY created_at", (task_id,)
        ).fetchall()
        return [TaskReview(
            review_id=r["review_id"], task_id=r["task_id"], decision=ReviewDecision(r["decision"]),
            original_objective=r["original_objective"], modified_objective=r["modified_objective"],
            original_action_mode=ActionMode(r["original_action_mode"]),
            modified_action_mode=ActionMode(r["modified_action_mode"]) if r["modified_action_mode"] else None,
            reason_code=r["reason_code"], reason_note=r["reason_note"],
            deferred_to=date.fromisoformat(r["deferred_to"]) if r["deferred_to"] else None,
            actor_rep_id=r["actor_rep_id"], created_at=datetime.fromisoformat(r["created_at"]),
        ) for r in rows]

    # -- write: review / outcome (transaction, no partial write) -------------
    def apply_review(self, task_id: str, decision: ReviewDecision, *,
                      modified_objective: str | None, modified_action_mode: ActionMode | None,
                      reason_code: str, reason_note: str | None, deferred_to: date | None,
                      actor_rep_id: str) -> Task:
        task = self.get_task(task_id)
        updated = transition(task, decision, modified_objective=modified_objective,
                              modified_action_mode=modified_action_mode,
                              reason_code=reason_code, deferred_to=deferred_to)
        review = TaskReview(
            review_id=f"REV-{uuid.uuid4().hex[:10]}", task_id=task_id, decision=decision,
            original_objective=task.objective, modified_objective=modified_objective,
            original_action_mode=task.action_mode, modified_action_mode=modified_action_mode,
            reason_code=reason_code, reason_note=reason_note, deferred_to=deferred_to,
            actor_rep_id=actor_rep_id, created_at=datetime.now(),
        )
        cur = self._conn.cursor()
        try:
            cur.execute(
                """INSERT INTO task_reviews (review_id, task_id, decision, original_objective,
                    modified_objective, original_action_mode, modified_action_mode, reason_code,
                    reason_note, deferred_to, actor_rep_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (review.review_id, review.task_id, review.decision.value, review.original_objective,
                 review.modified_objective, review.original_action_mode.value,
                 review.modified_action_mode.value if review.modified_action_mode else None,
                 review.reason_code, review.reason_note,
                 review.deferred_to.isoformat() if review.deferred_to else None,
                 review.actor_rep_id, review.created_at.isoformat()),
            )
            cur.execute("UPDATE tasks SET status = ?, objective = ?, action_mode = ? WHERE task_id = ?",
                        (updated.status.value, updated.objective, updated.action_mode.value, task_id))
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return updated

    def mark_scheduled(self, task_id: str) -> Task:
        task = self.get_task(task_id)
        updated = schedule_task(task)
        self._conn.execute("UPDATE tasks SET status = ? WHERE task_id = ?", (updated.status.value, task_id))
        self._conn.commit()
        return updated

    def apply_outcome(self, task_id: str, execution_status: ExecutionStatus,
                       outcome_type: OutcomeType | None, note: str | None,
                       next_step: str | None, next_date: date | None, actor_rep_id: str) -> Task:
        task = self.get_task(task_id)
        validate_outcome(task, execution_status, outcome_type)
        updated = apply_outcome_to_task(task, execution_status)
        outcome = TaskOutcome(
            outcome_id=f"OUT-{uuid.uuid4().hex[:10]}", task_id=task_id,
            execution_status=execution_status, outcome_type=outcome_type, note=note,
            next_step=next_step, next_date=next_date, completed_at=datetime.now(),
            actor_rep_id=actor_rep_id,
        )
        cur = self._conn.cursor()
        try:
            cur.execute(
                """INSERT INTO task_outcomes (outcome_id, task_id, execution_status, outcome_type,
                    note, next_step, next_date, completed_at, actor_rep_id) VALUES (?,?,?,?,?,?,?,?,?)""",
                (outcome.outcome_id, outcome.task_id, outcome.execution_status.value,
                 outcome.outcome_type.value if outcome.outcome_type else None, outcome.note,
                 outcome.next_step, outcome.next_date.isoformat() if outcome.next_date else None,
                 outcome.completed_at.isoformat(), outcome.actor_rep_id),
            )
            cur.execute("UPDATE tasks SET status = ? WHERE task_id = ?", (updated.status.value, task_id))
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return updated

    def get_outcome(self, task_id: str) -> TaskOutcome | None:
        row = self._conn.execute(
            "SELECT * FROM task_outcomes WHERE task_id = ? ORDER BY completed_at DESC LIMIT 1", (task_id,)
        ).fetchone()
        if row is None:
            return None
        return TaskOutcome(
            outcome_id=row["outcome_id"], task_id=row["task_id"],
            execution_status=ExecutionStatus(row["execution_status"]),
            outcome_type=OutcomeType(row["outcome_type"]) if row["outcome_type"] else None,
            note=row["note"], next_step=row["next_step"],
            next_date=date.fromisoformat(row["next_date"]) if row["next_date"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]), actor_rep_id=row["actor_rep_id"],
        )

    def reset_demo(self) -> None:
        cur = self._conn.cursor()
        for table in ("task_outcomes", "task_reviews", "task_evidence", "tasks"):
            cur.execute(f"DELETE FROM {table}")
        self._conn.commit()
