"""
讀取 data/fixtures/*.csv 並做 schema 驗證（SPEC §8.11），
提供依 rep/date/target 查詢的穩定介面給 engines/ 和 services/ 使用。
"""
from __future__ import annotations

import csv
import os
from datetime import date, datetime

from domain.models import ActionMode, FixedAppointment

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

TAIWAN_LAT_RANGE = (21.5, 25.5)
TAIWAN_LON_RANGE = (119.5, 122.5)


class SchemaError(Exception):
    pass


def _read_csv(filename: str) -> list[dict]:
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _to_bool(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def _to_float(v, default=None):
    if v is None or v == "":
        return default
    return float(v)


def _to_date(v) -> date | None:
    if not v:
        return None
    return datetime.fromisoformat(v).date() if "T" not in v and len(v) > 10 else datetime.fromisoformat(v).date()


def _to_datetime(v) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return datetime.combine(datetime.fromisoformat(v).date(), datetime.min.time())


class FixtureRepository:
    def __init__(self, demo_cutoff: date, fixtures_dir: str = FIXTURES_DIR):
        self.demo_cutoff = demo_cutoff
        self._dir = fixtures_dir
        self.reps = self._load_reps()
        self.accounts = self._load_accounts()
        self.prospects = self._load_prospects()
        self.interactions = self._load_interactions()
        self.orders = self._load_orders()
        self.appointments = self._load_appointments()
        self._validate()

    # -- loaders -----------------------------------------------------------
    def _rows(self, filename):
        path = os.path.join(self._dir, filename)
        with open(path, encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def _load_reps(self):
        return {r["rep_id"]: r for r in self._rows("reps.csv")}

    def _load_accounts(self):
        out = {}
        for r in self._rows("accounts.csv"):
            r["lat"] = _to_float(r.get("lat"))
            r["lon"] = _to_float(r.get("lon"))
            out[r["account_id"]] = r
        return out

    def _load_prospects(self):
        out = {}
        for r in self._rows("prospects.csv"):
            r["lat"] = _to_float(r.get("lat"))
            r["lon"] = _to_float(r.get("lon"))
            r["explicit_interest"] = _to_bool(r.get("explicit_interest"))
            out[r["prospect_id"]] = r
        return out

    def _load_interactions(self):
        out = []
        for r in self._rows("interactions.csv"):
            r["resolved"] = _to_bool(r.get("resolved"))
            r["competitor_mentioned"] = _to_bool(r.get("competitor_mentioned"))
            r["occurred_at"] = _to_datetime(r["occurred_at"])
            r["due_date"] = _to_date(r["due_date"]) if r.get("due_date") else None
            out.append(r)
        return out

    def _load_orders(self):
        out = []
        for r in self._rows("orders.csv"):
            r["order_date"] = _to_date(r["order_date"])
            r["quantity"] = float(r["quantity"])
            r["amount"] = float(r["amount"])
            out.append(r)
        return out

    def _load_appointments(self):
        out = []
        for r in self._rows("appointments.csv"):
            r["appointment_date"] = _to_date(r["appointment_date"])
            r["duration_minutes"] = int(r["duration_minutes"])
            out.append(r)
        return out

    # -- validation (SPEC §8.11) --------------------------------------------
    def _validate(self):
        rep_ids = set(self.reps)
        account_ids = set(self.accounts)
        prospect_ids = set(self.prospects)

        for aid, a in self.accounts.items():
            if a["rep_id"] not in rep_ids:
                raise SchemaError(f"account {aid} 參照到不存在的 rep_id {a['rep_id']}")
            for field, rng in (("lat", TAIWAN_LAT_RANGE), ("lon", TAIWAN_LON_RANGE)):
                v = a[field]
                if v is not None and not (rng[0] <= v <= rng[1]):
                    raise SchemaError(f"account {aid} 的 {field}={v} 超出合理台灣範圍")

        for pid, p in self.prospects.items():
            if p["rep_id"] not in rep_ids:
                raise SchemaError(f"prospect {pid} 參照到不存在的 rep_id {p['rep_id']}")

        for it in self.interactions:
            target_ids = account_ids if it["target_type"] == "account" else prospect_ids
            if it["target_id"] not in target_ids:
                raise SchemaError(f"interaction {it['interaction_id']} 參照到不存在的 target {it['target_id']}")
            if it["occurred_at"] and it["occurred_at"].date() > self.demo_cutoff:
                raise SchemaError(f"interaction {it['interaction_id']} 的時間晚於 demo cutoff")

        for o in self.orders:
            if o["account_id"] not in account_ids:
                raise SchemaError(f"order {o['order_id']} 參照到不存在的 account {o['account_id']}")
            if o["amount"] < 0 or o["quantity"] < 0:
                raise SchemaError(f"order {o['order_id']} 金額或數量為負")
            if o["order_date"] and o["order_date"] > self.demo_cutoff:
                raise SchemaError(f"order {o['order_id']} 的日期晚於 demo cutoff")

        for ap in self.appointments:
            if ap["rep_id"] not in rep_ids:
                raise SchemaError(f"appointment {ap['appointment_id']} 參照到不存在的 rep_id")
            if ap["target_id"] not in account_ids and ap["target_id"] not in prospect_ids:
                raise SchemaError(f"appointment {ap['appointment_id']} 參照到不存在的 target")
            if ap["duration_minutes"] < 0:
                raise SchemaError(f"appointment {ap['appointment_id']} 的分鐘數為負")

    # -- query API -----------------------------------------------------------
    def get_reps(self) -> list[dict]:
        return list(self.reps.values())

    def get_rep(self, rep_id: str) -> dict:
        return self.reps[rep_id]

    def get_accounts(self, rep_id: str | None = None) -> list[dict]:
        vals = list(self.accounts.values())
        return [a for a in vals if a["rep_id"] == rep_id] if rep_id else vals

    def get_account(self, account_id: str) -> dict:
        return self.accounts[account_id]

    def get_prospects(self, rep_id: str | None = None) -> list[dict]:
        vals = list(self.prospects.values())
        return [p for p in vals if p["rep_id"] == rep_id] if rep_id else vals

    def get_prospect(self, prospect_id: str) -> dict:
        return self.prospects[prospect_id]

    def get_interactions(self, target_id: str, target_type: str | None = None) -> list[dict]:
        return [i for i in self.interactions if i["target_id"] == target_id
                and (target_type is None or i["target_type"] == target_type)]

    def get_orders(self, account_id: str) -> list[dict]:
        return [o for o in self.orders if o["account_id"] == account_id]

    def get_fixed_appointments(self, rep_id: str, on_date: date) -> list[FixedAppointment]:
        result = []
        for ap in self.appointments:
            if ap["rep_id"] != rep_id or ap["appointment_date"] != on_date:
                continue
            target_name = (self.accounts.get(ap["target_id"]) or self.prospects.get(ap["target_id"]) or {}).get("name", ap["target_id"])
            target = self.accounts.get(ap["target_id"]) or self.prospects.get(ap["target_id"]) or {}
            result.append(FixedAppointment(
                appointment_id=ap["appointment_id"], rep_id=ap["rep_id"], target_id=ap["target_id"],
                target_name=target_name, appointment_date=ap["appointment_date"],
                start_time=ap["start_time"], duration_minutes=ap["duration_minutes"],
                action_mode=ActionMode(ap["action_mode"]), purpose=ap["purpose"], status=ap["status"],
                lat=target.get("lat"), lon=target.get("lon"),
            ))
        return sorted(result, key=lambda a: a.start_time)

    def has_fixed_appointment(self, target_id: str, on_date: date) -> bool:
        return any(ap["target_id"] == target_id and ap["appointment_date"] == on_date for ap in self.appointments)
