"""OpenAPI contract schema verification for v1 endpoints."""

from jsonschema import Draft202012Validator, FormatChecker


def test_openapi_examples_and_responses(client):
    spec = client.get("/openapi.json").json()
    for operations in spec["paths"].values():
        for operation in operations.values():
            for response in operation["responses"].values():
                content = response.get("content", {}).get("application/json", {})
                if "example" in content:
                    schema = content["schema"] | {"components": spec["components"]}
                    Draft202012Validator(schema, format_checker=FormatChecker()).validate(
                        content["example"]
                    )
