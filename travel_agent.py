import os, json, requests, datetime, decimal, urllib.parse
from strands import Agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp

def load_secrets_from_aws(secret_name, region_name=None):
    try:
        import boto3
        session = boto3.session.Session()
        if region_name is None:
            region_name = os.environ.get('AWS_REGION', 'us-east-1')
        client = session.client(service_name='secretsmanager', region_name=region_name)
        secret = client.get_secret_value(SecretId=secret_name)['SecretString']
        for k, v in json.loads(secret).items(): os.environ[k] = v
        return json.loads(secret)
    except Exception as e:
        print(f"Warning: Could not load secrets from AWS Secrets Manager: {e}"); return {}

def try_load_secrets():
    sn = os.environ.get('AGENTCORE_SECRET_NAME','arn:aws:secretsmanager:us-east-1:484577546576:secret:agentcore/travelplanner/credentials-tmqDBh')
    if sn: load_secrets_from_aws(sn)
try_load_secrets()

# Normalise Snowflake account so users can pass either just the locator
# (e.g. "sfseapac-bsuresh") or the full host
# (e.g. "sfseapac-bsuresh.snowflakecomputing.com" or a full https URL).
_raw_acct = os.getenv("SNOWFLAKE_ACCOUNT")
if not _raw_acct:
    raise ValueError("SNOWFLAKE_ACCOUNT is not set. Check Secrets Manager config.")
_acct = _raw_acct.strip()
_acct = _acct.replace("https://", "").replace("http://", "")
_acct = _acct.split("/")[0]
if ".snowflakecomputing.com" in _acct:
    _acct = _acct.split(".snowflakecomputing.com")[0]
SNOWFLAKE_ACCOUNT = _acct

# Default to your actual Snowflake objects: database `travel_db`, schema `public`
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE", "travel_db")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "public")

# Default orchestration model for Claude via Bedrock/Strands (used only for Wikipedia destination extraction)
MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")

# Cortex Agent defaults – you have an agent at travel_db.public.TRAVEL_AGENT
CORTEX_AGENT_DATABASE = os.getenv("CORTEX_AGENT_DATABASE", SNOWFLAKE_DATABASE or "travel_db")
CORTEX_AGENT_SCHEMA = os.getenv("CORTEX_AGENT_SCHEMA", SNOWFLAKE_SCHEMA or "public")
CORTEX_AGENT_NAME = os.getenv("CORTEX_AGENT_NAME", "TRAVEL_AGENT")
CORTEX_BASE_URL = os.getenv("CORTEX_BASE_URL", f"https://{SNOWFLAKE_ACCOUNT}.snowflakecomputing.com")

# Wikipedia REST API configuration (for destination info lookups)
WIKI_BASE_URL = os.getenv("WIKI_BASE_URL", "https://en.wikipedia.org/api/rest_v1")
WIKI_USER_AGENT = os.getenv(
    "WIKI_USER_AGENT",
    "TravelPlannerAgent/1.0 (Snowflake-AWS-AgentCore-Travel-Planner)",
)

def _canon_ident(ident: str) -> str:
    """
    Normalise Snowflake identifiers for REST paths.
    - If the identifier is unquoted and all-lowercase, Snowflake will have stored it uppercased,
      so we upcase it for the REST API.
    - If it contains quotes or any uppercase characters, leave it as-is.
    """
    if not isinstance(ident, str):
        return ident
    if '"' in ident:
        return ident
    if ident.islower():
        return ident.upper()
    return ident

def _parse_cortex_sse(raw: str):
    """
    Parse a Cortex Agent text/event-stream response and return the last
    `response` event's data as a dict, if available.
    """
    last = None
    event_type = None
    data_lines = []

    # Iterate line-by-line over the entire stream, treating blank lines as
    # event boundaries. This closely mirrors how SSE is defined and matches
    # the Snowflake sample behaviour.
    for ln in raw.splitlines():
        stripped = ln.strip()
        if stripped == "":
            # End of current event block
            if event_type == "response" and data_lines:
                data_str = "\n".join(data_lines)
                try:
                    last = json.loads(data_str)
                except Exception:
                    # Ignore parse error for this block; keep going for later ones
                    pass
            event_type = None
            data_lines = []
            continue

        if ln.startswith("event:"):
            event_type = ln.split(":", 1)[1].strip()
        elif ln.startswith("data:"):
            data_lines.append(ln.split(":", 1)[1].lstrip())

    # Catch any trailing event without a final blank line
    if event_type == "response" and data_lines:
        try:
            last = json.loads("\n".join(data_lines))
        except Exception:
            pass

    return last if last is not None else {"raw": raw}

make_json_safe = lambda obj: {k: make_json_safe(v) for k, v in obj.items()} if isinstance(obj, dict) else [make_json_safe(v) for v in obj] if isinstance(obj, list) else str(obj) if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)) else float(obj) if isinstance(obj, decimal.Decimal) else obj


def _wiki_build_destinations_from_input(user_input: str, model: str = None):
    """
    Use Claude (via Strands) to extract destination names from a free-form
    travel query. This is only used for the optional Wikipedia lookup mode.
    """
    m = model or MODEL_ID
    system_prompt = (
        "You are a travel destination extractor.\n"
        "Given a user's natural language travel request, extract the main cities/countries\n"
        "they are travelling to (NOT the origin city) as a JSON object:\n"
        "{\n"
        '  "destinations": ["<city or country>", ...]\n'
        "}\n"
        "- Only output valid JSON (no backticks, no explanation).\n"
        "- Use concise Wikipedia-friendly titles, e.g. 'Singapore', 'Tokyo', 'Bali', 'Japan'.\n"
        "- If you can't infer any, return {\"destinations\": []}.\n"
    )
    agent = Agent(model=m, system_prompt=system_prompt)
    raw = str(agent(user_input or ""))
    # Try to parse raw as JSON; if that fails, try to extract the first {...} block.
    try:
        obj = json.loads(raw)
    except Exception:
        import re

        mobj = re.search(r"\{.*\}", raw, re.S)
        if not mobj:
            return {"destinations": [], "raw": raw}
        try:
            obj = json.loads(mobj.group(0))
        except Exception:
            return {"destinations": [], "raw": raw}

    dests = obj.get("destinations") or []
    if not isinstance(dests, list):
        dests = []
    # Normalise to simple strings
    norm = [str(d).strip() for d in dests if str(d).strip()]
    return {"destinations": norm, "raw": make_json_safe(obj)}


def _wiki_get_page_summary(title: str):
    """
    Call Wikipedia's REST API `/page/summary/{title}` to fetch a short summary
    for a given page title.

    This follows the reference OpenAPI spec the user provided and respects the
    required `User-Agent` header.
    """
    title = (title or "").strip()
    if not title:
        return {"error": "empty_title"}

    # Wikipedia expects spaces as underscores in titles
    encoded_title = urllib.parse.quote(title.replace(" ", "_"))
    url = f"{WIKI_BASE_URL}/page/summary/{encoded_title}"
    headers = {"User-Agent": WIKI_USER_AGENT}
    timeout_s = int(os.getenv("WIKI_TIMEOUT_SECONDS", "10"))

    try:
        resp = requests.get(url, headers=headers, timeout=timeout_s)
        if resp.status_code == 404:
            return {"title": title, "error": "not_found", "status_code": 404}
        resp.raise_for_status()
        data = resp.json()

        # Return a richer, travel-planner–friendly structure
        content_urls = data.get("content_urls") or {}
        desktop = content_urls.get("desktop") or {}
        thumb_obj = data.get("thumbnail") or {}
        orig_obj = data.get("originalimage") or {}
        thumb_src = thumb_obj.get("source")
        orig_src = orig_obj.get("source")

        images = []
        if thumb_src:
            images.append(thumb_src)
        if orig_src and orig_src != thumb_src:
            images.append(orig_src)

        return {
            "title": data.get("title", title),
            "extract": data.get("extract"),
            "lang": data.get("lang", "en"),
            "page_url": desktop.get("page"),
            "thumbnail": thumb_src,
            "images": images,
            "description": data.get("description"),
            "raw": make_json_safe(data),
        }
    except Exception as e:
        return {"title": title, "error": str(e)}


def wiki_destination_info(destinations):
    """
    Get Wikipedia summaries for one or more destination titles.

    IMPORTANT: This function does **not** infer destinations from the user
    query. The caller must explicitly pass the destination titles it wants
    summaries for, so Trip Plan behaviour remains unchanged.
    """
    if isinstance(destinations, str):
        destinations = [destinations]
    if not isinstance(destinations, list):
        return {"error": "destinations must be a string or a list of strings"}

    cleaned = [str(d).strip() for d in destinations if str(d).strip()]
    summaries = [_wiki_get_page_summary(title) for title in cleaned]
    return {
        "destinations": cleaned,
        "summaries": summaries,
    }


def wiki_travel_summary(wiki_info: dict, model: str = None) -> str:
    """
    Use Claude (via Strands) to turn raw Wikipedia destination info into a
    traveller-focused summary: why visit, key highlights, family-friendliness,
    safety/logistics notes, etc.
    """
    m = model or MODEL_ID
    system_prompt = (
        "You are a travel assistant.\n"
        "You are given JSON containing Wikipedia metadata for one or more travel destinations.\n"
        "Write a concise, traveller-focused markdown summary that:\n"
        "- Briefly introduces each destination (1–2 sentences).\n"
        "- Highlights top family-friendly attractions and experiences.\n"
        "- Mentions any notable culture, food, or neighborhoods that visitors should know.\n"
        "- Adds 2–4 practical notes: safety, transport basics, when to visit, or local tips.\n"
        "- Do NOT copy raw Wikipedia text verbatim; rewrite in your own words.\n"
        "- Do NOT invent specific statistics or facts that are not implied by the data.\n"
    )
    safe = make_json_safe(wiki_info or {})
    try:
        summary = str(Agent(model=m, system_prompt=system_prompt)(json.dumps(safe)))
    except Exception as e:
        summary = f"Could not summarize Wikipedia info: {e}"
    return summary


def wiki_destination_info_from_prompt(user_input: str):
    """
    High-level helper: given a free-form user query, first use Claude/Strands
    to extract destination names, then fetch Wikipedia summaries for those
    destinations.

    This is an additive capability and does NOT affect the main Trip Plan flow.
    """
    extraction = _wiki_build_destinations_from_input(user_input)
    dests = extraction.get("destinations") or []
    if not dests:
        # Nothing inferred – return just the extraction for debugging.
        return {
            "destinations": [],
            "summaries": [],
            "extraction": extraction,
            "travel_summary": "",
        }
    wiki = wiki_destination_info(dests)
    # Ask Claude to produce a traveller-oriented summary based on the wiki info.
    travel_summary = wiki_travel_summary({"extraction": extraction, "wiki": wiki})
    return {
        "destinations": wiki.get("destinations", dests),
        "summaries": wiki.get("summaries", []),
        "extraction": extraction,
        "travel_summary": travel_summary,
    }
def _call_cortex_agent(user_input):
    """
    Call your Snowflake Cortex Agent (travel_db.public.TRAVEL_AGENT by default)
    directly with the user's question, instead of invoking Cortex Analyst and
    Cortex Search separately.
    """
    token = os.getenv("SNOWFLAKE_AUTH_TOKEN")
    if not token:
        return {"error": "SNOWFLAKE_AUTH_TOKEN is not set. Check Secrets Manager."}

    db = _canon_ident(CORTEX_AGENT_DATABASE)
    sch = _canon_ident(CORTEX_AGENT_SCHEMA)
    name = _canon_ident(CORTEX_AGENT_NAME)
    # Official Cortex Agents endpoint:
    # /api/v2/databases/{DATABASE}/schemas/{SCHEMA}/agents/{AGENT}:run
    url = f"{CORTEX_BASE_URL}/api/v2/databases/{db}/schemas/{sch}/agents/{name}:run"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "X-Snowflake-Authorization-Token-Type": "PROGRAMMATIC_ACCESS_TOKEN",
    }
    body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": str(user_input),
                    }
                ],
            }
        ]
    }
    timeout_s = int(os.getenv("CORTEX_AGENT_TIMEOUT_SECONDS", "60"))
    try:
        # Call Cortex Agents. We request text/event-stream, but instead of manually
        # iterating the stream, we let `requests` buffer the body and then parse it
        # as a whole using `_parse_cortex_sse`. This avoids issues where iterating
        # `iter_lines()` can consume the stream and leave `resp.text` empty.
        resp = requests.post(url, headers=headers, json=body, timeout=timeout_s)
        resp.raise_for_status()

        # If Snowflake returns text/event-stream, parse it for the final `response` event.
        ctype = resp.headers.get("Content-Type", "")
        raw_text = resp.text or ""
        if "text/event-stream" in ctype and raw_text:
            return _parse_cortex_sse(raw_text)
        # If it's already JSON, just return it as-is.
        if "application/json" in ctype:
            try:
                return resp.json()
            except Exception:
                pass
        # Fallback: return whatever raw text we received for debugging.
        return {
            "raw": raw_text,
            "status_code": resp.status_code,
            "content_type": ctype,
        }
    except Exception as e:
        return {"error": f"Cortex Agent error: {e}"}

def _extract_agent_text(agent_resp):
    """
    Best-effort extraction of the main text answer from a Cortex Agent response.
    Falls back to JSON if we can't find a clean text field.
    """
    if isinstance(agent_resp, str):
        return agent_resp
    if not isinstance(agent_resp, dict):
        return str(agent_resp)

    for key in ("output", "answer", "text"):
        val = agent_resp.get(key)
        if isinstance(val, str):
            return val

    # Shape used by Cortex Agents: a top-level message with content items.
    content = agent_resp.get("content")
    if isinstance(content, list):
        texts = []
        for item in content:
            if not isinstance(item, dict):
                continue
            # Prefer content items explicitly marked as text
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                texts.append(item["text"])
            # Fallback: any direct text field
            elif isinstance(item.get("text"), str):
                texts.append(item["text"])
        if texts:
            return "\n\n".join(texts)

    msg = agent_resp.get("message") or agent_resp.get("final_message")
    if isinstance(msg, dict):
        contents = msg.get("content") or []
        if isinstance(contents, list):
            for c in contents:
                if isinstance(c, dict) and c.get("type") == "text" and isinstance(c.get("text"), str):
                    return c["text"]

    return json.dumps(agent_resp)

def cortex_agent_trip(user_input):
    """
    Single-call mode that delegates the entire planning task to your Snowflake
    Cortex Agent object (e.g. travel_db.public.TRAVEL_AGENT). This bypasses
    the explicit Cortex Analyst + Cortex Search calls in this file and lets
    the configured agent orchestration handle everything.
    """
    raw = _call_cortex_agent(user_input)
    if isinstance(raw, dict) and raw.get("error"):
        return {"error": raw["error"], "raw_context": make_json_safe(raw)}

    # Try to enrich the context with Wikipedia destination info inferred from
    # the same user input. This does NOT affect the main trip plan text, which
    # still comes entirely from the Cortex Agent in Snowflake.
    wiki_info = None
    try:
        wiki_info = wiki_destination_info_from_prompt(user_input)
    except Exception as e:
        wiki_info = {"error": str(e)}

    text = _extract_agent_text(raw)
    ctx = {"cortex_agent_response": raw}
    if wiki_info is not None:
        ctx["wiki_destination_info"] = wiki_info

    return {
        "best_trip_recommendation": text,
        "raw_context": make_json_safe(ctx),
    }
app = BedrockAgentCoreApp()
@app.entrypoint
def invoke(payload):
    user_input = payload.get("prompt") or payload.get("query")
    mode = (payload.get("mode") or "").lower()

    # Optional Wikipedia mode: fetch destination information via the Wikipedia API.
    # This is *additive* and does not change existing Trip Plan behaviour, because
    # current callers do not send `mode="wiki"`.
    if mode == "wiki":
        dests = payload.get("destinations") or payload.get("titles")
        if dests:
            return wiki_destination_info(dests)
        # If no explicit destinations were provided, infer them from the user input.
        return wiki_destination_info_from_prompt(user_input)

    # Always delegate the raw user input directly to the Cortex Agent in Snowflake,
    # without any additional modes or preprocessing.
    return cortex_agent_trip(user_input)
if __name__ == "__main__": app.run()
