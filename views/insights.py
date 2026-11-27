import streamlit as st

from views.common import filters, load_flat
from callanalyzer import store
from callanalyzer.config import load_settings, missing_keys
from callanalyzer.review import insights_report


def downloads(r: dict, key: str) -> None:
    """PDF (for sharing) and Markdown downloads for one saved report."""
    when = str(r["created_at"]).replace("T", " ")[:16]
    stamp = str(r["created_at"])[:10].replace("-", "")
    c1, c2, _ = st.columns([1.3, 1.3, 3])
    try:
        from callanalyzer.pdf import report_pdf
        company = load_settings()["company"]["name"]
        pdf = report_pdf(r["content_md"], f"{company} · Call insights report",
                         f"Generated {when}  ·  {r['scope']}", f"{company} call insights · {when}")
        c1.download_button("📄 Download PDF", pdf, f"call_insights_{stamp}.pdf", "application/pdf",
                           key=f"pdf_{key}", type="primary", width="stretch")
    except Exception as e:  # never block the page if the PDF can't be made
        c1.caption(f"PDF not available: {type(e).__name__}: {e}")
    c2.download_button("⬇️ Markdown (.md)", r["content_md"].encode(), f"call_insights_{stamp}.md",
                       key=f"md_{key}", width="stretch")

st.title("💡 AI insights")
st.caption("The AI reads all the call reviews in the selection and writes a report: what's working, what isn't, "
           "how the executives compare, how pitches changed over time, and how to improve the process.")

raw, flat = load_flat()
if flat.empty:
    st.info("No reviewed calls yet.")
    st.stop()

view = filters(flat, "ins")
st.write(f"**{len(view)} call(s)** selected.")
focus = st.text_input("Anything to focus on? (optional)",
                      placeholder="e.g. why dropped customers are not renewing; compare Sachin's October vs November pitch")

settings = load_settings()
need = [k for k in missing_keys(settings, engine="none")]
has_key = not need
if need:
    st.error(f"Missing key: {', '.join(need)}. Add it on the **Settings** page (left menu).")
if st.button("Generate report", type="primary", disabled=view.empty or not has_key):
    reviews = raw.set_index("id").loc[view["id"]]
    rows = [{"executive": r["executive"], "date": r["call_date"], "campaign": r["campaign"],
             "pitch_version": r["pitch_version"], **r["review"], "call_type": r.get("call_type") or r["review"].get("call_type")} for _, r in reviews.iterrows()]
    status = st.empty()
    with st.spinner(f"Analysing {len(rows)} call reviews… larger selections take a few minutes on the free tier."):
        try:
            md = insights_report(rows, settings, focus, progress=lambda m: status.caption(m))
        except Exception as e:
            st.error(f"{type(e).__name__}: {e}")
            st.stop()
    scope = f"{len(rows)} calls" + (f"; focus: {focus}" if focus else "")
    store.save_report(scope, md)
    st.rerun()

reports = store.load_reports()
if reports:
    latest, older = reports[0], reports[1:]
    st.divider()
    st.subheader(f"Latest report · {latest['created_at'].replace('T', ' ')}")
    st.caption(latest["scope"])
    downloads(latest, "latest")
    st.markdown(latest["content_md"])
    downloads(latest, "latest_end")
    for r in older:
        with st.expander(f"{r['created_at'].replace('T', ' ')} · {r['scope']}"):
            downloads(r, str(r.get("id", r["created_at"])))
            st.markdown(r["content_md"])
