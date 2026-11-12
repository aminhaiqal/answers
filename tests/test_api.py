from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from axelyn.api.app import create_app
from axelyn.config import Settings
from axelyn.infrastructure.database import Base


def test_authenticated_document_and_question_flow(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    engine.dispose()
    settings = Settings(_env_file=None, database_url=url, api_key="x" * 32)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/ready").status_code == 200
        assert client.post("/v1/questions", json={"question": "leave"}).status_code == 401
        headers = {"Authorization": "Bearer " + "x" * 32}
        response = client.put(
            "/v1/documents/policy",
            headers=headers,
            json={"title": "HR", "text": "Annual leave is 20 days."},
        )
        assert response.status_code == 200
        result = client.post("/v1/questions", headers=headers, json={"question": "annual leave"})
        assert result.status_code == 200
        assert result.json()["result"]["sources"][0]["document_id"] == "policy"
        assert (
            client.post("/v1/questions", headers=headers, json={"question": "   "}).status_code
            == 422
        )
