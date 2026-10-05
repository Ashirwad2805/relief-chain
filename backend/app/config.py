import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Search in backend directory and project root directory
    env_paths = [
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path.cwd() / ".env"
    ]
    for p in env_paths:
        if p.exists():
            load_dotenv(dotenv_path=p, override=False)
            break
    else:
        load_dotenv()
except ImportError:
    pass

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./reliefchain.db")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    # Comma-separated list of allowed frontend origins (whitespace stripped)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    @classmethod
    def frontend_origins(cls) -> list[str]:
        origins = [o.strip() for o in cls.FRONTEND_URL.split(",") if o.strip()]
        for extra in (
            "http://localhost:5173",
            "http://localhost:8000",
            "https://relief-chain-delta.vercel.app",
        ):
            if extra not in origins:
                origins.append(extra)
        return origins


    JWT_SECRET: str = os.getenv("JWT_SECRET", "reliefchain-disaster-resilience-secret-seed-42")
    SIMULATION_SEED: int = int(os.getenv("SIMULATION_SEED", "42"))

    # Optional Integration API Keys
    MAPTILER_API_KEY: str | None = os.getenv("MAPTILER_API_KEY", None)
    MAPBOX_TOKEN: str | None = os.getenv("MAPBOX_TOKEN", None)
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY", None)
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY", None)
    GOOGLE_MAPS_API_KEY: str | None = os.getenv("GOOGLE_MAPS_API_KEY", None)
    PAYMENT_TEST_KEY: str | None = os.getenv("PAYMENT_TEST_KEY", None)
    BLOCKCHAIN_RPC_URL: str | None = os.getenv("BLOCKCHAIN_RPC_URL", None)
    BLOCKCHAIN_PRIVATE_KEY: str | None = os.getenv("BLOCKCHAIN_PRIVATE_KEY", None)

    @classmethod
    def get_integration_statuses(cls) -> list[dict]:
        return [
            {
                "id": "maptiler",
                "name": "MapTiler / Vector Tiles",
                "category": "Mapping",
                "status": "Connected" if cls.MAPTILER_API_KEY else "Mock mode",
                "configured": bool(cls.MAPTILER_API_KEY),
                "notes": "Bundled offline SVG / GeoJSON active" if not cls.MAPTILER_API_KEY else "Vector satellite overlay ready"
            },
            {
                "id": "mapbox",
                "name": "Mapbox Navigation SDK",
                "category": "Mapping",
                "status": "Connected" if cls.MAPBOX_TOKEN else "Mock mode",
                "configured": bool(cls.MAPBOX_TOKEN),
                "notes": "NetworkX Dijkstra local solver active" if not cls.MAPBOX_TOKEN else "Live traffic API enabled"
            },
            {
                "id": "google_maps",
                "name": "Google Maps Platform",
                "category": "Traffic & Routing",
                "status": "Connected" if cls.GOOGLE_MAPS_API_KEY else "Mock mode",
                "configured": bool(cls.GOOGLE_MAPS_API_KEY),
                "notes": "Local road graph fallback active"
            },
            {
                "id": "rbi_gateway",
                "name": "RBI Payment Gateway / Escrow",
                "category": "Financial",
                "status": "Connected" if cls.PAYMENT_TEST_KEY else "Mock mode",
                "configured": bool(cls.PAYMENT_TEST_KEY),
                "notes": "Simulated tamper-evident cryptographic escrow"
            },
            {
                "id": "blockchain",
                "name": "Public Chain Anchor (Ethereum/Polygon)",
                "category": "Ledger",
                "status": "Connected" if cls.BLOCKCHAIN_RPC_URL else "Mock mode",
                "configured": bool(cls.BLOCKCHAIN_RPC_URL),
                "notes": "SHA-256 internal tamper-evident hash chain active"
            },
            {
                "id": "ai_reasoning",
                "name": "LLM Explainer Engine",
                "category": "AI / ML",
                "status": "Connected" if (cls.OPENAI_API_KEY or cls.ANTHROPIC_API_KEY) else "Mock mode",
                "configured": bool(cls.OPENAI_API_KEY or cls.ANTHROPIC_API_KEY),
                "notes": "Deterministic mathematical explainability model active (zero hallucinations)"
            }
        ]

settings = Settings()
