"""Exercises the auth_headers_professor / auth_headers_student fixtures (AEGIS-68).

These fixtures back the endpoint tests, so this asserts they actually
authenticate with the right role: GET /exams is professor-only (200 for a
professor JWT, 403 for a student JWT).
"""

from httpx import AsyncClient


async def test_professor_header_allowed_on_professor_endpoint(
    client: AsyncClient, auth_headers_professor: dict[str, str]
) -> None:
    resp = await client.get("/exams", headers=auth_headers_professor)
    assert resp.status_code == 200


async def test_student_header_forbidden_on_professor_endpoint(
    client: AsyncClient, auth_headers_student: dict[str, str]
) -> None:
    resp = await client.get("/exams", headers=auth_headers_student)
    assert resp.status_code == 403
