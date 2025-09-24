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


