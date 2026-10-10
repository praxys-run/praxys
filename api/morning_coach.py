"""Server-owned morning Coach evidence, templates and snapshot contract.

Selection changes emphasis, never the canonical Today decision. No model text
or numbers cross this boundary. Existing recovery formulas remain authoritative.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from analysis.config import is_praxys_plan_source
from db.cache_revision import SCOPES, get_revisions

CONTENT_VERSION = "morning-coach-v2"
CONTRACT_KEY = "_morning_coach"


def digest(value: Any) -> str:
    """Hash a canonical JSON value, rejecting non-finite numbers."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def snapshot_identity(user_id: str, revisions: dict, as_of: str, include_stryd: bool) -> str:
    """Bind the owner, server calendar, source vector and plan representation."""
    return digest([CONTENT_VERSION, user_id, as_of, revisions, include_stryd])


def current_snapshot(db: Session, user_id: str, include_stryd: bool) -> str:
    """Read current source identity; callers bracket reads or hold write locks."""
    return snapshot_identity(user_id, get_revisions(db, user_id, SCOPES),
                             date.today().isoformat(), include_stryd)


def available(db: Session, user_id: str) -> bool:
    """Require processing consent, active account and operational Azure AI."""
    from api.optional_processing import background_ai_authorized
    from api.llm import runtime_ai_available
    return background_ai_authorized(db, user_id=user_id) and runtime_ai_available()


def theory_refs(science: dict, pillars: tuple[str, ...] = ("recovery", "load")) -> list[dict]:
    """Return allowlisted, server-selected method destinations for both clients."""
    refs = []
    for pillar in pillars:
        if pillar not in {"recovery", "load", "prediction", "zones"}:
            continue
        theory = science.get(pillar)
        if theory is None:
            continue
        key = theory.get("id") if isinstance(theory, dict) else theory.id
        name = theory.get("name") if isinstance(theory, dict) else theory.name
        if isinstance(key, str) and isinstance(name, str):
            refs.append({"pillar": pillar, "theory_id": key, "label": name})
    return refs


def _number(value: object, *, score: bool = False) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    if not math.isfinite(value) or (value < 0 if score else value <= 0):
        return None
    if score and value > 100:
        return None
    return round(float(value), 1)


def _day(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _workout_label(plan: dict) -> tuple[str, str]:
    """Name a course through fixed bilingual labels, never provider prose."""
    return {"easy": ("easy run", "轻松跑"), "recovery": ("recovery run", "恢复跑"),
            "long": ("long run", "长距离跑"), "tempo": ("tempo run", "节奏跑"),
            "intervals": ("interval session", "间歇训练"),
            "rest": ("rest day", "休息日")}.get(plan.get("workout_type"), ("workout", "训练课"))


def _course_targets(plan: dict) -> tuple[str, str]:
    """Quote finite, ordered course targets without deriving a new dose."""
    en, zh = [], []
    for key, unit in (("planned_distance_km", "km"), ("planned_duration_min", "min")):
        value = _number(plan.get(key))
        if value is not None:
            en.append(f"{value:g} {unit}")
            zh.append(f"{value:g} {'公里' if unit == 'km' else '分钟'}")
    low, high = (_number(plan.get(key)) for key in ("target_power_min", "target_power_max"))
    if low is not None and high is not None and low <= high:
        en.append(f"{low:g}–{high:g} W")
        zh.append(f"{low:g}–{high:g} W")
    return ", ".join(en), "、".join(zh)


def _external_courses(context: dict, as_of: date) -> list[dict]:
    """Keep same-day external observations separate from the canonical plan."""
    courses = list(context.get("external_planned_today") or [])
    plan = context.get("planned_today")
    if not courses and isinstance(plan, dict) and plan.get("owner") == "external":
        courses = [plan]
    return [p for p in courses if isinstance(p, dict)
            and _day(p.get("date")) == as_of and not is_praxys_plan_source(p.get("source"))
            and (context.get("include_stryd_plan", True) or str(p.get("source", "")).strip().casefold() != "stryd")]


def _platform_name(plan: dict) -> str:
    """Use provider identities rather than arbitrary external labels."""
    return {"stryd": "Stryd", "garmin": "Garmin"}.get(str(plan.get("source", "")).strip().casefold(), "External")


def candidates(context: dict) -> dict:
    """Build eligible observations and actions before model selection.

    Current recovery uses the accepted today/yesterday window, metric-specific
    dates and existing baseline support. Recorded training is descriptive.
    """
    as_of = date.fromisoformat(context["as_of_date"])
    state = context.get("recovery_state") or {}
    dates = state.get("metric_dates") or {}
    evidence: dict[str, dict] = {}
    recovery_parts = {"en": [], "zh": []}
    missing = {"en": [], "zh": []}
    for metric, key, en, zh, unit in (
        ("sleep", "sleep_score", "sleep score", "睡眠评分", ""),
        ("hrv", "hrv_ms", "HRV", "HRV", " ms"),
        ("rhr", "resting_hr", "resting heart rate", "静息心率", " bpm"),
    ):
        value = _number(state.get(key), score=metric == "sleep")
        observed = _day(dates.get(metric))
        current = (value is not None and observed is not None
                   and 0 <= (as_of - observed).days <= 1
                   and (state.get("metric_validity") or {}).get(metric, True))
        if current:
            recovery_parts["en"].append(f"{en} {value:g}{unit} ({observed})")
            recovery_parts["zh"].append(f"{zh} {value:g}{unit}（{observed}）")
        else:
            missing["en"].append(en)
            missing["zh"].append(zh)
        evidence[f"recovery.{metric}"] = {
            "en": (f"{en.capitalize()}: {value:g}{unit}, recorded {observed}." if current else
                   f"Sync a recent {en} observation to complete the recovery picture."),
            "zh": (f"{zh}：{value:g}{unit}，记录于 {observed}。" if current else
                   f"同步近期{zh}记录后，可补齐今天的恢复信息。"),
            "current": bool(current),
        }
    recovery_summary = {}
    for lang in ("en", "zh"):
        absent = (", " if lang == "en" else "、").join(missing[lang])
        if lang == "en":
            recovery_summary[lang] = (f"Current {absent} unavailable" if absent else "Current sleep, HRV and resting heart rate recorded")
        else:
            recovery_summary[lang] = (f"缺少当前{absent}" if absent else "已有当前睡眠、HRV 和静息心率记录")
    interpretations: dict[str, dict] = {}
    for metric, key, labels in (
        ("hrv", "hrv_trend", {"stable": ("stable", "稳定"), "declining": ("declining", "下降"), "improving": ("rising", "上升")}),
        ("rhr", "rhr_trend", {"stable": ("stable", "稳定"), "elevated": ("elevated", "偏高"), "low": ("lower", "偏低")}),
    ):
        trend = state.get(key)
        if evidence[f"recovery.{metric}"]["current"] and trend in labels:
            en, zh = labels[trend]
            name = "HRV rolling mean" if metric == "hrv" else "Resting heart rate"
            name_zh = "HRV 滚动均值" if metric == "hrv" else "静息心率"
            interpretations[f"{metric}.{trend}"] = {
                "requires": [f"recovery.{metric}"],
                "short_en": f"{'HRV trend' if metric == 'hrv' else 'resting heart rate'} {en}",
                "short_zh": f"{'HRV 趋势' if metric == 'hrv' else '静息心率'}{zh}",
                "en": f"{name}: {en} against the personal reference window.",
                "zh": f"相对既有个人参考窗口，{name_zh}{zh}。",
            }
        else:
            evidence[f"trend.{metric}"] = {
                "en": f"{'HRV' if metric == 'hrv' else 'Resting heart rate'} trend assessment awaits sufficient recent observations.",
                "zh": f"{'HRV' if metric == 'hrv' else '静息心率'}趋势解读等待有效的近期记录补齐。",
            }
    fitness = context.get("current_fitness") or {}
    if not (context.get("recent_training") or {}).get("sessions"):
        fitness = {}
    load_parts = []
    for key in ("ctl", "atl", "tsb"):
        value = fitness.get(key)
        if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value):
            load_parts.append(f"{key.upper()} {value:.1f}")
    load_text = ", ".join(load_parts)
    evidence["load.current"] = {
        "en": f"Modeled load on {as_of}: {load_text}. Read TSB as modeled load balance alongside recovery observations." if load_parts else "Current modeled load awaits training data.",
        "zh": f"{as_of} 的建模负荷：{load_text}。TSB 表示建模负荷平衡，可结合恢复观测一起参考。" if load_parts else "当前建模负荷解读等待训练数据补齐。",
    }
    start = as_of - timedelta(days=6)
    sessions = [s for s in (context.get("recent_training") or {}).get("sessions", [])
                if (d := _day(s.get("date"))) is not None and d <= as_of]
    week = [s for s in sessions if _day(s.get("date")) >= start]
    count = len(week)
    distances = [_number(s.get("distance_km"), score=False) for s in week]
    loads = [_number(s.get("rss"), score=False) for s in week]
    distance = f"{sum(v for v in distances if v is not None):g} km" if count and all(v is not None for v in distances) else None
    load = f"{sum(v for v in loads if v is not None):g}" if count and all(v is not None for v in loads) else None
    evidence["training.week"] = {
        "en": f"Recorded training {start}–{as_of}: {count} sessions; distance {distance or 'unavailable'}; load {load or 'unavailable'}. Coverage includes recorded sessions only.",
        "zh": f"{start} 至 {as_of} 的已记录训练：{count} 次；距离{distance or '不可用'}；负荷{load or '不可用'}。仅覆盖已记录的训练。",
    }
    if sessions:
        last = max(sessions, key=lambda s: str(s["date"]))
        distance_last = _number(last.get("distance_km"))
        evidence["training.recent"] = {
            "en": f"Latest recorded workout: {str(last['date'])[:10]}" + (f", {distance_last:g} km." if distance_last is not None else "; distance unavailable."),
            "zh": f"最近已记录训练：{str(last['date'])[:10]}" + (f"，{distance_last:g} km。" if distance_last is not None else "；距离不可用。"),
        }
        # Descriptive split evidence only. Select the longest measured power
        # split; never infer a zone, recovery cost or dose from activity avg_power.
        splits = [s for s in (last.get("splits") or []) if isinstance(s, dict)
                  and _number(s.get("duration_sec")) is not None
                  and _number(s.get("avg_power")) is not None and s.get("power_source")]
        if splits:
            split = max(splits, key=lambda s: s["duration_sec"])
            minutes, watts = split["duration_sec"] / 60, _number(split["avg_power"])
            evidence["training.split"] = {
                "en": f"The latest workout includes a recorded {minutes:g}-minute split averaging {watts:g} W. Keep this session in view when reviewing today's course.",
                "zh": f"最近一次训练包含一个 {minutes:g} 分钟、平均功率 {watts:g} W 的分段。查看今天的课程时，可一起参考这节训练的记录。",
            }
    else:
        evidence["training.recent"] = {"en": "No recent workout recorded in the available history.", "zh": "现有历史中没有近期训练记录。"}
    canonical_plan = context.get("planned_today")
    plan = canonical_plan if canonical_plan and canonical_plan.get("owner") != "external" else None
    external = _external_courses(context, as_of)
    rec = (context.get("today_signal") or {}).get("recommendation")
    # Every action is an existing canonical decision, with no invented dose.
    actions_by_signal = {
        "rest": ("Keep today for recovery.", "今天以恢复为主。"),
        "easy": ("Keep today's session easy.", "今天保持轻松训练。"),
        "modify": ("Modify today's session according to the Today signal.", "按今日信号调整今天的训练。"),
        "reduce_intensity": ("Reduce today's training intensity.", "降低今天的训练强度。"),
        "follow_plan": ("Follow today's scheduled workout.", "按今天已安排的训练执行。"),
        "unscheduled": ("Review the training plan before adding a session.", "添加训练前先查看训练计划。"),
    }
    if rec not in actions_by_signal or (canonical_plan is None and rec != "unscheduled"):
        raise ValueError("incoherent_canonical_action")
    reason_code = (context.get("today_signal") or {}).get("reason_code")
    action = actions_by_signal[rec]
    if reason_code == "unscheduled_hrv_caution":
        action = ("Rest, walk, or do gentle mobility.", "休息、散步或做轻柔的活动度练习。")
    elif reason_code == "unscheduled_high_load":
        action = ("Keep any optional movement easy and short.", "如需活动，保持轻松、简短。")
    elif rec == "modify":
        # Use the first canonical alternative, through fixed templates only.
        first = ((context.get("today_signal") or {}).get("alternative_codes") or [{}])[0].get("code")
        action = {
            "drop_to_easy": ("Switch today's session to an easy run.", "将今天的训练改为轻松跑。"),
            "drop_one_zone": ("Drop intensity by one zone.", "将强度降低一个区间。"),
            "proceed_monitor_body": ("Monitor how you feel during the planned session.", "按计划训练时留意身体感受。"),
            "run_easy": ("Run easy instead.", "改为轻松跑。"),
        }.get(first, action)
    if rec == "follow_plan" and plan:
        workout = _workout_label(plan)
        duration = _number(plan.get("planned_duration_min"))
        if workout:
            action = (f"Follow the planned {duration:g}-minute {workout[0]}." if duration else f"Follow the planned {workout[0]}.",
                      f"按计划完成 {duration:g} 分钟{workout[1]}。" if duration else f"按计划完成{workout[1]}。")
    plan_en = "No Praxys-managed workout is scheduled today." if plan is None else ("Praxys schedules recovery today." if reason_code == "rest_scheduled" else "Today's workout follows the Praxys-managed plan.")
    plan_zh = "今天暂无 Praxys 管理的训练安排。" if plan is None else ("Praxys 计划今天以恢复为主。" if reason_code == "rest_scheduled" else "今天按 Praxys 管理的训练计划安排。")
    for index, course in enumerate(external):
        provider = _platform_name(course)
        label_en, label_zh = _workout_label(course)
        target_en, target_zh = _course_targets(course)
        evidence[f"plan.external.{index}"] = {
            "en": f"{provider} lists an external {label_en}" + (f": {target_en}." if target_en else ".") + " The Praxys-managed plan takes priority.",
            "zh": f"{'外部平台' if provider == 'External' else provider} 显示一节外部{label_zh}" + (f"：{target_zh}。" if target_zh else "。") + "今日安排优先依据 Praxys 管理的计划。",
        }
    if plan is None and external:
        if len(external) == 1:
            course = external[0]
            provider = _platform_name(course)
            label_en, label_zh = _workout_label(course)
            plan_en = plan_en[:-1] + f"; {provider} lists an external {label_en} for reference."
            plan_zh = plan_zh[:-1] + f"；{'外部平台' if provider == 'External' else provider} 的{label_zh}可作为训练参考。"
            # External-course wording is conditional and uses existing course
            # values only. Canonical caution/recovery actions still win.
            if ((rec == "unscheduled" and reason_code == "unscheduled_open") or rec == "follow_plan"):
                low, high = (_number(course.get(key)) for key in ("target_power_min", "target_power_max"))
                target_en = f"use its {low:g}–{high:g} W target as a reference" if low is not None and high is not None and low <= high else "use its recorded targets as a reference"
                target_zh = f"以课程标注的 {low:g}–{high:g} W 为强度参考" if low is not None and high is not None and low <= high else "参考该课程已记录的目标"
                action = (f"If you choose the {provider} {label_en}, {target_en} and adjust execution to how you feel.",
                          f"如果选择{'外部平台' if provider == 'External' else provider} 的{label_zh}，{target_zh}，并结合身体感受调整执行。")
        else:
            plan_en = plan_en[:-1] + "; connected platforms list several external courses for reference."
            plan_zh = plan_zh[:-1] + "；已连接平台提供了多节外部课程参考。"
            if rec == "follow_plan":
                action = ("If you choose an external course, review that course's recorded targets alongside recovery.", "如果选择外部课程，结合恢复状态查看该课程已记录的目标。")
    elif plan is None and rec == "follow_plan":
        raise ValueError("missing_external_course")
    evidence["plan.today"] = {"en": plan_en, "zh": plan_zh}
    # Approved plan values, never descriptions from external free text.
    if plan:
        for key, en, zh, unit in (("planned_duration_min", "Duration", "时长", "min"), ("planned_distance_km", "Distance", "距离", "km")):
            val = _number(plan.get(key))
            if val is not None:
                evidence["plan.today"]["en"] += f" {en}: {val:g} {unit}."
                evidence["plan.today"]["zh"] += f"{zh}：{val:g} {unit}。"
    sessions_label = f"{count} recorded {'session' if count == 1 else 'sessions'} in seven days" if count else "No training recorded in the seven-day window"
    week_en = f"{sessions_label}" + (f", totaling {distance}" if distance else "") + "."
    week_zh = f"近七天{'记录 ' + str(count) + ' 次训练' if count else '暂无训练记录'}" + (f"，共 {distance}" if distance else "") + "。"
    if load is None:
        evidence["training.week"]["en"] += " Further load interpretation awaits complete session loads."
        evidence["training.week"]["zh"] += "进一步的负荷解读等待逐次训练数据补齐。"
    sleep_value = _number(state.get("sleep_score"), score=True) if evidence["recovery.sleep"]["current"] else None
    return {"evidence": evidence, "interpretations": interpretations,
            "actions": {f"today.{rec}": {"en": action[0], "zh": action[1]}},
            "recovery_summary": recovery_summary,
            "missing_recovery": bool(missing["en"]),
            "plan_summary": {"en": plan_en, "zh": plan_zh},
            "week_summary": {"en": week_en, "zh": week_zh},
            "sleep_value": sleep_value,
            "theory_refs": theory_refs(context.get("science") or {})}


def render_selection(raw: object, eligible: dict) -> dict:
    """Reject free text, ineligible IDs and unsupported ID combinations."""
    keys = {"evidence_ids": "evidence", "interpretation_ids": "interpretations", "action_ids": "actions"}
    if not isinstance(raw, dict) or set(raw) != set(keys):
        raise ValueError("selection_fields")
    for key, pool in keys.items():
        ids = raw[key]
        if (not isinstance(ids, list) or len(ids) > len(eligible[pool])
                or any(not isinstance(x, str) or x not in eligible[pool] for x in ids)
                or len(ids) != len(set(ids))):
            raise ValueError("selection_ids")
    # Mandatory coverage; model may order evidence, but cannot erase recovery,
    # recorded training, missingness, or the scheduled/no-plan distinction.
    if set(raw["evidence_ids"]) != set(eligible["evidence"]):
        raise ValueError("missing_evidence")
    if len(raw["action_ids"]) != 1:
        raise ValueError("missing_action")
    for key in raw["interpretation_ids"]:
        if not set(eligible["interpretations"][key]["requires"]) <= set(raw["evidence_ids"]):
            raise ValueError("unsupported_interpretation")
    translations = {}
    for lang in ("en", "zh"):
        recovery = eligible["recovery_summary"][lang]
        # At most two compact supported trend clauses; observations and their
        # individual dates remain fully available in the findings.
        trend_phrases = [eligible["interpretations"][key][f"short_{lang}"] for key in raw["interpretation_ids"]]
        if trend_phrases:
            trends = ("; " if lang == "en" else "，").join(trend_phrases)
            recovery = ((recovery + ("; " if lang == "en" else "；")) if eligible["missing_recovery"] else "") + trends
            if lang == "en":
                recovery = recovery[0].upper() + recovery[1:] + " against the personal reference window"
            else:
                recovery = "相对个人参考窗口，" + recovery
        sleep = eligible.get("sleep_value")
        if sleep is not None:
            recovery += f"; sleep score {sleep:g}" if lang == "en" else f"，睡眠评分为 {sleep:g}"
        recovery += "." if lang == "en" else "。"
        findings = []
        recovery_added = False
        for key in raw["evidence_ids"]:
            if key.startswith("recovery."):
                if not recovery_added:
                    findings.append({"type": "neutral", "text": " ".join(
                        eligible["evidence"][f"recovery.{metric}"][lang]
                        for metric in ("sleep", "hrv", "rhr"))})
                    recovery_added = True
            else:
                findings.append({"type": "neutral", "text": eligible["evidence"][key][lang]})
        translations[lang] = {
            "headline": "Recovery and training today" if lang == "en" else "今日恢复与训练",
            "summary": " ".join((recovery, eligible["week_summary"][lang], eligible["plan_summary"][lang])),
            "findings": findings,
            "recommendations": [eligible["actions"][key][lang] for key in raw["action_ids"]],
        }
    return {**translations["en"], "translations": translations}


def bind_payload(payload: dict, context: dict, selection: dict, eligible: dict) -> dict:
    """Attach server-owned provenance and separate input/content identities."""
    contract = {"version": CONTENT_VERSION, "snapshot": context["coach_snapshot"],
                "as_of_date": context["as_of_date"], "data_as_of": context.get("data_as_of"),
                "include_stryd": context["include_stryd_plan"], "selection": selection,
                "candidates": eligible}
    content_hash = digest([contract, payload])
    payload["meta_extra"] = {CONTRACT_KEY: contract, "input_hash": context["coach_snapshot"],
                             "content_version": CONTENT_VERSION, "dataset_hash": content_hash,
                             "theory_refs": eligible["theory_refs"]}
    return payload


def validate_stored(row: Any, expected_snapshot: str | None) -> bool:
    """Verify trusted provenance and exact re-rendered bilingual content."""
    from api.insight_feedback import GENERATION_PROVENANCE_KEY
    try:
        meta = row.meta
        contract = meta[CONTRACT_KEY]
        provenance = meta[GENERATION_PROVENANCE_KEY]
        if (not expected_snapshot or contract["snapshot"] != expected_snapshot
                or contract["version"] != CONTENT_VERSION
                or meta["content_version"] != CONTENT_VERSION
                or contract["as_of_date"] != date.today().isoformat()
                or meta["input_hash"] != expected_snapshot
                or not provenance.get("run_started_at")
                or set(provenance["source_revisions"]) != set(SCOPES)
                or snapshot_identity(row.user_id, provenance["source_revisions"], contract["as_of_date"], contract["include_stryd"]) != expected_snapshot):
            return False
        rendered = render_selection(contract["selection"], contract["candidates"])
        if any(getattr(row, k) != v for k, v in rendered.items()):
            return False
        return meta["dataset_hash"] == digest([contract, rendered])
    except (KeyError, TypeError, ValueError, AttributeError):
        return False
