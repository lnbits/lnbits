import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, model_validator

from lnbits.exceptions import register_exception_handlers


class ValidationPayload(BaseModel):
    password: str = Field(min_length=8)

    @model_validator(mode="after")
    def reject_password(self):
        raise ValueError("Password rejected.")


@pytest.mark.parametrize("password", ["p4s$", "private-test-password"])
def test_validation_errors_are_json_serializable_and_omit_inputs(password, mocker):
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/api/v1/validation-test")
    def validate(payload: ValidationPayload):
        return payload

    log = mocker.patch("lnbits.exceptions.logger.error")
    with TestClient(app) as client:
        response = client.post("/api/v1/validation-test", json={"password": password})

    assert response.status_code == 400
    assert response.json()["detail"][0]["type"] in {"string_too_short", "value_error"}
    assert "input" not in response.json()["detail"][0]
    assert password not in response.text
    assert password not in str(log.call_args)
