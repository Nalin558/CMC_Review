import json
from app import app
import validator


def test_validate_endpoint_success(monkeypatch):
    # Patch the heavy LLM call inside run_validator for deterministic response
    def fake_run_validator(guidelines, paragraph):
        return (
            "GUIDELINES VIOLATED:\n- None\n\nAI REASONING:\n- No issues found\n\nHIGHLIGHTED PARAGRAPH:\nOriginal paragraph.",
            "- None",
            "- No issues found",
            "Original paragraph."
        )

    monkeypatch.setattr(validator, "run_validator", fake_run_validator)

    client = app.test_client()
    payload = {"guidelines": "Guideline A", "paragraph": "Some paragraph to check."}
    res = client.post('/validate', data=json.dumps(payload), content_type='application/json')

    assert res.status_code == 200
    data = res.get_json()
    assert "highlighted_html" in data
    assert "violated" in data
    assert "reasoning" in data


def test_validate_endpoint_missing_params():
    client = app.test_client()
    res = client.post('/validate', data=json.dumps({}), content_type='application/json')
    assert res.status_code == 400
    data = res.get_json()
    assert "error" in data
