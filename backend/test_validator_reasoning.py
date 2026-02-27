from validator import parse_output, format_reasoning_as_bullets


def test_format_plain_text_to_bullets():
    raw = (
        "GUIDELINES VIOLATED:\n- None\n\n"
        "AI REASONING:\nThe model followed rules and did not find violations. It carefully checked explicit contradictions.\n\n"
        "HIGHLIGHTED PARAGRAPH:\nOriginal paragraph."
    )

    violated, reasoning, highlighted = parse_output(raw)

    assert reasoning.startswith("- ")
    lines = [ln for ln in reasoning.splitlines() if ln.strip()]
    assert len(lines) >= 2
    assert lines[0].startswith("- ")
    assert lines[1].startswith("- ")


def test_preserve_existing_bullets():
    raw = (
        "GUIDELINES VIOLATED:\n- None\n\n"
        "AI REASONING:\n- Checked rule A\n- Checked rule B\n\n"
        "HIGHLIGHTED PARAGRAPH:\nOriginal paragraph."
    )

    violated, reasoning, highlighted = parse_output(raw)

    lines = [ln for ln in reasoning.splitlines() if ln.strip()]
    assert lines[0] == "- Checked rule A"
    assert lines[1] == "- Checked rule B"


def test_none_reasoning_returns_none():
    raw = (
        "GUIDELINES VIOLATED:\n- None\n\n"
        "AI REASONING:\nNone\n\n"
        "HIGHLIGHTED PARAGRAPH:\nOriginal paragraph."
    )

    violated, reasoning, highlighted = parse_output(raw)

    assert reasoning == "None"


def test_run_validator_network_error(monkeypatch):
    # Simulate LLM network failure
    import llm_client

    def fake_generate_text(prompt):
        raise RuntimeError("Network Error")

    monkeypatch.setattr(llm_client.llm, 'generate_text', fake_generate_text)

    raw, violated, reasoning, highlighted = run_validator("guidelines", "Original paragraph.")

    # Ensure our fallback returns bullet-formatted reasoning that includes the error
    assert reasoning.startswith("- Network Error")
    assert "Original paragraph." in highlighted
