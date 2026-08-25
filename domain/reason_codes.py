"""
Evidence reason codes：任務文案不可以直接拼接任意欄位，一律透過這裡的
code -> 人類可讀標籤／formatter／來源類型／可用任務類型／是否為直接競品訊號 對照。
對應 SPEC §15.1。
"""
from __future__ import annotations

from dataclasses import dataclass
from domain.models import TaskType


@dataclass(frozen=True)
class ReasonCode:
    code: str
    label: str
    source_type: str
    applicable_task_types: tuple[TaskType, ...]
    is_direct_competitor_signal: bool = False


REASON_CODES: dict[str, ReasonCode] = {
    # ---- 攻｜Attack ----
    "attack_fit": ReasonCode(
        code="attack_fit", label="科別／策略適配",
        source_type="prospect", applicable_task_types=(TaskType.ATTACK,),
    ),
    "attack_interest": ReasonCode(
        code="attack_interest", label="明確興趣或活動回應",
        source_type="prospect", applicable_task_types=(TaskType.ATTACK,),
    ),
    "attack_lead_freshness": ReasonCode(
        code="attack_lead_freshness", label="線索來源新鮮度",
        source_type="prospect", applicable_task_types=(TaskType.ATTACK,),
    ),

    # ---- 守｜Defend ----
    "defend_core_product_stopped": ReasonCode(
        code="defend_core_product_stopped", label="核心品項連續停購",
        source_type="order", applicable_task_types=(TaskType.DEFEND,),
    ),
    "defend_revenue_decline": ReasonCode(
        code="defend_revenue_decline", label="訂單金額連續下降",
        source_type="order", applicable_task_types=(TaskType.DEFEND,),
    ),
    "defend_interaction_gap": ReasonCode(
        code="defend_interaction_gap", label="距上次有效互動過長",
        source_type="interaction", applicable_task_types=(TaskType.DEFEND,),
    ),
    "defend_overdue_commitment": ReasonCode(
        code="defend_overdue_commitment", label="未完成承諾已逾期",
        source_type="interaction", applicable_task_types=(TaskType.DEFEND,),
    ),
    "defend_service_issue": ReasonCode(
        code="defend_service_issue", label="服務／客訴事項未解決",
        source_type="interaction", applicable_task_types=(TaskType.DEFEND,),
    ),
    "defend_competitor_mentioned": ReasonCode(
        code="defend_competitor_mentioned", label="互動紀錄出現直接競品訊號",
        source_type="interaction", applicable_task_types=(TaskType.DEFEND,),
        is_direct_competitor_signal=True,
    ),

    # ---- 增｜Grow ----
    "grow_replenishment_window": ReasonCode(
        code="grow_replenishment_window", label="接近個別補貨週期",
        source_type="order", applicable_task_types=(TaskType.GROW,),
    ),
    "grow_purchase_stability": ReasonCode(
        code="grow_purchase_stability", label="過去採購穩定",
        source_type="order", applicable_task_types=(TaskType.GROW,),
    ),
    "grow_product_gap": ReasonCode(
        code="grow_product_gap", label="自身歷史品項缺口",
        source_type="order", applicable_task_types=(TaskType.GROW,),
    ),
    "grow_demand_signal": ReasonCode(
        code="grow_demand_signal", label="明確需求／產品興趣事件",
        source_type="interaction", applicable_task_types=(TaskType.GROW,),
    ),
}


def get_reason_code(code: str) -> ReasonCode:
    return REASON_CODES[code]


# ---------------------------------------------------------------------------
# 審核／結果表單用的原因代碼（跟上面的「任務觸發證據」代碼是不同用途）
# ---------------------------------------------------------------------------

REVIEW_REASON_CODES = [
    ("customer_already_contacted", "客戶已自行聯絡/已處理"),
    ("wrong_timing", "時機不對，之後再處理"),
    ("data_incorrect", "系統資料有誤"),
    ("out_of_capacity", "今日時間不足"),
    ("prefer_phone_first", "先電話確認比較合適"),
    ("other", "其他"),
]

# 文案護欄：允許使用的固定語句（SPEC §15.2）
ALLOWED_PHRASES = [
    "流失風險待查", "異常待查", "接近個別補貨週期", "高適配潛在診所",
    "證據強度：弱", "證據強度：中", "證據強度：強", "原因需業務確認",
    "任務價值分數用於 Demo 排序", "拜訪點位與建議順序示意",
]

# 禁用語句（SPEC §15.3, §16.5）——guardrail 測試會拿這份清單去掃輸出文字
BANNED_PHRASES = [
    "已被競品入侵", "提升成交率", "路線最佳化", "建議主推產品",
    "AI 已證實", "已避免多少營收損失", "接上真實資料即可直接上線",
    "AUC 0.618", "0.618", "54%", "67%", "IsolationForest",
]
