import json
from app import app


class FakeRet:
    def search(self, combined_text, k=5, category=None):
        # return list of tuples (score, text, meta)
        return [(0.9, "GUIDELINE A text", {}), (0.7, "GUIDELINE B text", {})]


def test_cmc_answer_section_includes_guideline_context(monkeypatch):
    # Patch ICHRetriever to avoid heavy index calls
    import app as appmod

    monkeypatch.setattr(appmod, 'ICHRetriever', lambda: FakeRet())

    # Also patch LLM call to deterministic response
    def fake_build_cmc_answer_json(comment, cmc_text, guideline_texts, category):
        return {"short_answer": "OK", "suggested_cmc_rewrite": "Rewritten paragraph."}

    monkeypatch.setattr(appmod, 'build_cmc_answer_json', fake_build_cmc_answer_json)

    client = app.test_client()
    payload = {"comment": "Test comment", "section_text": "Original section text", "category": "Q", "guideline_k": 2}
    res = client.post('/cmc/answer-section', data=json.dumps(payload), content_type='application/json')

    assert res.status_code == 200
    data = res.get_json()
    assert 'guideline_context' in data
    assert "GUIDELINE A text" in data['guideline_context']
    assert data['suggested_cmc_rewrite'] == "Rewritten paragraph."