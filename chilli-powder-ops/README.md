# Chilli Powder Floor Operations

Runnable MVP for the exact architecture:

```text
Live Excel ↓ Ingestion ↓ Validation ↓ PostgreSQL ↓ Metrics ↓ Rules
↓ RCA Tools / Evidence ↓ Quality & Safety ↓ LLM ↔ RAG
↓ Dashboard + Conversation
```

## Run

1. Put the supplied workbook at `C:\Users\diks2\Downloads\Chilli_Powder_Floor_Data_Collection.xlsx` (the default path), or set `CHILLI_XLSX`.
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

The implementation deliberately keeps the supplied five-sheet floor model: `1_Output`, `2_Stops`, `3_Settings`, `4_Changes`, and `5_Response`, with `Plan` as the owner-controlled reference.



