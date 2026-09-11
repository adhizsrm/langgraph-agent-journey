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
