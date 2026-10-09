# Chilli Powder Floor Operations

Runnable MVP for the exact architecture:

```text
Live Excel ↓ Ingestion ↓ Validation ↓ PostgreSQL ↓ Metrics ↓ Rules
↓ RCA Tools / Evidence ↓ Quality & Safety ↓ LLM ↔ RAG
↓ Dashboard + Conversation
```

## Run

1. The supplied workbook is packaged at `data/Chilli_Powder_Floor_Data_Collection.xlsx`, which is the default path and is included in the Docker image. To use another workbook, set `CHILLI_XLSX`.
2. Start PostgreSQL with `docker compose up -d db`.
3. Install dependencies: `python -m pip install -r requirements.txt`.
4. Start the app: `uvicorn app.main:app --reload`.
5. Open <http://127.0.0.1:8000>.

If `DATABASE_URL` is not available, the API still runs in demo mode using the workbook directly and clearly labels the data source. `Answer_Key` is never loaded.

## API

- `POST /api/ingest` - parse and validate the workbook
- `GET /api/summary` - stage metrics, quality/safety status, and latest RCA
- `GET /api/events?stage=Grinding` - normalized evidence rows
- `POST /api/conversation` - evidence-grounded floor question/answer
- `GET /api/health` - pipeline status
- `GET /api/workbook` - public download of the workbook currently used by the app

The implementation deliberately keeps the supplied five-sheet floor model: `1_Output`, `2_Stops`, `3_Settings`, `4_Changes`, and `5_Response`, with `Plan` as the owner-controlled reference.





The workbook is intentionally stored in the public repository under data/ and served by /api/workbook. Do not put secrets, credentials, or private operational data in this file.


## Comparison workflow

The workflow APIs support client input tiers (manual, erp, sensor), canonical production records, versioned targets with tolerances, idempotent incident creation, supervisor reasons, evidence-strength scoring, and an RC-01 through RC-13 registry awaiting definitions. The current public /api/summary dashboard remains compatible with the original floor workbook.

Workflow endpoints:

- PUT /api/workflow/capabilities/{client_id} - configure the client input tier
- POST /api/workflow/targets - define an owner-approved target and tolerance
- POST /api/workflow/import - import the packaged Excel baseline
- GET /api/workflow/incidents - list below-target incidents
- POST /api/workflow/incidents/{incident_id}/reason - submit a supervisor observation
- GET /api/workflow/incidents/{incident_id} - inspect evidence assessment
- GET /api/workflow/rca-registry - inspect unconfigured RC categories
