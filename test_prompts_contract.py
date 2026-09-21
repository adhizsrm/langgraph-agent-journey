from app.prompts.frontend import frontend_prompt
from app.prompts.backend import backend_prompt


def test_frontend_prompt_includes_proxy_rules():
    prompt = frontend_prompt.template
    assert "port: 5173" in prompt, "Frontend prompt must enforce Vite port 5173"
    assert "proxy:" in prompt, "Frontend prompt must enforce Vite proxy"
    assert (
        "target: 'http://localhost:3000'" in prompt
    ), "Frontend prompt must target backend port 3000"
    assert "relative paths" in prompt, "Frontend prompt must enforce relative API calls"
    assert (
        "do NOT add a 'rewrite' property" in prompt
    ), "Frontend prompt must forbid rewrite functions"


def test_backend_prompt_includes_port_rules():
    prompt = backend_prompt.template
    assert (
        "process.env.PORT || 3000" in prompt
    ), "Backend prompt must default to port 3000"
    assert (
        "MUST default to port 3000" in prompt
    ), "Backend prompt must clearly specify port 3000 default"


def test_enhancement_prompt_includes_completeness_contract():
    from app.prompts.enhancement import enhancement_prompt

    prompt = enhancement_prompt.template

    assert (
        "ONLY the `changes` field is applied" in prompt
    ), "Prompt must enforce changes authority"
    assert (
        "Every required part of this chain must be represented" in prompt
    ), "Prompt must enforce end-to-end completeness"
    assert (
        "An enhancement is incomplete if any required implementation exists only in\nthe `analysis` field"
        in prompt
    ), "Prompt must forbid analysis-only implementations"
    assert (
        "`changes` MUST contain the required App.jsx and App.css actions" in prompt
    ), "Prompt must include dark mode completeness example"
    assert (
        "FINAL STRUCTURED OUTPUT CHECK:" in prompt
    ), "Prompt must include final self-check"
