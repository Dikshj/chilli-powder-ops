from app.pipeline import load_workbook, metrics, rca
from app.vector_store import EvidenceIndex, records_from_workbook

def test_retrieval_recall_for_planted_grinding_signal():
    data=load_workbook(); idx=EvidenceIndex(); idx.build(records_from_workbook(data))
    hits=idx.search('hammer sieve grinding',limit=5,filters={'stage':'Grinding'})
    assert hits and all(h['metadata']['stage']=='Grinding' for h in hits)

def test_rule_answer_has_high_confidence_for_planted_issue():
    data=load_workbook(); analysis=rca('Grinding',metrics(data)['Grinding'],data)
    assert analysis['quality_hold'] is True and analysis['confidence'] >= .9
