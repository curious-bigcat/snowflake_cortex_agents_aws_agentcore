"""
Streamlit UI for the Travel Planner demo.

This file is intentionally kept thin: all heavy lifting (Cortex Agent calls,
Wikipedia lookups, summarisation) is done in `travel_agent.py` via Bedrock
AgentCore. Here we:
- Collect a free-form travel prompt.
- Invoke the AgentCore runtime.
- Render the returned trip plan, structured tables, and wiki destination info.
"""

import os, json, streamlit as st
import uuid, boto3
from botocore.config import Config

# ======================
# Basic Page & Style
# ======================
st.set_page_config("Travel Planner AI", "", layout="centered")

st.markdown(
    """
    <style>
      :root{--bg:#f7f8fb;--ink:#0f172a;--muted:#6b7280;--line:#e5e7eb;--brand:#1e3c72;--cta:#2563eb}
      html,body,[class*="css"]{background:var(--bg)!important;color:var(--ink)}
      .wrap{border:1px solid var(--line);border-radius:16px;padding:16px;background:#fff;box-shadow:0 8px 28px rgba(2,6,23,.06)}
      .title{display:flex;gap:10px;align-items:center;font:800 1.6rem system-ui;color:var(--brand)}
      .badge{display:inline-flex;gap:6px;align-items:center;font:700 .7rem system-ui;color:#1d4ed8;background:#eef2ff;border:1px solid #dbeafe;border-radius:999px;padding:2px 8px}
      .card{border:1px solid var(--line);border-radius:14px;padding:14px;background:#fff;box-shadow:0 6px 20px rgba(15,23,42,.06);margin:8px 0}
      .card h4{margin:0 0 6px;font:800 1.05rem system-ui;color:#1f5fbf}
      .muted{color:var(--muted)}
      .foot{margin-top:22px;color:#9aa3ad;font-size:.95rem;text-align:center;border-top:1px dashed var(--line);padding-top:10px}
      .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}
    </style>
    """,
    unsafe_allow_html=True,
)

# ======================
# Sidebar (Region / ARN / Mode)
# ======================
st.sidebar.title("Settings")

def get_region():
    region = os.environ.get("AWS_REGION")
    if not region:
        region = st.sidebar.text_input("AWS Region", value="us-east-1", key="region_input")
    return region or "us-east-1"

REGION = get_region()

def get_agentcore_client(region_name=None):
    region = region_name or REGION
    # Increase Bedrock AgentCore timeouts so long-running trip plans don't hit client read timeouts.
    read_t = int(os.environ.get("AGENTCORE_READ_TIMEOUT", "300"))
    conn_t = int(os.environ.get("AGENTCORE_CONNECT_TIMEOUT", "10"))
    cfg = Config(read_timeout=read_t, connect_timeout=conn_t)
    return boto3.client("bedrock-agentcore", region_name=region, config=cfg)

agent_arn = st.sidebar.text_input("Agent ARN", value="", key="agent_arn_input")

if "runtime_session_id" not in st.session_state:
    st.session_state.runtime_session_id = str(uuid.uuid4())
st.sidebar.caption("Session")
st.sidebar.code(st.session_state.runtime_session_id, language="bash")

# ======================
# Header
# ======================
st.markdown(
    """
    <div class="wrap">
      <div class="title">Travel Planner
        <span class="badge">AI Assistant</span>
      </div>
      <div class="kicker muted">One prompt → flights, hotels & a day-wise plan.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ======================
# Trip prompt form
# ======================
with st.form("planner"):
    prompt = st.text_area(
        "Where do you want to go?",
        "I want to go from Delhi to Pune for 3 nights, need a hotel with breakfast, and a sightseeing plan",
        height=110
    )
    submitted = st.form_submit_button("Plan My Trip")

# ======================
# Helpers (UI only)
# ======================
card = lambda t, h: st.markdown(f"<div class='card'><h4>{t}</h4>{h}</div>", unsafe_allow_html=True)

def parse_event_stream(lines_iter):
    """
    Minimal event-stream helper: assumes backend eventually emits one JSON object as `data: ...`.
    Uses tolerant UTF-8 decoding to avoid crashes on partial multibyte sequences.
    """
    chunks = []
    for raw in lines_iter:
        if not raw:
            continue
        try:
            line = raw.decode("utf-8", errors="ignore")
        except Exception:
            # Fallback: best-effort decode
            line = str(raw)
        if line.startswith("data: "):
            chunks.append(line[6:])
    raw_text = "".join(chunks)
    try:
        return json.loads(raw_text), raw_text
    except Exception:
        return {"raw": raw_text}, raw_text

# ======================
# Submit flow: call Bedrock AgentCore runtime
# ======================
raw, data = None, None
if submitted:
    if not agent_arn:
        st.error("Agent ARN is required to invoke the agent. Please provide it in the sidebar.")
    else:
        try:
            with st.spinner("Planning your trip…"):
                client = get_agentcore_client(REGION)
                payload = json.dumps({"prompt": prompt}).encode()
                response = client.invoke_agent_runtime(
                    agentRuntimeArn=agent_arn,
                    runtimeSessionId=st.session_state.runtime_session_id,
                    payload=payload
                )
                ct = response.get("contentType", "")
                if "text/event-stream" in ct:
                    data, raw = parse_event_stream(response["response"].iter_lines(chunk_size=10))
                elif "application/json" in ct:
                    raw = "".join([chunk.decode("utf-8") for chunk in response.get("response", [])])
                    try: data = json.loads(raw)
                    except Exception: data = {"raw": raw}
                else:
                    raw = str(response)
                    data = {"raw": raw}
        except Exception as e:
            st.error(f"Request failed: {e}")

if submitted and raw is not None:
    with st.expander("Debug: Backend Response", expanded=False):
        st.write("Session ID:", st.session_state.runtime_session_id)
        st.write("Agent ARN:", agent_arn)
        st.write("Raw Response:", raw)
        if data: st.json(data)

st.markdown(
    "<div class='foot'>© 2025 Travel Planner AI — Powered by AWS Bedrock AgentCore, AWS Strands, Snowflake Data Cloud & Cortex AI</div>",
    unsafe_allow_html=True,
)

# ======================
# Main Display: Wikipedia info, trip plan, and raw context
# ======================
if data:
    best = data.get("best_trip_recommendation")
    raw_context = data.get("raw_context")

    # Wikipedia destination info first, to give rich context before raw JSON.
    if isinstance(raw_context, dict):
        wiki_info = raw_context.get("wiki_destination_info")
        if isinstance(wiki_info, dict):
            summaries = wiki_info.get("summaries") or []
            travel_summary = wiki_info.get("travel_summary") or ""
            if summaries or travel_summary:
                with st.expander("Destination Info (Wikipedia)", expanded=True):
                    # High-level traveller-focused summary from Claude (if available)
                    if isinstance(travel_summary, str) and travel_summary.strip():
                        st.markdown("#### Travel Highlights")
                        st.markdown(travel_summary)
                        st.markdown("---")

                    # Per-destination rich cards
                    for s in summaries:
                        if not isinstance(s, dict):
                            continue
                        title = s.get("title") or "Destination"
                        extract = s.get("extract") or ""
                        page_url = s.get("page_url")
                        thumb = s.get("thumbnail")
                        images = s.get("images") or []
                        desc = s.get("description")

                        st.markdown(f"### {title}")
                        # Show primary thumbnail if available
                        if thumb:
                            st.image(thumb, width=260)
                        # Show any additional images (e.g., original image) for richer visuals
                        for img in images:
                            if img and img != thumb:
                                st.image(img, width=260)
                        if desc:
                            st.markdown(f"**Short description:** {desc}")
                        if extract:
                            st.markdown(f"**Overview:** {extract}")
                        if page_url:
                            st.markdown(f"[Open on Wikipedia]({page_url})")
                        st.markdown("---")

    if best:
        card("Travel Plan", f"<div class='mono' style='white-space:pre-wrap'>{best}</div>")
    if raw_context:
        with st.expander("Raw Context (from agent)", expanded=False):
            st.json(raw_context)

        # Additionally, try to surface any structured tables the Cortex Agent returned
        # (e.g. flights and hotels) in a friendlier format, similar to the Snowflake UI.
        cortex_resp = raw_context.get("cortex_agent_response")
        if isinstance(cortex_resp, dict):
            for item in cortex_resp.get("content", []):
                if not isinstance(item, dict):
                    continue
                if item.get("type") != "table":
                    continue
                table_block = item.get("table") or {}
                title = table_block.get("title") or "Details"
                rs = table_block.get("result_set") or {}
                meta = (rs.get("resultSetMetaData") or {})
                row_type = meta.get("rowType") or []
                # Column names come from rowType metadata
                columns = [col.get("name", f"col_{i}") for i, col in enumerate(row_type)]
                rows = rs.get("data") or []
                if not columns or not rows:
                    continue
                # Map each row to a dict for nicer display; limit to first N rows for readability
                max_rows = 30
                row_dicts = [dict(zip(columns, r)) for r in rows[:max_rows]]
                with st.expander(f"Details: {title}", expanded=False):
                    st.table(row_dicts)
