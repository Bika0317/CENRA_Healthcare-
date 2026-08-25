# CENRA Mission｜共用技術契約（三人都要對著這份寫）

這份文件是 A（domain/引擎/服務層）、B（審核狀態機/任務詳情/結果頁）、C（今日任務/行程頁/文件）三條軌道的**唯一共用真相**。任何人要改這份文件定義的形狀，先在群組講一聲，不要私自改。

對應完整規格：`CENRA_Mission_Codex_系統開發_SPEC.md`（以下簡稱 SPEC）§7.4, §7.5, §8, §11, §12。

---

## 1. Domain 物件（`domain/models.py`）

三人都要 import 這個檔案裡的型別，不要各自定義自己的 Task/Review 形狀。

```python
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class TargetType(str, Enum):
    ACCOUNT = "account"
    PROSPECT = "prospect"


class TaskType(str, Enum):
    ATTACK = "attack"   # 攻
    DEFEND = "defend"   # 守
    GROW = "grow"       # 增


class ActionMode(str, Enum):
    PHONE = "phone"
    VISIT = "visit"


class EvidenceStrength(str, Enum):
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"


class TaskStatus(str, Enum):
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    MODIFIED = "modified"
    DEFERRED = "deferred"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    NOT_COMPLETED = "not_completed"
    CANCELLED = "cancelled"


class ReviewDecision(str, Enum):
    ACCEPT = "accept"
    MODIFY = "modify"
    DEFER = "defer"
    REJECT = "reject"


class ExecutionStatus(str, Enum):
    COMPLETED = "completed"
    NOT_COMPLETED = "not_completed"
    CANCELLED = "cancelled"


class OutcomeType(str, Enum):
    DEMAND_CONFIRMED = "demand_confirmed"
    REPLENISHMENT = "replenishment"
    FOLLOW_UP_BOOKED = "follow_up_booked"
    NO_OPPORTUNITY = "no_opportunity"
    DATA_ERROR = "data_error"
    SERVICE_RESOLVED = "service_resolved"
    OTHER = "other"


@dataclass
class Evidence:
    evidence_id: str
    task_id: str
    code: str                  # 對應 domain/reason_codes.py 的 key
    label: str                 # 人類可讀標籤，例如「核心品項連續停購」
    display_value: str         # 例如「45 天未有效互動」
    source_type: str           # order / interaction / account / prospect / appointment
    source_id: str | None
    occurred_at: datetime | None
    strength: EvidenceStrength


@dataclass
class Task:
    task_id: str
    generation_key: str        # 保證同批次 idempotent 的 key
    generated_at: datetime
    task_date: date
    rep_id: str
    target_type: TargetType
    target_id: str
    task_type: TaskType
    title: str
    why_now: str
    objective: str
    action_mode: ActionMode
    estimated_minutes: int
    signal_score: float        # 0-100
    business_value_score: float  # 0-100
    urgency_score: float         # 0 / 50 / 100
    evidence_score: float        # 40 / 70 / 100
    strategy_fit_score: float    # 0 / 50 / 100
    cost_penalty: float          # 0-20
    value_score: float           # clamp 後 0-100，最終排序用這個
    evidence_strength: EvidenceStrength
    uncertainty_note: str
    data_updated_at: datetime
    model_version: str = "rules-v1"
    status: TaskStatus = TaskStatus.CANDIDATE
    evidences: list[Evidence] = field(default_factory=list)  # 最多 3 筆主要證據
    scheduled_start_time: str | None = None  # 只有 DailyPlan.visit_sequence 裡的副本會有值，不持久化


@dataclass
class TaskReview:
    review_id: str
    task_id: str
    decision: ReviewDecision
    original_objective: str
    modified_objective: str | None
    original_action_mode: ActionMode
    modified_action_mode: ActionMode | None
    reason_code: str
    reason_note: str | None
    deferred_to: date | None       # decision=defer 時必填
    actor_rep_id: str
    created_at: datetime


@dataclass
class TaskOutcome:
    outcome_id: str
    task_id: str
    execution_status: ExecutionStatus
    outcome_type: OutcomeType | None   # execution_status=completed 時必填
    note: str | None
    next_step: str | None
    next_date: date | None
    completed_at: datetime
    actor_rep_id: str


@dataclass
class FixedAppointment:
    appointment_id: str
    rep_id: str
    target_id: str
    appointment_date: date
    start_time: str            # "HH:MM"
    duration_minutes: int
    action_mode: ActionMode
    purpose: str
    status: str                # fixed / completed / cancelled


@dataclass
class DailyPlan:
    rep_id: str
    plan_date: date
    available_minutes: int
    fixed_appointments: list[FixedAppointment]
    candidate_tasks: list[Task]        # 這批候選（含所有 status）
    suggested_tasks: list[Task]        # 系統建議選取、依 value_score 排序
    remaining_minutes: int
    visit_sequence: list[Task]         # 只含已排點位的 visit 任務，依建議順序排列
```

### 1.1 狀態機規則（B 負責實作，A 負責定義函式簽名）

```python
def transition(task: Task, decision: ReviewDecision, **kwargs) -> Task:
    """
    合法轉移（SPEC §7.5）：
      candidate -> accepted / modified / deferred / rejected
      accepted / modified -> scheduled
      scheduled -> completed / not_completed / cancelled
    不合法轉移丟 InvalidTransitionError。
    defer 缺 deferred_to、reject 缺 reason_code、modify 沒有任何欄位變更 -> 丟 ValidationError。
    這個函式只改變 task.status 並回傳新 task，實際寫 DB 交給 review_service.py。
    """
```

---

## 2. CSV Fixture Schema（`data/fixtures/*.csv`，A 負責產生，C 的 UI 直接消費 `DailyPlan`，不必自己讀 CSV）

| 檔案 | 欄位（依序） |
|---|---|
| `reps.csv` | rep_id, rep_name, region, email, daily_available_minutes, home_lat, home_lon |
| `accounts.csv` | account_id, name, specialty, region, status(active/at_risk/inactive), rep_id, lat, lon, value_band(high/medium/low), created_at, updated_at |
| `prospects.csv` | prospect_id, name, specialty, region, rep_id, contact_stage(uncontacted/contacted/appointment/trial), fit_band(high/medium/low), lead_source, source_updated_at, explicit_interest(bool), lat, lon |
| `interactions.csv` | interaction_id, target_type(account/prospect), target_id, rep_id, occurred_at, channel(visit/phone/event), summary_tag, note, next_step, due_date, resolved(bool), competitor_mentioned(bool) |
| `orders.csv` | order_id, account_id, rep_id, order_date, product_line, quantity, amount, status(completed/cancelled/returned) |
| `appointments.csv` | appointment_id, rep_id, target_id, appointment_date, start_time, duration_minutes, action_mode, purpose, status |

**重要**：`accounts.csv` / `prospects.csv` **不可以**出現 `competitor_pressure`、`will_purchase`、`is_high_risk` 這類隱藏答案欄位。`competitor_mentioned` 只能出現在 `interactions.csv` 裡、對應一筆真實文字事件，不能是憑空生成的布林值。

---

## 3. Repository 介面（`data/fixture_repository.py`, `data/task_repository.py`）

```python
# data/fixture_repository.py
class FixtureRepository:
    def get_reps(self) -> list[dict]: ...
    def get_accounts(self, rep_id: str | None = None) -> list[dict]: ...
    def get_prospects(self, rep_id: str | None = None) -> list[dict]: ...
    def get_interactions(self, target_id: str, target_type: str) -> list[dict]: ...
    def get_orders(self, account_id: str) -> list[dict]: ...
    def get_fixed_appointments(self, rep_id: str, on_date: date) -> list[FixedAppointment]: ...

# data/task_repository.py
class TaskRepository:
    def __init__(self, db_path: str): ...
    def save_tasks(self, tasks: list[Task]) -> None: ...           # transaction, idempotent by generation_key
    def get_candidate_tasks(self, rep_id: str, task_date: date) -> list[Task]: ...
    def get_task(self, task_id: str) -> Task: ...
    def apply_review(self, task_id: str, review: TaskReview) -> Task: ...   # transaction: review + status 一起寫
    def apply_outcome(self, task_id: str, outcome: TaskOutcome) -> Task: ... # transaction: outcome + status 一起寫
    def get_review_history(self, task_id: str) -> list[TaskReview]: ...
    def reset_demo(self) -> None: ...     # 清空 tasks/evidence/review/outcome，回到固定初始狀態
    def resurface_deferred_tasks(self, rep_id: str, as_of: date) -> int: ...  # deferred_to<=as_of 的任務轉回 candidate
```

B 直接呼叫 `apply_review()` / `apply_outcome()`，不用自己寫 SQL。

---

## 4. 核心服務入口（A 負責，C 的 UI 直接呼叫這個拿 `DailyPlan`）

```python
# services/daily_plan_service.py
def build_daily_plan(
    rep_id: str,
    plan_date: date,
    available_minutes: int,
    fixture_repo: FixtureRepository,
    task_repo: TaskRepository,
) -> DailyPlan:
    """
    唯一的今日任務規劃入口。今天下午 A 會先交出一版「回傳假資料」的版本，
    C 可以先接這個假版本把 UI 串起來，晚一點 A 換成真邏輯後 C 不用改任何呼叫方式。
    """
```

---

## 5. 用詞護欄（C 的 guardrail test 要 grep 這些禁用語句，B 寫任務文案時也要避開）

**禁止出現**（SPEC §15.3）：
「已被競品入侵」「提升成交率」「路線最佳化」「建議主推產品」「AI 已證實」「已避免多少營收損失」「接上真實資料即可直接上線」，以及舊版的 Bootstrap 數字（54%、67%、AUC 0.618、15% 高風險、29% 競品壓力）。

**允許使用**（SPEC §15.2）：
「流失風險待查」「異常待查」「接近個別補貨週期」「高適配潛在診所」「證據強度：弱／中／強」「原因需業務確認」「任務價值分數用於 Demo 排序」「拜訪點位與建議順序示意」。
