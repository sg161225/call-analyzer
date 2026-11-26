"""One call, three ways: 📊 Visual · 📄 Detailed · 🎧 Recording."""
from __future__ import annotations

import html
import math

import pandas as pd
import streamlit as st

from callanalyzer import store
from callanalyzer.calltypes import CALL_TYPES, sections_for
from callanalyzer.quality import SHORT_FATAL, SOFT_SKILLS
from callanalyzer.review import PARAMETERS

GOOD, WARN, BAD, BLUE, NA = "#0ca30c", "#e0a100", "#d03b3b", "#2a78d6", "#a9adb5"
TRACK, LINE = "rgba(128,128,128,.18)", "rgba(128,128,128,.28)"
MOMENT_COLOR = {"Checklist done": GOOD, "Positive": GOOD, "Objection": WARN, "Missed": BAD, "Fatal": BAD,
                "Outcome": BLUE, "Other": NA}
MOOD_COLOR = {"Positive": GOOD, "Neutral": NA, "Negative": BAD}
RATE_COLOR = {"Good": GOOD, "Partial": WARN, "Weak": BAD}
ICON = {"Good": "✅", "Partial": "🟡", "Weak": "❌", "Yes": "✅", "No": "❌", "Not applicable": "➖"}
VIEWS = ["📊 Visual", "📄 Detailed", "🎧 Recording"]


def mmss(t: float | None) -> str:
    t = int(t or 0)
    return f"{t // 60}:{t % 60:02d}"


def esc(s) -> str:
    return html.escape(str(s or ""))


def chip(text: str, color: str) -> str:
    return (f"<span style='display:inline-block;padding:2px 10px;border-radius:999px;font-size:.8rem;font-weight:600;"
            f"color:{color};background:color-mix(in srgb,{color} 14%,transparent)'>{esc(text)}</span>")


def _seek(t: float) -> None:
    """Jump the recording to t seconds and switch to the Recording view."""
    st.session_state["cv_seek"] = int(t)
    st.session_state["cv_autoplay"] = True
    st.session_state["cv_mode"] = VIEWS[2]


# ---------------------------------------------------------------------------------------------
def render(r: pd.Series, rv: dict, raw: pd.Series, nav_ids: list[int]) -> None:
    segments = raw.get("segments") or []
    stats = raw.get("audio") or {}
    if st.session_state.get("cv_call") != r["id"]:          # new call: reset player position
        st.session_state.update(cv_call=r["id"], cv_seek=0, cv_autoplay=False)

    _header(r, rv, nav_ids)
    mode = st.segmented_control("View", VIEWS, key="cv_mode", default=VIEWS[0], label_visibility="collapsed") or VIEWS[0]
    if r["Fatal"]:
        _fatal_banner(r)
    if mode == VIEWS[0]:
        _visual(r, rv, segments, stats)
    elif mode == VIEWS[1]:
        _detailed(r, rv)
    else:
        _recording(r, rv, segments, stats)


# ---- header ----------------------------------------------------------------------------------
def _header(r, rv, nav_ids):
    score = int(rv.get("overall_score") or 0)
    col = BAD if r["Fatal"] else GOOD if score >= 7 else WARN if score >= 5 else BAD
    circ = 2 * math.pi * 40
    icon = CALL_TYPES.get(r["Call type"], {}).get("icon", "")
    outcome = r["Outcome"]
    oc = GOOD if any(k in outcome for k in ("received", "completed", "resolved")) else \
        BAD if any(k in outcome for k in ("Lost", "escalated")) else WARN
    facts = [f"{icon} {esc(r['Call type'])}", f"📅 {r['Date']:%d %b %Y}" if pd.notna(r["Date"]) else "",
             f"⏱ {mmss(r['Minutes'] * 60)}", f"📱 {esc(r['Mobile'])}" if r["Mobile"] else "",
             f"💰 ₹{int(r['Deal value']):,}" if r["Deal value"] else ""]
    badges = (chip("⛔ FATAL", BAD) if r["Fatal"] else chip("No fatal errors", GOOD) if r["Assessed"] else "") + " " + chip(outcome, oc)
    st.markdown(f"""
<div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap;border:1px solid {LINE};border-radius:12px;padding:14px 18px;margin:8px 0">
  <div style="position:relative;width:84px;height:84px;flex:none">
    <svg viewBox="0 0 92 92" width="84" height="84" style="transform:rotate(-90deg)">
      <circle cx="46" cy="46" r="40" fill="none" stroke="{TRACK}" stroke-width="9"/>
      <circle cx="46" cy="46" r="40" fill="none" stroke="{col}" stroke-width="9" stroke-linecap="round"
              stroke-dasharray="{circ * score / 10:.1f} {circ:.1f}"/></svg>
    <div style="position:absolute;inset:0;display:grid;place-items:center;text-align:center;line-height:1">
      <div><div style="font-size:1.6rem;font-weight:700">{score}</div><div style="font-size:.7rem;opacity:.7">/ 10</div></div></div>
  </div>
  <div style="flex:1;min-width:220px">
    <div style="font-size:1.35rem;font-weight:700">{esc(r['Executive'])} · {esc(r['Customer'] or r['File'])}</div>
    <div style="display:flex;flex-wrap:wrap;gap:4px 16px;opacity:.8;font-size:.88rem;margin-top:2px">{''.join(f'<span>{f}</span>' for f in facts if f)}</div>
    <div style="margin-top:6px;font-size:.9rem">{esc(rv.get('one_line_summary', ''))}</div>
  </div>
  <div style="display:flex;gap:6px;flex-wrap:wrap">{badges}</div>
</div>""", unsafe_allow_html=True)
    if r["id"] in nav_ids and len(nav_ids) > 1:
        i = nav_ids.index(r["id"])
        c1, c2, c3 = st.columns([1, 1, 6])
        c1.button("◀ Previous call", disabled=i == 0, key="cv_prev", width="stretch",
                  on_click=lambda: st.session_state.update(detail_id=nav_ids[i - 1]))
        c2.button("Next call ▶", disabled=i == len(nav_ids) - 1, key="cv_next", width="stretch",
                  on_click=lambda: st.session_state.update(detail_id=nav_ids[i + 1]))
        c3.caption(f"Call {i + 1} of {len(nav_ids)} in the current filter")


def _fatal_banner(r):
    items = "".join(f"<li><b>{mmss(e.get('time_sec')) + ' · ' if e.get('time_sec') else ''}"
                    f"{esc(SHORT_FATAL.get(e['category'], e['category']))}</b>: “{esc(e.get('evidence'))}”</li>"
                    for e in r["Fatal errors"])
    st.markdown(f"""<div style="border:2px solid {BAD};border-radius:10px;padding:10px 16px;margin:6px 0 10px;
background:color-mix(in srgb,{BAD} 8%,transparent)"><b style="color:{BAD}">⛔ FATAL CALL</b>: the executive made a blunder
<ul style="margin:6px 0 0">{items}</ul></div>""", unsafe_allow_html=True)
    times = [e.get("time_sec") for e in r["Fatal errors"] if e.get("time_sec")]
    if times:
        st.button(f"🎧 Listen to the fatal moment ({mmss(times[0])})", key="cv_fatal_listen",
                  on_click=_seek, args=(max(0, times[0] - 3),))


# ---- 📊 visual ---------------------------------------------------------------------------------
def _timeline_html(rv, length):
    moments, moods = rv.get("moments") or [], rv.get("mood_timeline") or []
    L = max(1, length)
    band = "".join(f"<div title='Customer mood: {esc(m['mood'])}' style='position:absolute;top:34px;height:10px;"
                   f"left:{m['start_sec'] / L * 100:.2f}%;width:{max(0.5, (min(m['end_sec'], L) - m['start_sec']) / L * 100):.2f}%;"
                   f"background:{MOOD_COLOR.get(m['mood'], NA)};opacity:.55;border-radius:3px'></div>" for m in moods)
    dots = "".join(f"<div title='{mmss(m['time_sec'])} · {esc(m['text'])}' style='position:absolute;top:6px;width:16px;height:16px;"
                   f"border-radius:50%;left:{min(m['time_sec'], L) / L * 100:.2f}%;transform:translateX(-50%);"
                   f"background:{MOMENT_COLOR.get(m['kind'], NA)};border:2px solid rgba(255,255,255,.9)'></div>" for m in moments)
    ticks = "".join(f"<span>{mmss(L * f)}</span>" for f in (0, .25, .5, .75, 1))
    legend = " ".join(f"<span style='margin-right:12px'><span style='display:inline-block;width:10px;height:10px;border-radius:50%;"
                      f"background:{c};margin-right:4px'></span>{k}</span>"
                      for k, c in (("Done / positive", GOOD), ("Objection", WARN), ("Missed / fatal", BAD), ("Outcome", BLUE)))
    return f"""<div style="position:relative;height:52px;margin:6px 8px 0">
<div style="position:absolute;left:0;right:0;top:37px;height:4px;border-radius:2px;background:{TRACK}"></div>{band}{dots}</div>
<div style="display:flex;justify-content:space-between;font-size:.72rem;opacity:.7;margin:0 2px">{ticks}</div>
<div style="font-size:.78rem;opacity:.8;margin-top:6px">{legend} · band underneath = customer mood
(<span style="color:{GOOD}">positive</span> / neutral / <span style="color:{BAD}">negative</span>)</div>"""


def _moment_buttons(rv, key):
    moments = rv.get("moments") or []
    cols = st.columns(2)
    for i, m in enumerate(moments):
        dot = {GOOD: "🟢", WARN: "🟠", BAD: "🔴", BLUE: "🔵"}.get(MOMENT_COLOR.get(m["kind"], NA), "⚪")
        cols[i % 2].button(f"{dot} {mmss(m['time_sec'])} · {m['text']}", key=f"{key}_{i}", width="stretch",
                           on_click=_seek, args=(max(0, m["time_sec"] - 2),),
                           help="Play the recording from this moment")


def _talk_split(rv, segments):
    ex = set(rv.get("executive_lines") or [])
    if not segments or not ex:
        return None
    dur = lambda s: max(0.0, float(s.get("end") or 0) - float(s.get("start") or 0))  # noqa: E731
    e = sum(dur(s) for i, s in enumerate(segments) if i in ex)
    c = sum(dur(s) for i, s in enumerate(segments) if i not in ex)
    return e / (e + c) if e + c else None


def _visual(r, rv, segments, stats):
    length = int(r["Minutes"] * 60) or (int(segments[-1]["end"]) if segments else 0)
    with st.container(border=True):
        st.markdown("**🕒 Call timeline** · dots are key moments; click one below to hear it")
        if rv.get("moments"):
            st.markdown(_timeline_html(rv, length), unsafe_allow_html=True)
            _moment_buttons(rv, "vm")
        else:
            st.caption("The timeline is available for calls uploaded from now on (older reviews have no time stamps).")

    c1, c2 = st.columns(2, gap="medium")
    with c1.container(border=True):
        st.markdown("**Scorecard**")
        rows = []
        for key, label in PARAMETERS.items():
            if key == "acpt_improvement":
                continue
            rating = (rv.get(key) or {}).get("rating")
            lvl = {"Good": 3, "Partial": 2, "Weak": 1}.get(rating, 0)
            c = RATE_COLOR.get(rating, NA)
            bars = "".join(f"<i style='display:inline-block;width:24px;height:10px;border-radius:3px;margin-right:4px;"
                           f"background:{c if k <= lvl else TRACK}'></i>" for k in (1, 2, 3))
            rows.append(f"<div style='display:grid;grid-template-columns:1.4fr auto auto;gap:10px;align-items:center;"
                        f"padding:7px 0;border-bottom:1px solid {LINE}'><span>{esc(label)}</span><span>{bars}</span>"
                        f"<span>{chip(rating or '—', c)}</span></div>")
        st.markdown("".join(rows), unsafe_allow_html=True)
    with c2.container(border=True):
        st.markdown("**Soft skills**")
        ss = rv.get("soft_skills") or {}
        if not ss:
            st.caption("Not assessed (call reviewed before soft skills were added).")
        else:
            gauges = []
            for key in ("empathy", "humility", "fluency"):
                sk = ss.get(key) or {}
                rating = sk.get("rating")
                v = {"Good": 1, "Partial": .6, "Weak": .25}.get(rating, 0)
                a = math.pi * (1 - v)
                x, y = 55 + 45 * math.cos(a), 55 - 45 * math.sin(a)
                c = RATE_COLOR.get(rating, NA)
                gauges.append(f"""<div style="text-align:center;min-width:0">
<svg viewBox="0 0 110 62" width="110" height="62"><path d="M10 55 A45 45 0 0 1 100 55" fill="none" stroke="{TRACK}" stroke-width="10" stroke-linecap="round"/>
<path d="M10 55 A45 45 0 0 1 {x:.1f} {y:.1f}" fill="none" stroke="{c}" stroke-width="10" stroke-linecap="round"/></svg>
<div style="font-weight:600;font-size:.85rem">{esc(SOFT_SKILLS[key][0])}</div><div>{chip(f"{ICON.get(rating, '')} {rating}", c)}</div>
<div style="font-size:.78rem;opacity:.75;margin-top:2px">{esc(sk.get('evidence'))}</div></div>""")
            st.markdown(f"<div style='display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px'>{''.join(gauges)}</div>",
                        unsafe_allow_html=True)

    c3, c4 = st.columns(2, gap="medium")
    with c3.container(border=True):
        st.markdown("**Conversation**")
        split = _talk_split(rv, segments)
        if split is not None:
            st.markdown(f"""<div style="font-size:.85rem;margin-bottom:4px">Talk time (approx.):
<b style="color:{BLUE}">Executive {split:.0%}</b> · Customer {1 - split:.0%}</div>
<div style="display:flex;height:12px;border-radius:6px;overflow:hidden;background:{TRACK}">
<div style="width:{split * 100:.0f}%;background:{BLUE}"></div><div style="flex:1;background:{NA};opacity:.6"></div></div>""",
                        unsafe_allow_html=True)
            if split > 0.7:
                st.caption("⚠️ The executive talked most of the call; good calls usually let the customer speak more.")
        da = stats.get("dead_air") or {}
        if da:
            msg = (f"Dead air: **{da['count']}** pause(s) of {da.get('min_len', 4):.0f}s or more"
                   + (f" ({da['total_sec']:.0f}s total, longest {da['longest_sec']:.0f}s)" if da["count"] else " 🎉"))
            st.markdown(msg)
        moods = rv.get("mood_timeline") or []
        if moods:
            st.markdown("Customer mood: " + " → ".join(chip(m["mood"], MOOD_COLOR.get(m["mood"], NA)) for m in moods),
                        unsafe_allow_html=True)
        else:
            st.markdown(f"Customer mood: {chip(rv.get('customer_sentiment_start', '—'), NA)} → "
                        f"{chip(rv.get('customer_sentiment_end', '—'), NA)}", unsafe_allow_html=True)
        if split is None and not da:
            st.caption("Talk time and dead air are measured for calls uploaded from now on.")
    with c4.container(border=True):
        st.markdown(f"**{r['Call type']} checklist**")
        given = {c["item"]: c.get("done") for c in r["Checklist"] or []}
        cards = []
        for name, items in sections_for(r["Call type"]):
            app = [given.get(i) for i in items if given.get(i) in ("Yes", "No")]
            if not app:
                continue
            p = sum(a == "Yes" for a in app) / len(app)
            c = GOOD if p >= .8 else WARN if p >= .5 else BAD
            cards.append(f"<div style='border:1px solid {LINE};border-radius:8px;padding:8px 10px'>"
                         f"<div style='font-size:.78rem;opacity:.75'>{esc(name)}</div><div style='font-weight:700;font-size:1.1rem'>{p:.0%}</div>"
                         f"<div style='height:6px;border-radius:3px;background:{TRACK};overflow:hidden'><div style='width:{max(4, p * 100):.0f}%;"
                         f"height:100%;background:{c}'></div></div><div style='font-size:.72rem;opacity:.7'>{sum(a == 'Yes' for a in app)} of {len(app)}</div></div>")
        st.markdown(f"<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px'>{''.join(cards)}</div>"
                    if cards else "<span style='opacity:.7'>No checklist for this call.</span>", unsafe_allow_html=True)


# ---- 📄 detailed -------------------------------------------------------------------------------
def _detailed(r, rv):
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.markdown("**Scorecard: your six columns**")
        for key, label in PARAMETERS.items():
            a = rv.get(key)
            if key == "acpt_improvement":
                with st.expander(f"**{label}**", expanded=True):
                    for i, tip in enumerate(a or [], 1):
                        st.markdown(f"{i}. {tip}")
                continue
            if not a:
                continue
            with st.expander(f"{ICON.get(a.get('rating'), '')} **{label}** · {a.get('rating')}", expanded=key == "business_probing"):
                if key == "customer_queries":
                    for q in a.get("queries", []):
                        st.markdown(f"- {q}" + (" ❗ *unresolved*" if q in a.get("unresolved", []) else ""))
                    continue
                if key == "pitch":
                    st.markdown(f"*Features:* {', '.join(a.get('features_mentioned') or []) or 'none'}  \n"
                                f"*Offers:* {', '.join(a.get('offers_made') or []) or '**none**'}")
                st.markdown(f"*Observed:* {a.get('observed', '')}  \n*Improve:* {a.get('improvement', '')}")
        with st.container(border=True):
            st.markdown("**Outcome & next step**")
            st.markdown(f"- Outcome: **{r['Outcome']}** · {rv.get('outcome_note', '')}\n"
                        + (f"- Next step: **{r['Next step']}**" + (f" (due {r['Next step date']:%d %b})" if pd.notna(r["Next step date"]) else "") + "\n" if r["Next step"] else "")
                        + (f"- Deal value: **₹{int(r['Deal value']):,}** {r['Deal note']}\n" if r["Deal value"] else "")
                        + (f"- Loss reason: {r['Loss reason']}\n" if r["Loss reason"] not in ("None", "") else "")
                        + (f"- Risk: **{r['Risk']}**: {r['Risk reason']}\n" if r["Risk"] not in ("None", "") else ""))
    with c2:
        with st.container(border=True):
            st.markdown(f"**{r['Call type']} checklist with evidence**")
            for name, items in sections_for(r["Call type"]):
                given = {c["item"]: c for c in r["Checklist"] or []}
                st.markdown(f"<div style='font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;opacity:.7;margin-top:6px'>{esc(name)}</div>",
                            unsafe_allow_html=True)
                for it in items:
                    c = given.get(it, {})
                    st.markdown(f"{ICON.get(c.get('done'), '➖')} {esc(it)} <span style='opacity:.65;font-size:.88em'>· {esc(c.get('evidence', 'not checked'))}</span>",
                                unsafe_allow_html=True)
        if r["Objections"]:
            with st.container(border=True):
                pct = r["Playbook %"]
                st.markdown("**🛡️ Objections vs playbook**" + (f" · {pct:.0%} handled the playbook way" if pct is not None else ""))
                mark = {"Yes": "✅ Followed", "Partly": "🟡 Partly", "No": "❌ Not followed"}
                for o in r["Objections"]:
                    st.markdown(f"**{esc(o['objection'])}** · {mark.get(o['playbook_followed'], '')}  \n"
                                f"<span style='opacity:.75'>Customer: “{esc(o.get('customer_said'))}” · Executive: “{esc(o.get('executive_response'))}”</span>",
                                unsafe_allow_html=True)
                    if o["playbook_followed"] != "Yes" and o.get("recommended_response"):
                        st.markdown(f"💬 *Should say:* {o['recommended_response']}")
        ss = rv.get("soft_skills") or {}
        if ss:
            with st.container(border=True):
                st.markdown("**Soft skills**")
                for key in ("empathy", "humility", "fluency"):
                    sk = ss.get(key) or {}
                    st.markdown(f"{ICON.get(sk.get('rating'), '')} **{SOFT_SKILLS[key][0]}** · {sk.get('rating')}: {sk.get('evidence', '')}")


# ---- 🎧 recording ------------------------------------------------------------------------------
def _wave_html(peaks, length, rv, cursor):
    n = len(peaks) or 1
    pos = cursor / max(1, length)
    bars = "".join(f"<i style='flex:1;min-width:1px;border-radius:2px;height:{max(6, p * 100):.0f}%;"
                   f"background:{BLUE if (i + .5) / n <= pos else NA}'></i>" for i, p in enumerate(peaks))
    marks = "".join(f"<span title='{mmss(m['time_sec'])} · {esc(m['text'])}' style='position:absolute;top:-4px;bottom:-4px;width:3px;"
                    f"border-radius:2px;left:{min(m['time_sec'], length) / max(1, length) * 100:.2f}%;"
                    f"background:{MOMENT_COLOR.get(m['kind'], NA)}'></span>" for m in rv.get("moments") or [])
    return (f"<div style='position:relative;height:64px;display:flex;align-items:center;gap:2px;margin:4px 0'>{bars}{marks}</div>"
            f"<div style='display:flex;justify-content:space-between;font-size:.72rem;opacity:.7'>"
            f"{''.join(f'<span>{mmss(length * f)}</span>' for f in (0, .25, .5, .75, 1))}</div>")


def _line_flags(rv, segments):
    """Mark transcript lines where a fatal error, objection or missed point happened."""
    flags = {}

    def line_at(t):
        best = None
        for i, s in enumerate(segments):
            if float(s.get("start") or 0) <= t:
                best = i
        return best

    for m in rv.get("moments") or []:
        i = line_at(m["time_sec"])
        if i is not None and m["kind"] in ("Fatal", "Objection", "Missed"):
            flags[i] = {"Fatal": "⛔", "Objection": "⚠️", "Missed": "❌"}[m["kind"]] if flags.get(i) != "⛔" else "⛔"
    for e in rv.get("fatal_errors") or []:
        if e.get("time_sec"):
            i = line_at(e["time_sec"])
            if i is not None:
                flags[i] = "⛔"
    return flags


def _recording(r, rv, segments, stats):
    rec = store.get_recording(int(r["id"]))
    length = int(r["Minutes"] * 60) or (int(segments[-1]["end"]) if segments else 0)
    seek = int(st.session_state.get("cv_seek") or 0)
    if rec:
        with st.container(border=True):
            autoplay = bool(st.session_state.pop("cv_autoplay", False))
            st.audio(rec["audio"], format=rec["mime"], start_time=seek, autoplay=autoplay)
            st.markdown(_wave_html(rec["peaks"], length, rv, seek), unsafe_allow_html=True)
            st.caption(f"Starting at {mmss(seek)}. Coloured lines on the waveform are key moments. "
                       "Click a moment or a transcript line to jump there.")
            d1, d2, _ = st.columns([1, 1, 3])
            d1.download_button("⬇️ Recording (MP3)", rec["audio"], f"call_{r['id']}.mp3", mime=rec["mime"], width="stretch")
            if segments:
                ex = set(rv.get("executive_lines") or [])
                who = (lambda i: "Executive" if i in ex else "Customer") if ex else (lambda i: "")
                txt = "\n".join(f"[{mmss(s['start'])}] {who(i) + ': ' if who(i) else ''}{s['text']}" for i, s in enumerate(segments))
                d2.download_button("⬇️ Transcript (.txt)", txt.encode("utf-8"), f"call_{r['id']}_transcript.txt", width="stretch")
    else:
        st.info("The recording isn't stored for this call. Recordings are kept for calls uploaded from now on "
                "(setting `keep_recordings` in config/settings.toml).")

    c1, c2 = st.columns([1, 2], gap="medium")
    with c1.container(border=True):
        st.markdown("**Key moments**")
        if rv.get("moments"):
            for i, m in enumerate(rv["moments"]):
                dot = {GOOD: "🟢", WARN: "🟠", BAD: "🔴", BLUE: "🔵"}.get(MOMENT_COLOR.get(m["kind"], NA), "⚪")
                st.button(f"{dot} {mmss(m['time_sec'])} · {m['text']}", key=f"rm_{i}", width="stretch",
                          on_click=_seek, args=(max(0, m["time_sec"] - 2),), disabled=not rec)
        else:
            st.caption("No time-stamped moments for this call.")
    with c2.container(border=True):
        st.markdown("**Transcript** (English) · select a line to play from there")
        if not segments:
            st.caption("No transcript stored for this call.")
            return
        ex = set(rv.get("executive_lines") or [])
        flags = _line_flags(rv, segments)
        q = st.text_input("Search the transcript", key=f"tx_q_{r['id']}", placeholder="e.g. refund, GST, price",
                          label_visibility="collapsed")
        df = pd.DataFrame({
            "i": range(len(segments)),
            "Time": [mmss(s["start"]) for s in segments],
            "": [flags.get(i, "") for i in range(len(segments))],
            "Speaker": [("Executive" if i in ex else "Customer") if ex else "" for i in range(len(segments))],
            "Text": [s["text"] for s in segments],
            "_start": [s["start"] for s in segments],
        })
        if q.strip():
            df = df[df["Text"].str.contains(q.strip(), case=False, regex=False)]
            st.caption(f"{len(df)} line(s) match “{q.strip()}”.")
        sel = st.dataframe(df.drop(columns=["_start"]), hide_index=True, width="stretch", height=380,
                           on_select="rerun", selection_mode="single-row", key=f"tx_{r['id']}",
                           column_config={"i": None, "Time": st.column_config.TextColumn(width="small"),
                                          "": st.column_config.TextColumn(width="small"),
                                          "Speaker": st.column_config.TextColumn(width="small"),
                                          "Text": st.column_config.TextColumn(width="large")})
        rows = sel.selection.rows if sel and sel.selection else []
        if rows:
            t = int(df.iloc[rows[0]]["_start"])
            if t != seek:
                st.session_state.update(cv_seek=t, cv_autoplay=True)
                st.rerun()
        st.caption("⛔ fatal · ⚠️ objection · ❌ missed point. Speaker labels are worked out by the AI and can be "
                   "wrong when two people talk in one line.")
    with st.expander("📜 Read the full transcript"):
        tint = {"⛔": BAD, "⚠️": WARN, "❌": BAD}
        lines = []
        for i, s_ in enumerate(segments):
            f = flags.get(i, "")
            who = ("Executive" if i in ex else "Customer") if ex else ""
            bg = f"background:color-mix(in srgb,{tint[f]} 12%,transparent);" if f else ""
            lines.append(f"<div style='display:grid;grid-template-columns:48px 86px 1fr;gap:8px;padding:5px 8px;border-radius:6px;{bg}'>"
                         f"<span style='opacity:.65'>{mmss(s_['start'])}</span>"
                         f"<b style='color:{BLUE if who == 'Executive' else 'inherit'}'>{who}</b><span>{f} {esc(s_['text'])}</span></div>")
        st.markdown("".join(lines), unsafe_allow_html=True)
