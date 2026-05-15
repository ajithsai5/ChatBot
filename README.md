# UHCCP Internal Chatbot

AI-powered internal chatbot for the UHCCP DevOps team. It provides a web UI and REST APIs to answer questions using Azure OpenAI and Azure AI Search, plus domain-specific tools for Rally (Agile) data, ServiceNow tickets, Splunk traffic metrics, Dynatrace problems, and CRuX/SEO performance.

This document explains architecture, setup, configuration, endpoints, tooling, deployment, and troubleshooting.


### Overview

- Web server: Flask app serving HTML/JS UI and JSON APIs
- LLM: Azure OpenAI Chat Completions (deployment "UHCCP_ChatBot")
- Embeddings + retrieval: Azure OpenAI embeddings (deployment "UHCCP_Vector") + Azure AI Search index "uhccp-vector"
- Tooling: Rich function tool-calls to query Rally, incidents/problems/changes (ServiceNow Data Mart), Splunk traffic, Dynatrace problems, performance (user actions), and CRuX metrics
- Logging: Structured usage logs shipped to Logstash
- Deployment: Docker (multi-stage) and Kubernetes manifests with ingress/service/network policy


## Features

- Chat UI with Markdown rendering and basic sanitization hooks
- Persona-aware responses optimized for UHCCP queries
- Hybrid RAG: searched context from Azure AI Search combined with tool results
- Follow-up question suggestions and link packaging
- Multiple REST endpoints for chat, metrics, and health
- Optional metrics endpoint aggregating Elasticsearch usage and feedback


## Architecture

### Core components

- `main.py`
	- Flask app and routes
		- `GET /` → renders `templates/index.html`
		- `GET /uhccp` → renders `templates/uhccp_index.html`
		- `GET|POST /chat` and `/uhccp-internal-chatbot/chat`
			- Accepts query param `msg` and optional `context` (GET) or JSON `{history, username}` (POST)
			- Calls `pynote.get_chatbot_response` and returns a JSON-encoded `response` string (line breaks converted to `<br>`)
		- `POST /chatbot` and `/uhccp-internal-chatbot/chatbot`
			- Accepts JSON `{message, context}` and returns JSON `{response, context}`
		- `GET /health` and `/uhccp-internal-chatbot/health` → returns `OK`
		- `GET /persona_usage` → queries Elasticsearch indices for usage and feedback; returns `{count, daily_count[], feedback_positive, feedback_negative, pie_data[]}`
		- `GET /uhccp-internal-chatbot/static/<path>` → serves files from `static/`
	- CORS enabled; max request size 16 MB
	- Uses `env_variables.env` to toggle development and endpoints

- `pynote.py`
	- Orchestrates persona, tool calls, RAG search, and final chat response
	- Uses Azure AI Search + OpenAI chat completions via `vector.py`
	- Exposes `get_chatbot_response(question, ...)` for `/chat` and `chat_bot_response(question)` for `/chatbot`

- `vector.py`
	- Azure OpenAI embeddings client (deployment `UHCCP_Vector`)
	- Azure OpenAI chat client (deployment `UHCCP_ChatBot`)
	- Azure AI Search client (index `uhccp-vector`)
	- Key functions:
		- `get_embeddings(text)` → returns embedding vector
		- `get_vectorized_query(search, scrum=False)` → returns Azure Search `VectorizedQuery`
		- `search_documents(search, vectorized_queries, ...)` → returns concatenated chunks + file metadata
		- `single_chatbot_response(messages, outdata, long_res, ...)` → gets final LLM answer; may augment with tool outputs
	- Uses `file_link.json` mapping `{file_name: link}` to append “For more information…” link to chat answers

- `system_messages.py`
	- Persona/system prompt strings for chat instructions (e.g., avoid third-person, respect Rally IDs)

- `personas.py`
	- Declares persona tool list and default search service/index
	- Wraps `tools.tools` and adds a `search_client` to the persona via Azure AI Search credential

- `tools/` module
	- `tools.py` → registry of tool-callable functions with OpenAI tool schema (names, descriptions, parameters)
	- `tool_calls.py` → translates OpenAI tool calls to concrete function invocations and aggregates results
	- `rally_funcs.py` → Rally-related queries via internal UHCCP endpoints (iterations/releases/features/stories/defects/capabilities)
	- `tickets_funcs.py` → Incident/Problem/Change queries and related suggestions (Data Mart via `psycopg2`), Splunk traffic, Dynatrace problems, CRuX and performance reports
	- `vbf_list.py` → enumerates allowable VBF values for CRuX filtering

- `env_variables.py`
	- `Environment` class toggles DEV/SCRUM/RALLY flags
	- Configures internal service endpoints for `CHATBOT_ENDPOINT` and `TICKETS_ENDPOINT`
	- Reads sensitive keys from environment:
		- `AZURE_AI_Service_KEY` (Azure OpenAI)
		- `AZURE_Search_Service_KEY` (Azure AI Search)

- `chatbot_logger.py`
	- `ChatbotLogger` packages per-interaction metadata and POSTs to Logstash endpoint
	- Fields include index tags, persona, environment, username, ask_type, question, answer

### Frontend

- Templates: `templates/index.html`, `templates/uhccp_index.html`, `templates/exit.html`
	- Loads `/uhccp-internal-chatbot/static/styles.css` and either `scripts.js` or `uhccp_scripts.js`
	- Imports `marked` for Markdown rendering; uses `DOMPurify` if available for sanitization
- Static JS: `static/scripts.js` (uses `/chat`) and `static/uhccp_scripts.js` (uses `/chatbot`)
	- Shows animated “Thinking…” indicator; abortable requests; basic conversation panel rendering
	- Expects JSON responses like `{response, context}`
- Styles: `static/styles.css` with responsive chat layout and Markdown-friendly styles


## API Endpoints

- `GET /` → HTML home
- `GET /uhccp` → HTML home (UHCCP variant)
- `GET|POST /chat` and `/uhccp-internal-chatbot/chat`
	- GET: `?msg=...&context=...`
	- POST: JSON `{history?: [], username?: string}`; query params still used for `msg`
	- Returns JSON-encoded string: `{response, questions?, persona, urlInfo?}`
- `POST /chatbot` and `/uhccp-internal-chatbot/chatbot`
	- Body: `{message: string, context?: string}`; returns `{response: string, context: string}`
- `GET /health` and `/uhccp-internal-chatbot/health` → `OK`
- `GET /persona_usage`
	- Hits internal Elasticsearch endpoints, returns an object with:
		- `count`: total unique question count
		- `daily_count`: array of `{date, count}`
		- `feedback_positive`, `feedback_negative`
		- `pie_data`: counts by persona


## Tooling and Data Sources

### Rally functions (`tools/rally_funcs.py`)

Functions expect parameters like `team`, `iteration`, `release`, `feature`, `from_date`, `to_date`, and boolean flags `ai`, `milestone`, `ppm`. They compose URLs to `env.get_tickets_endpoint()` (Dev vs Prod) and return textual summaries of JSON responses.

- `get_user_stories`, `get_features`, `get_capabilites`
- `get_defects`, `get_release_defects`, `get_release_features`
- `get_current_iterations`, `get_current_releases`
- `get_rally_obj_info(FormattedID)` and `get_rally_obj_info_no_id(...)`
- Helpers: `set_rally_teams()`, `get_allowed_teams()`

### Ticket and metrics functions (`tools/tickets_funcs.py`)

- ServiceNow Data Mart via `psycopg2`:
	- `get_latest_inc`, `get_latest_prb`, `get_latest_chg` (last 30 days)
	- Requires env vars `DATA_MART_DB_USER`, `DATA_MART_DB_PASSWORD`
- Related ticket discovery: `get_related_tickets`, `get_related_stories`
- Splunk traffic: `get_splunk_report({from_date, to_date})` aggregations of 4xx/5xx and total traffic by VBF
- Dynatrace problems: `get_dynatrace_problems` (requires `DYNATRACE_API` bearer token)
- CRuX metrics: `get_crux_report({from_date, to_date, VBF?})`
- Performance: `get_performance_score({from_date, to_date})` using `user_actions*`

### Retrieval augmented generation (`vector.py`)

- Embeddings: Azure OpenAI `UHCCP_Vector`
- Chat: Azure OpenAI `UHCCP_ChatBot`
- Search: Azure AI Search index `uhccp-vector` with fields `chunk` and `title`
- File links: `file_link.json` mapping of documentation names to external URLs


## Configuration

### Environment variables

Set the following in your environment (PowerShell examples below):

- Azure keys
	- `AZURE_AI_Service_KEY` → Azure OpenAI API key
	- `AZURE_Search_Service_KEY` → Azure AI Search admin/query key
- Data Mart (ServiceNow) DB
	- `DATA_MART_DB_USER`, `DATA_MART_DB_PASSWORD`
- Dynatrace
	- `DYNATRACE_API` → `Authorization` header value (e.g., `Api-Token <token>`)

Optional toggles are handled programmatically via `env_variables.env.set_env(dev=False, scrum=False, rally=False)`.

### Certificates

- `optum.pem` and `standard_trusts.pem` are used for TLS verification in internal requests. Keep them secure and do not commit secrets.

### File links

- `file_link.json` holds `{ "DocName.md": "https://..." }` entries used to enrich chat answers with “For more information…” links.


## Local Development

Prerequisites:

- Python 3.11
- Access to required internal services (UHCCP endpoints, Elasticsearch, Dynatrace) and keys

Setup (PowerShell):

```powershell
# From repo root
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt

# Required environment variables (examples)
$env:AZURE_AI_Service_KEY = "<your-azure-openai-key>"
$env:AZURE_Search_Service_KEY = "<your-azure-search-key>"
$env:DATA_MART_DB_USER = "<db-user>"; $env:DATA_MART_DB_PASSWORD = "<db-pass>"
$env:DYNATRACE_API = "Api-Token <token>"

# Run the app
python .\main.py
# App listens on http://127.0.0.1:7669/
```

UI pages:

- `http://127.0.0.1:7669/` → default chat using `/chat`
- `http://127.0.0.1:7669/uhccp` → UHCCP variant using `/chatbot`


## Docker

Multi-stage Dockerfile builds a virtual environment and runs via `gunicorn`:

- Base image: `centraluhg.jfrog.io/.../python:3.11-latest-dev`
- Exposes port `7669`
- Entrypoint: `python -m gunicorn -b 0.0.0.0:7669 main:app`

Build and run (PowerShell):

```powershell
docker build -t uhccp-internal-chatbot:local .
docker run --rm -p 7669:7669 --env AZURE_AI_Service_KEY --env AZURE_Search_Service_KEY \ 
	--env DATA_MART_DB_USER --env DATA_MART_DB_PASSWORD --env DYNATRACE_API \ 
	uhccp-internal-chatbot:local
```


## Kubernetes

Manifests are under `deployments/` and `manifests/`:

- `deployments/deployment.yaml`
	- Deployment `uhccp-internal-chatbot`
	- Injects secrets:
		- `azure-search-service-key.password` → `AZURE_Search_Service_KEY`
		- `azure-ai-service-key.password` → `AZURE_AI_Service_KEY`
	- Resource requests/limits set to 2000m CPU, 3072Mi memory
	- Probes configured (liveness: `ls`, readiness: TCP 8081)
	- Note: container `ports` lists `8081`, but app serves `7669`; ensure consistency between `containerPort`, `Service.targetPort`, and `Ingress`.

- `manifests/service.yaml`
	- ClusterIP service maps port `80` → `targetPort: 7669`

- `manifests/ingress.yaml`
	- Host: `hcccloud-uhgdlm-dtlapi-dev.uhc.com`
	- Path: `/uhccp-internal-chatbot(/|$)(.*)` with regex rewrite `/$2`
	- TLS enabled

- `manifests/networkpolicy.yaml`
	- Allows ingress/egress on common ports and `7669` for pods labeled `app: uhccp-internal-chatbot`


## Logging

- `chatbot_logger.py` sends packaged interaction data to `http://rn000125170:8080/generic_export`
- Fields include `_index_tag`, `_index_frequency`, `persona`, `environment`, `username`, `question`, `answer`, `ask_type`


## Dependencies

See `requirements.txt` for the full list. Key packages:

- Flask, Flask-Cors
- openai (AzureOpenAI), azure-ai-inference, azure-search-documents
- httpx, requests
- tiktoken
- psycopg2-binary
- Jinja2


## File Structure

```
chatbot_logger.py            # Logstash exporter for chatbot interactions
Dockerfile                   # Multi-stage build; gunicorn entrypoint
env_variables.py             # Environment toggles, endpoints, Azure keys
file_link.json               # Map of doc names → URLs for reference in answers
main.py                      # Flask app, routes, static serving
optum.pem, standard_trusts.pem   # TLS certs used for internal requests
optumcicd.yaml              # CI/CD metadata (disabled deploy)
personas.py                 # Persona tools and search client
pynote.py                   # Chat orchestration and RAG flow
README.md                   # This document
requirements.txt            # Python dependencies
system_messages.py          # System prompts for UHCCP persona
vector.py                   # Embeddings, search, and final chat responses
vitals.yaml                 # Accounts metadata

deployments/
	deployment.yaml           # Kubernetes Deployment (env, resources, probes)

manifests/
	ingress.yaml              # Ingress rule and TLS
	networkpolicy.yaml        # NetworkPolicy for the app
	service.yaml              # ClusterIP service

static/
	scripts.js                # Chat UI JS (calls /chat)
	uhccp_scripts.js          # Chat UI JS (calls /chatbot)
	styles.css                # Chat UI styles

templates/
	index.html                # Default UI page
	uhccp_index.html          # UHCCP variant UI page
	exit.html                 # Exit page

tools/
	__init__.py
	rally_funcs.py            # Rally endpoints and helpers
	tickets_funcs.py          # Inc/PRB/CHG, Splunk, Dynatrace, CRuX, performance
	tool_calls.py             # OpenAI tool call handling
	tools.py                  # Tool registry and schemas
	vbf_list.py               # Allowed VBF values
```


## Usage Notes and Contracts

- `/chat` returns a JSON string with keys `{response, questions?, persona, urlInfo?}`; newlines are converted to `<br>` in the string.
- `/chatbot` returns structured JSON `{response, context}`.
- Tool calls are decided by the LLM via `tool_calls.py`; results may be appended to the RAG `Data:` content.
- Rally IDs must preserve format: `F12345`, `US12345`, `DE12345`, `C12345`.


## Security and Compliance

- Do not commit secrets. Provide keys via environment variables or Kubernetes secrets.
- `httpx.Client(verify=False)` in `vector.py` is for testing; enable certificate verification in production.
- Certificates (`optum.pem`, `standard_trusts.pem`) should be managed securely.


## Known Issues / Gaps

- Frontend sanitization relies on `DOMPurify`, but it’s not imported by default in templates. Consider adding a CDN script tag:
	- `<script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.6/dist/purify.min.js"></script>`
- Mismatch between container `ports` (8081) and app port (7669); align deployment probes and `containerPort`.
- `/chat` returns a raw JSON string via `flask.Response`; consider `flask.jsonify` with `Content-Type: application/json`.
- `env.set_env(dev=False)` comment says “development mode” but `dev=False` sets Prod; update comment or logic for clarity.


## CI/CD

- `optumcicd.yaml` indicates `disableDeploy: true`; adjust for actual pipeline configuration.


## Try It (Examples)

### Call the chat API (PowerShell)

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:7669/uhccp-internal-chatbot/chatbot" -ContentType "application/json" -Body (@{ message = "What is UHCCP?"; context = "" } | ConvertTo-Json)
```

### Health check

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:7669/uhccp-internal-chatbot/health
```


## License

Internal use only. Property of Optum/UHG. Do not distribute.
