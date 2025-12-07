# snowflake_aws_agentcore

## Overview

**Snowflake AWS AgentCore** is an enterprise-grade, multi-agent travel planning system. It generates complete, data-driven travel itineraries—including flights, hotels, and day-wise plans—from a single user prompt. The system leverages:

- **LLMs (Anthropic Claude via AWS Bedrock)** for intent extraction, reasoning, and plan generation
- **Snowflake Cortex Analyst & Search** for real-time flight/hotel data and semantic travel guide search
- **AWS Bedrock AgentCore** for secure, scalable orchestration
- **Streamlit** for a modern, interactive frontend

---

## Features

- **Unified Prompt:** Enter your travel needs in natural language; get flights, hotels, and a day-wise itinerary.
- **Multi-city, Round-trip Support:** Handles complex itineraries and user preferences.
- **LLM-Powered Recommendations:** Uses Claude for intent extraction, reasoning, and plan generation.
- **Live Data:** Queries real-time flight/hotel data and travel guides from Snowflake.
- **Modern, Minimal UI:** Streamlit frontend with tabs, tables, and a professional, condensed design.
- **Cloud-Native:** Deployable to AWS Bedrock AgentCore for production use.
- **Secure Secrets Management:** Uses AWS Secrets Manager for all credentials and sensitive config.
- **Highly Maintainable:** The codebase is concise, with all repetitive logic factored out and helpers inlined where possible.

---

## Architecture

- **Frontend:** Streamlit (Python)
- **Backend:** Python, BedrockAgentCoreApp (AWS)
- **Data/AI:**
  - Snowflake Cortex Analyst (NL-to-SQL for flights/hotels)
  - Snowflake Cortex Search (semantic search for travel guides)
  - Anthropic Claude (via AWS Bedrock)
  - AWS Bedrock AgentCore & Strands (agent orchestration)
- **Deployment:** Docker, AWS Bedrock AgentCore Runtime
- **Secrets:** AWS Secrets Manager

---

## Project Structure

```
agentcore/
├── my_new_travel_agent.py              # Main agent code (BedrockAgentCoreApp, highly condensed)
├── streamlit_coordinator_travel_agent.py # Streamlit UI (modern, minimal, and optimized)
├── requirements.txt                   # Python dependencies
├── bedrock_agentcore.yaml             # AgentCore config
├── Dockerfile                         # For container builds
├── agentcore-prereqs.yaml             # CloudFormation for IAM, ECR, Secrets Manager
├── snowflake_setup_worksheet.sql      # Step-by-step Snowflake setup worksheet
├── FLIGHT.csv, HOTEL.csv              # Sample data for Snowflake
├── Travel_Plan_Guide.pdf              # Travel guide PDF (for Cortex Search)
├── ...
```

---

## Detailed Setup & Deployment Guide

### 1. Snowflake Setup

**a. Create Database, Schema, and Tables**
- Log in to your Snowflake account (via web UI or SnowSQL CLI).
- Run the provided SQL script to create the necessary database, schema, and tables:

```sql
CREATE OR REPLACE DATABASE TRAVEL_DB;
USE DATABASE TRAVEL_DB;
CREATE OR REPLACE SCHEMA PUBLIC;

-- Flights table
CREATE OR REPLACE TABLE PUBLIC.flight_data (
    airline STRING,
    source STRING,
    destination STRING,
    price NUMBER,
    duration NUMBER,
    total_stops NUMBER,
    dep_time STRING,
    arrival_time STRING
);

-- Hotels table
CREATE OR REPLACE TABLE PUBLIC.hotel_data (
    name STRING,
    city STRING,
    price NUMBER,
    rating NUMBER
);
```

**b. Load Sample Data**
- Use the Snowflake UI or SnowSQL to load your sample CSVs:

```sql
PUT file:///path/to/FLIGHT.csv @%PUBLIC.flight_data;
COPY INTO PUBLIC.flight_data FROM @%PUBLIC.flight_data FILE_FORMAT = (TYPE = 'CSV' FIELD_OPTIONALLY_ENCLOSED_BY='"');

PUT file:///path/to/HOTEL.csv @%PUBLIC.hotel_data;
COPY INTO PUBLIC.hotel_data FROM @%PUBLIC.hotel_data FILE_FORMAT = (TYPE = 'CSV' FIELD_OPTIONALLY_ENCLOSED_BY='"');
```

### 2. Cortex Analyst Configuration

- Ensure you have access to Snowflake Cortex Analyst (contact your Snowflake admin if unsure).
- Create or update a semantic model YAML file (e.g., `FLIGHT_ANALYTICS.yaml`) and upload it to a Snowflake stage:

```sql
CREATE OR REPLACE STAGE PUBLIC.DATA;
PUT file:///path/to/FLIGHT_ANALYTICS.yaml @PUBLIC.DATA;
PUT file:///path/to/HOTEL_ANALYTICS.yaml @PUBLIC.DATA;
```
- Note the stage path (e.g., `@TRAVEL_DB.PUBLIC.DATA/FLIGHT_ANALYTICS.yaml`) for use in your agent config.

#### Creating or Updating a Semantic View (Semantic Model) in Snowsight

You can create a semantic view using the wizard or by uploading a YAML file:

**A. Using the Wizard**
- In Snowsight, go to Data » Databases, select your database and schema.
- Click Create » Semantic View » Create with guided setup.
- Follow the wizard to select tables, columns, and define facts, dimensions, metrics, and relationships.
- Save your semantic view.

**B. Uploading a YAML Specification**
- In Snowsight, go to Data » Databases, select your database and schema.
- Click Create » Semantic View » Upload YAML file.
- Select your YAML file and upload it.
- Choose the database, schema, and stage for the file.
- Click Upload.

**Editing and Sharing**
- Edit semantic views from the Semantic views tab in Snowsight or Cortex Analyst.
- Share access by selecting More options » Share and choosing the appropriate role.

**Best Practices**
- Use clear, business-friendly names and descriptions.
- Add representative user questions and synonyms.
- Test with real business questions and iterate.

### 3. Cortex Search Configuration

- Set up a Cortex Search service in your Snowflake account (requires admin privileges).
- Create a search index on your travel guide or documentation data:

```sql
CREATE OR REPLACE TABLE PUBLIC.travel_guides (
    CHUNK STRING
);
-- Load your travel guide data into this table
-- Then create a search index:
CREATE OR REPLACE SEARCH INDEX travel_guides_index ON PUBLIC.travel_guides(CHUNK);

-- Register the search service (replace with your actual service name)
CREATE OR REPLACE CORTEX SEARCH SERVICE TRAVEL_SEARCH_SERVICE ON PUBLIC.travel_guides_index;
```
- Note the database, schema, and service name for your agent config.

### 4. AWS Configuration

**a. Secrets Manager**
- Store your Snowflake credentials and config as a JSON secret:

```json
{
  "SNOWFLAKE_ACCOUNT": "your_account",
  "SNOWFLAKE_USER": "your_user",
  "SNOWFLAKE_PASSWORD": "your_password",
  "SNOWFLAKE_DATABASE": "TRAVEL_DB",
  "SNOWFLAKE_SCHEMA": "PUBLIC",
  "SNOWFLAKE_WAREHOUSE": "XSMALL_WH",
  "CORTEX_ANALYTIST_URL": "https://<account>.snowflakecomputing.com/api/v2/cortex/analyst/message",
  "SEMANTIC_MODEL_FILE": "@TRAVEL_DB.PUBLIC.DATA/FLIGHT_ANALYTICS.yaml",
  "HOTEL_SEMANTIC_MODEL_FILE": "@TRAVEL_DB.PUBLIC.DATA/HOTEL_ANALYTICS.yaml",
  "CORTEX_SEARCH_DATABASE": "TRAVEL_DB",
  "CORTEX_SEARCH_SCHEMA": "PUBLIC",
  "CORTEX_SEARCH_SERVICE": "TRAVEL_SEARCH_SERVICE"
}
```
- Save the ARN of this secret for use in your environment variables.

**b. IAM Permissions**
- Ensure your AWS user/role has permissions for Secrets Manager and (if needed) S3.

### 5. CloudFormation Setup (Optional, for IaC)

- Use AWS CloudFormation to automate infrastructure setup (Secrets Manager, IAM roles, etc.).
- Example CloudFormation snippet for a secret:

```yaml
Resources:
  TravelAgentSecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: agentcore/travelplanner/credentials
      SecretString: '{ ... }'  # Your JSON config here
```
- Deploy with:
```sh
aws cloudformation deploy --template-file your_template.yaml --stack-name travel-agent-stack
```

### 6. AgentCore Configuration and Launch

- Ensure all environment variables are set (either via AWS Secrets Manager or manually):

```sh
export AGENTCORE_SECRET_NAME=arn:aws:secretsmanager:us-east-1:xxxx:secret:agentcore/travelplanner/credentials-xxxx
```
- Install Python dependencies:
```sh
pip install -r requirements.txt
```
- Launch the agent:
```sh
python my_new_travel_agent.py
```
- The agent will start as a service (API or CLI, depending on your configuration).

### 7. Streamlit App Configuration and Launch (Optional UI)

- If you have a Streamlit frontend (e.g., `streamlit_coordinator_travel_agent.py`):
- Install Streamlit if not already installed:
```sh
pip install streamlit
```
- Launch the app:
```sh
streamlit run streamlit_coordinator_travel_agent.py
```
- Configure the app to point to your running agent service (update API endpoint in the Streamlit script if needed).

---

## Step-by-Step Setup & Run Guide

You can follow the **Snowflake-first → AWS AgentCore → Streamlit** flow below.

### 1. Prerequisites

- **Snowflake** account with Cortex Agents enabled.
- **AWS** account with:
  - Bedrock + AgentCore access.
  - Permissions for AWS Secrets Manager.
- **Local dev machine** with Python 3.9+ and the ability to run Streamlit.

### 2. Snowflake Setup (Data + Cortex Agent)

1. Open `snowflake_setup_worksheet.sql` in Snowsight.
2. Run it step-by-step (or as a whole) to:
   - Create `TRAVEL_DB.PUBLIC`.
   - Create and load `FLIGHT_DATA`, `HOTEL_DATA`.
   - Stage the travel guide PDF and configure Cortex Search over it.
   - Create the **Cortex Agent** `TRAVEL_DB.PUBLIC.TRAVEL_AGENT` with tools like:
     - `hotel_flight_analyst` (Cortex Analyst),
     - `cortex_search` (travel guides),
     - `data_to_chart` (charts).
3. Verify in Snowsight:
   - Data is present in `TRAVEL_DB.PUBLIC.FLIGHT_DATA` and `HOTEL_DATA`.
   - `TRAVEL_AGENT` appears under Data » Agents and answers a simple question.

> The Python app only talks to this single `TRAVEL_AGENT` via REST; it never calls Analyst/Search directly.

### 3. AWS Secrets Manager Configuration

Create a JSON secret (for example `agentcore/travelplanner/credentials`) with at least:

```json
{
  "SNOWFLAKE_ACCOUNT": "your_account_locator_or_host",
  "SNOWFLAKE_DATABASE": "TRAVEL_DB",
  "SNOWFLAKE_SCHEMA": "PUBLIC",
  "CORTEX_AGENT_DATABASE": "TRAVEL_DB",
  "CORTEX_AGENT_SCHEMA": "PUBLIC",
  "CORTEX_AGENT_NAME": "TRAVEL_AGENT",
  "SNOWFLAKE_AUTH_TOKEN": "<PROGRAMMATIC_ACCESS_TOKEN>",
  "MODEL_ID": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
  "WIKI_USER_AGENT": "YourAppName/1.0 (contact@example.com)"
}
```

Notes:
- `SNOWFLAKE_ACCOUNT` can be either the account locator or full host; the code normalises it.
- `SNOWFLAKE_AUTH_TOKEN` must be a **programmatic access token** with permission to run the Cortex Agent.

Record the **secret ARN**; you’ll use it as `AGENTCORE_SECRET_NAME`.

### 4. Run the AgentCore App (`travel_agent.py`)

Install dependencies:

```bash
cd snowflake_aws_agentcore
pip install -r requirements.txt
```

For **local testing**:

```bash
export AGENTCORE_SECRET_NAME="<arn:aws:secretsmanager:...:secret:agentcore/travelplanner/credentials-...>"
python travel_agent.py
```

In AWS AgentCore, deploy `travel_agent.py` (and its dependencies) as a runtime, and set `AGENTCORE_SECRET_NAME` in the runtime’s environment.

The entrypoint `invoke(payload)` expects:

- `payload["prompt"]`: user’s travel question.
- (Optional) `payload["mode"] == "wiki"`: for wiki-only responses.

For normal Trip Plan calls (no `mode`), it returns:

```jsonc
{
  "best_trip_recommendation": "<markdown trip plan>",
  "raw_context": {
    "cortex_agent_response": { "...": "..." },
    "wiki_destination_info": {
      "destinations": ["Tokyo", "Singapore"],
      "summaries": [/* per-destination wiki data */],
      "travel_summary": "<markdown travel highlights>"
    }
  }
}
```

### 5. Streamlit UI

From the project root:

```bash
pip install streamlit
streamlit run streamlit_coordinator_travel_agent.py
```

In the Streamlit app:

1. Set **AWS Region** in the sidebar (e.g. `us-east-1`).
2. Paste your **Agent ARN** (Bedrock AgentCore runtime ARN).
3. Enter a free-form prompt such as:
   - “Plan an 8-day family trip from Bengaluru to Singapore, with hotels, sightseeing and budget.”
4. Click **“Plan My Trip”**.

The app will show:

- **Destination Info (Wikipedia)** – Claude-written travel highlights plus cards for each destination (images, descriptions, links).
- **Travel Plan** – Markdown trip plan from Snowflake `TRAVEL_AGENT`.
- **Raw Context (from agent)** – Full JSON, plus flight/hotel tables rendered under “Details: …” expanders.

## Security & Best Practices
- **Secrets:** All credentials are stored in AWS Secrets Manager and loaded at runtime. Never hardcode secrets.
- **IAM:** The agent runs with least-privilege IAM permissions (see CloudFormation template).
- **Networking:** For production, restrict access to ECR, Secrets Manager, and Bedrock AgentCore via VPC or security groups.
- **Auditing:** Use AWS CloudTrail and CloudWatch for monitoring and auditing agent activity.
- **Data:** All data at rest and in transit is encrypted by default (Snowflake, AWS, etc.).

---

## Troubleshooting & FAQ
- **Streamlit error: AGENT_ENDPOINT not set**
  - Set the endpoint as described above.
- **Request failed: ...**
  - Check agent logs in AWS CloudWatch.
  - Ensure the agent is running and the endpoint is correct.
- **Port 8080 in use (local)**
  - Free the port: `lsof -i :8080` then `kill -9 <PID>`
- **Agent returns string, not JSON**
  - Ensure your entrypoint returns a dict, not a string.
- **OpenTelemetry/OTLP errors**
  - These are non-blocking unless you want tracing. Ignore or disable tracing if not needed.
- **Secrets not loading**
  - Ensure `AGENTCORE_SECRET_NAME` is set to the correct ARN and IAM permissions are correct.
- **Snowflake connection errors**
  - Double-check all Snowflake credentials and network access.

---


