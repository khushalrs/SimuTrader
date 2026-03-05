from __future__ import annotations

import re
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BinaryExpression, BindParameter, BooleanClauseList, UnaryExpression
from sqlalchemy.sql.functions import Function

from app.db import get_db
from app.models.assets import Asset

ASSETS_ROUTE_FILE = Path(__file__).resolve().parents[1] / "app" / "api" / "routes" / "assets.py"
_assets_spec = importlib.util.spec_from_file_location("isolated_assets_route", ASSETS_ROUTE_FILE)
if _assets_spec is None or _assets_spec.loader is None:
    raise RuntimeError(f"Failed to load assets route module from {ASSETS_ROUTE_FILE}")
_assets_module = importlib.util.module_from_spec(_assets_spec)
_assets_spec.loader.exec_module(_assets_module)
assets_router = _assets_module.router


def _asset(symbol: str, name: str, asset_class: str) -> SimpleNamespace:
    return SimpleNamespace(
        asset_id=uuid4(),
        symbol=symbol,
        name=name,
        asset_class=asset_class,
        currency="USD",
        exchange="NASDAQ",
        is_active=True,
        data_source="seed",
        meta={},
    )


def _like_matches(value: str | None, pattern: str, *, case_insensitive: bool) -> bool:
    if value is None:
        return False
    escaped = re.escape(pattern).replace("%", ".*").replace("_", ".")
    flags = re.IGNORECASE if case_insensitive else 0
    return re.fullmatch(escaped, value, flags=flags) is not None


def _resolve_operand(node, row):  # noqa: ANN001
    if isinstance(node, BindParameter):
        return node.value
    if isinstance(node, Function):
        if node.name.lower() == "lower":
            arg = next(iter(node.clauses))
            value = _resolve_operand(arg, row)
            return None if value is None else str(value).lower()
    if hasattr(node, "name") and hasattr(row, node.name):
        return getattr(row, node.name)
    if hasattr(node, "key") and hasattr(row, node.key):
        return getattr(row, node.key)
    if hasattr(node, "element"):
        return _resolve_operand(node.element, row)
    raise AssertionError(f"Unsupported operand: {node!r}")


def _eval_expr(expr, row) -> bool:  # noqa: ANN001
    if isinstance(expr, BooleanClauseList):
        if expr.operator == operators.or_:
            return any(_eval_expr(clause, row) for clause in expr.clauses)
        if expr.operator == operators.and_:
            return all(_eval_expr(clause, row) for clause in expr.clauses)
        raise AssertionError(f"Unsupported boolean operator: {expr.operator!r}")

    if isinstance(expr, BinaryExpression):
        left = _resolve_operand(expr.left, row)
        right = _resolve_operand(expr.right, row)
        if expr.operator == operators.eq:
            return left == right
        if expr.operator == operators.ilike_op:
            return _like_matches(left, right, case_insensitive=True)
        if expr.operator == operators.like_op:
            return _like_matches(left, right, case_insensitive=False)
        raise AssertionError(f"Unsupported binary operator: {expr.operator!r}")

    raise AssertionError(f"Unsupported expression: {expr!r}")


@dataclass
class _FakeQuery:
    rows: list[SimpleNamespace]
    limit_value: int | None = None

    def filter(self, *criteria):  # noqa: ANN002
        filtered = [
            row
            for row in self.rows
            if all(_eval_expr(criterion, row) for criterion in criteria)
        ]
        return _FakeQuery(rows=filtered, limit_value=self.limit_value)

    def order_by(self, *clauses):  # noqa: ANN002
        ordered = list(self.rows)
        for clause in clauses:
            descending = False
            current = clause
            if isinstance(clause, UnaryExpression):
                current = clause.element
                descending = clause.modifier == operators.desc_op
            key = getattr(current, "name", None) or getattr(current, "key", None)
            if key is None:
                raise AssertionError(f"Unsupported order clause: {clause!r}")
            ordered = sorted(ordered, key=lambda row: getattr(row, key), reverse=descending)
        return _FakeQuery(rows=ordered, limit_value=self.limit_value)

    def limit(self, value: int):
        return _FakeQuery(rows=list(self.rows), limit_value=value)

    def all(self):
        if self.limit_value is None:
            return list(self.rows)
        return list(self.rows[: self.limit_value])


class _FakeDB:
    def __init__(self, assets: list[SimpleNamespace]):
        self._assets = list(assets)

    def query(self, entity):
        if entity is not Asset:
            raise AssertionError(f"Unexpected query entity: {entity!r}")
        return _FakeQuery(rows=list(self._assets))


def _client_with_assets(assets: list[SimpleNamespace]) -> TestClient:
    test_app = FastAPI()
    test_app.include_router(assets_router)

    def _override_get_db():
        yield _FakeDB(assets)

    test_app.dependency_overrides[get_db] = _override_get_db
    return TestClient(test_app)


def test_assets_search_by_symbol():
    client = _client_with_assets(
        [
            _asset("AAPL", "Apple Inc", "US_EQUITY"),
            _asset("MSFT", "Microsoft Corporation", "US_EQUITY"),
        ]
    )
    res = client.get("/assets", params={"q": "AAPL"})
    assert res.status_code == 200
    payload = res.json()
    assert [row["symbol"] for row in payload] == ["AAPL"]


def test_assets_search_by_company_name():
    client = _client_with_assets(
        [
            _asset("AAPL", "Apple Inc", "US_EQUITY"),
            _asset("MSFT", "Microsoft Corporation", "US_EQUITY"),
        ]
    )
    res = client.get("/assets", params={"q": "microsoft"})
    assert res.status_code == 200
    payload = res.json()
    assert [row["symbol"] for row in payload] == ["MSFT"]


def test_assets_filter_by_asset_class_case_insensitive():
    client = _client_with_assets(
        [
            _asset("AAPL", "Apple Inc", "US_EQUITY"),
            _asset("MRPL", "MRPL Ltd", "IN_EQUITY"),
        ]
    )
    res = client.get("/assets", params={"asset_class": "us_equity"})
    assert res.status_code == 200
    payload = res.json()
    assert [row["symbol"] for row in payload] == ["AAPL"]


def test_assets_limit_is_enforced():
    client = _client_with_assets(
        [
            _asset("AAPL", "Apple Inc", "US_EQUITY"),
            _asset("AMZN", "Amazon.com", "US_EQUITY"),
            _asset("MSFT", "Microsoft Corporation", "US_EQUITY"),
        ]
    )
    ok_res = client.get("/assets", params={"limit": 1})
    assert ok_res.status_code == 200
    assert len(ok_res.json()) == 1

    invalid_res = client.get("/assets", params={"limit": 101})
    assert invalid_res.status_code == 422


def test_assets_no_match_returns_empty_list():
    client = _client_with_assets([_asset("AAPL", "Apple Inc", "US_EQUITY")])
    res = client.get("/assets", params={"q": "not-a-match"})
    assert res.status_code == 200
    assert res.json() == []


def test_assets_simple_fallback_prefix_tokens():
    client = _client_with_assets(
        [
            _asset("MSFT", "Microsoft Corporation", "US_EQUITY"),
            _asset("AAPL", "Apple Inc", "US_EQUITY"),
        ]
    )
    res = client.get("/assets", params={"q": "micro soft"})
    assert res.status_code == 200
    payload = res.json()
    assert [row["symbol"] for row in payload] == ["MSFT"]


def test_assets_no_params_preserves_legacy_behavior():
    client = _client_with_assets(
        [
            _asset("MSFT", "Microsoft Corporation", "US_EQUITY"),
            _asset("AAPL", "Apple Inc", "US_EQUITY"),
            _asset("MRPL", "MRPL Ltd", "IN_EQUITY"),
        ]
    )
    res = client.get("/assets")
    assert res.status_code == 200
    payload = res.json()
    assert [row["symbol"] for row in payload] == ["AAPL", "MRPL", "MSFT"]


def test_assets_openapi_includes_query_params():
    client = _client_with_assets([])
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    params = schema["paths"]["/assets"]["get"]["parameters"]
    names = {item["name"] for item in params}
    assert {"q", "asset_class", "limit"}.issubset(names)
