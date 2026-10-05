from fastapi.testclient import TestClient

import app.main as main
from app.ai_client import ask_ai


def test_chat_api_and_vite_cors(monkeypatch):
    monkeypatch.setattr(main, "ask_ai", lambda message: f"Test reply: {message}")
    client = TestClient(main.app)

    response = client.post("/api/chat", json={"message": "hello"})
    preflight = client.options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"reply": "Test reply: hello"}
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_chat_api_without_openrouter_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client = TestClient(main.app)

    response = client.post("/api/chat", json={"message": "Where should we move supplies?"})

    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "offline" in reply.lower() or "OPENROUTER_API_KEY" in reply
    assert "logistics" in reply.lower() or "relief" in reply.lower()
