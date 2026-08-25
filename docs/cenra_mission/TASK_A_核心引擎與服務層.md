# 我（A）的任務：domain / fixtures / 三類任務引擎 / 評分 / DailyPlan 服務

對應 SPEC Stage 1–4。這條軌道是 B、C 的共用地基，所以順序上要最先交付 `00_CONTRACTS.md` 定義的介面（已完成），接著依序把「假資料版」換成「真邏輯版」。

## 交付順序

1. **契約文件**（已完成）：`docs/cenra_mission/00_CONTRACTS.md`。
2. `domain/models.py`、`domain/reason_codes.py`：把契約文件裡的 dataclass/enum 變成真的可 import 的程式碼，`transition()` 先做出完整規則判斷（這個不依賴資料庫，可以最先做完）。
3. `data/fixtures/seed_generator.py` + 六張 CSV：3 業務、每人 8–12 帳戶、3–5 潛在診所、180+ 天訂單/互動、主 demo 業務 2 個固定預約，內建 SPEC §9.2 的 8 種必備情境。固定 random seed。
4. `data/fixture_repository.py`：讀 CSV + schema 驗證（SPEC §8.11）。
5. `data/task_repository.py`：SQLite 建表、`save_tasks()` idempotent（用 generation_key 判斷）、`apply_review()`/`apply_outcome()` transaction、`reset_demo()`。這一步做完後 B、C 就能開始接真資料。
6. `engines/attack.py` / `defend.py` / `grow.py`：SPEC §10 的資格條件、觸發規則、原始訊號權重。
7. `services/scoring.py`：統一任務價值分數公式（SPEC §11）。
8. `services/scheduling.py`：固定預約占用 + 三類最低配額 + nearest-neighbor 點位順序（SPEC §12）。
9. `services/daily_plan_service.py`：串起 6-8，組出 `DailyPlan`。**先交一版回傳 mock DailyPlan 的版本給 C**（C 現在就在等這個），晚一點再換真邏輯，函式簽名不變。

## 測試

- `tests/test_engines.py`：涵蓋 SPEC §16.2 的 20 條規則。
- `tests/test_scoring.py` + `tests/test_daily_plan_service.py`：涵蓋單一候選 percentile=70、tie-break、容量不超額、idempotent。
- `tests/test_repository.py`：schema 驗證、transaction 失敗不部分寫入、reset 回到固定狀態。

## 今天交付給 B、C 的訊息時間點

- 「契約文件寫完了，可以開始寫測試和刻 UI 骨架」→ 已完成。
- 「`domain/models.py` 真的可以 import 了」→ 儘快。
- 「`task_repository.py` 的 `apply_review`/`apply_outcome` 是真的了，B 可以串真資料」→ 中午前。
- 「`daily_plan_service.build_daily_plan()` 是真的了，C 可以串真資料」→ 下午。

完成後回來對照 `docs/cenra_mission/00_CONTRACTS.md` 檢查有沒有跟原始約定的介面形狀跑掉；如果中途發現契約需要改，先跟 B、C 講。
