from fastapi.testclient import TestClient

import app.main as main


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
