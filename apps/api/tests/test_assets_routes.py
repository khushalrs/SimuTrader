from __future__ import annotations

import re
import importlib.util
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import duckdb
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


def _seed_asset_coverage(path: Path, symbol: str) -> None:
    con = duckdb.connect(str(path))
    con.execute(
        """
        CREATE TABLE prices (
            date DATE,
            symbol VARCHAR,
            asset_class VARCHAR,
            currency VARCHAR,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE,
            exchange VARCHAR,
            data_source VARCHAR
        );
        """
    )
    con.executemany(
        "INSERT INTO prices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (date(2024, 1, 2), symbol, "US_EQUITY", "USD", 100.0, 100.0, 100.0, 100.0, 1000.0, "NASDAQ", "seed"),
            (date(2024, 1, 5), symbol, "US_EQUITY", "USD", 103.0, 103.0, 103.0, 103.0, 1200.0, "NASDAQ", "seed"),
        ],
    )
    con.close()


def _like_matches(value: str | None, pattern: str, *, case_insensitive: bool) -> bool:
    if value is None:
        return False
    escaped = re.escape(pattern).replace("%", ".*").replace("_", ".")
    flags = re.IGNORECASE if case_insensitive else 0
    return re.fullmatch(escaped, value, flags=flags) is not None


def _resolve_operand(node, row):  # noqa: ANN001
    if isinstance(node, BindParameter):
        return node.value
    if str(node) == "true":
        return True
    if str(node) == "false":
        return False
    if isinstance(node, Function):
        if node.name.lower() == "lower":
            arg = next(iter(node.clauses))
            value = _resolve_operand(arg, row)
            return None if value is None else str(value).lower()
        if node.name.lower() == "upper":
            arg = next(iter(node.clauses))
            value = _resolve_operand(arg, row)
            return None if value is None else str(value).upper()
    if hasattr(node, "name") and hasattr(row, node.name):
        return getattr(row, node.name)
    if getattr(node, "key", None) is not None and hasattr(row, node.key):
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

    def first(self):
        rows = self.all()
        return rows[0] if rows else None


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


def test_assets_filters_currency_exchange_and_is_active():
    assets = [
        _asset("AAPL", "Apple Inc", "US_EQUITY"),
        _asset("MSFT", "Microsoft Corporation", "US_EQUITY"),
    ]
    assets[1].currency = "EUR"
    assets[1].exchange = "XETRA"
    assets[1].is_active = False
    client = _client_with_assets(assets)
    res = client.get(
        "/assets",
        params={"currency": "usd", "exchange": "nasdaq", "is_active": "true"},
    )
    assert res.status_code == 200
    payload = res.json()
    assert [row["symbol"] for row in payload] == ["AAPL"]


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


def test_assets_no_params_are_capped_by_default():
    client = _client_with_assets(
        [_asset(f"SYM{idx:02d}", f"Name {idx:02d}", "US_EQUITY") for idx in range(25)]
    )
    res = client.get("/assets")
    assert res.status_code == 200
    assert len(res.json()) == 20


def test_asset_detail_returns_coverage(tmp_path, monkeypatch):
    coverage_path = tmp_path / "assets_coverage.duckdb"
    _seed_asset_coverage(coverage_path, "AAPL")
    monkeypatch.setattr(_assets_module, "get_duckdb_conn", lambda: duckdb.connect(str(coverage_path)))

    client = _client_with_assets([_asset("AAPL", "Apple Inc", "US_EQUITY")])
    res = client.get("/assets/AAPL")
    assert res.status_code == 200
    payload = res.json()
    assert payload["symbol"] == "AAPL"
    assert payload["coverage"]["first_date"] == "2024-01-02"
    assert payload["coverage"]["last_date"] == "2024-01-05"
    assert payload["coverage"]["rows"] == 2


def test_assets_openapi_includes_query_params():
    client = _client_with_assets([])
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    list_params = schema["paths"]["/assets"]["get"]["parameters"]
    names = {item["name"] for item in list_params}
    assert {"q", "asset_class", "currency", "exchange", "is_active", "limit"}.issubset(names)
    assert schema["paths"]["/assets/{symbol}"]["get"]["parameters"][0]["name"] == "symbol"
