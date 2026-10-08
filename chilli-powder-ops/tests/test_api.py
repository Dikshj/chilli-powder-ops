import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def test_health_and_summary_have_schema():
    assert client.get('/api/health').status_code == 200
    body=client.get('/api/summary').json()
    assert set(body['stages']) == {'Cleaning','Grinding','Packing'}
    assert body['validation_errors'] == []

def test_conversation_returns_row_citations_and_filters():
    response=client.post('/api/conversation',json={'question':'What is the current risk?','stage':'Grinding','top_k':3})
    assert response.status_code == 200
    body=response.json()
    assert body['rag']['filters']['stage']=='Grinding'
    assert body['citations']
    assert all('sheet' in c and 'row' in c for c in body['citations'])

def test_invalid_numeric_and_stage_requests_are_rejected():
    assert client.post('/api/conversation',json={'question':'x','stage':'Unknown'}).status_code == 422
    assert client.post('/api/conversation',json={'question':'x'*2001,'stage':'Grinding'}).status_code == 422

def test_ingestion_reports_duplicate_fingerprint():
    first=client.post('/api/ingest').json()['ingestion']
    second=client.post('/api/ingest').json()['ingestion']
    assert first['fingerprint'] == second['fingerprint']
    assert second['duplicate'] is True

@pytest.mark.skipif(not os.getenv('DATABASE_URL'), reason='requires PostgreSQL/Docker')
def test_postgres_end_to_end_ingestion():
    body=client.post('/api/ingest').json()
    assert body['ingestion']['storage']=='postgresql'
