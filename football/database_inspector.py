from __future__ import annotations

import re

from django.apps import apps
from django.db import connections


DEFAULT_TIMEOUT = 12
DEFAULT_MAX_TABLES = 6
DEFAULT_DUPLICATE_COLUMNS = ("title", "name", "slug")
FOCUS_MODEL_NAMES = (
    "SessionTask",
    "TrainingSession",
    "Team",
    "Player",
    "Match",
    "ConvocationRecord",
    "RivalAnalysisReport",
    "WorkspacePreference",
)


def _safe_table_name(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", text):
        return ""
    return text


def _split_candidates(raw) -> list[str]:
    out = []
    seen = set()
    for piece in re.split(r"[\n,;]+", str(raw or "")):
        value = _safe_table_name(piece)
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _focus_tables_from_page_context(page_context=None) -> list[str]:
    context = page_context if isinstance(page_context, dict) else {}
    candidates = []
    for key in ("db_table", "database_table", "table", "inspect_table", "focus_table"):
        candidates.extend(_split_candidates(context.get(key)))
    for key in ("db_tables", "database_tables", "tables", "inspect_tables", "focus_tables"):
        candidates.extend(_split_candidates(context.get(key)))
    for key in ("db_model", "database_model", "model", "inspect_model", "focus_model"):
        model_name = str(context.get(key) or "").strip()
        if not model_name:
            continue
        try:
            model = apps.get_model("football", model_name)
        except Exception:
            model = None
        if model and getattr(model._meta, "db_table", ""):
            candidates.append(str(model._meta.db_table))
    seen = set()
    out = []
    for value in candidates:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _football_model_tables() -> list[str]:
    tables = []
    seen = set()
    try:
        app_config = apps.get_app_config("football")
    except Exception:
        return tables
    for model_name in FOCUS_MODEL_NAMES:
        try:
            model = app_config.get_model(model_name)
        except Exception:
            model = None
        table = str(getattr(getattr(model, "_meta", None), "db_table", "") or "").strip() if model else ""
        if table and table not in seen:
            seen.add(table)
            tables.append(table)
    return tables


def _quote_table(connection, table_name: str) -> str:
    return connection.ops.quote_name(table_name)


def _table_columns(cursor, connection, table_name: str, *, limit: int = 8) -> list[str]:
    try:
        description = connection.introspection.get_table_description(cursor, table_name)
    except Exception:
        return []
    columns = []
    for column in description[:max(1, int(limit or 8))]:
        name = str(getattr(column, "name", "") or "")
        if name:
            columns.append(name)
    return columns


def _duplicate_summary(cursor, connection, table_name: str, columns: list[str], *, limit: int = 3) -> dict:
    duplicates = {}
    if not columns:
        return duplicates
    quoted_table = _quote_table(connection, table_name)
    for column in columns:
        if column not in DEFAULT_DUPLICATE_COLUMNS:
            continue
        quoted_column = _quote_table(connection, column)
        try:
            cursor.execute(
                f"""
                SELECT {quoted_column}, COUNT(*) AS c
                FROM {quoted_table}
                WHERE COALESCE({quoted_column}, '') <> ''
                GROUP BY {quoted_column}
                HAVING COUNT(*) > 1
                ORDER BY c DESC, {quoted_column} ASC
                LIMIT %s
                """,
                [max(1, int(limit or 3))],
            )
            rows = cursor.fetchall()
        except Exception:
            continue
        if rows:
            duplicates[column] = [
                {"value": str(row[0])[:180], "count": int(row[1] or 0)}
                for row in rows
                if row and row[0] not in (None, "")
            ]
    return duplicates


def inspect_database_readonly(*, page_context=None, max_tables: int = DEFAULT_MAX_TABLES, column_limit: int = 8, duplicate_limit: int = 3) -> dict:
    alias = "default"
    try:
        connection = connections[alias]
    except Exception as exc:
        return {"enabled": False, "reason": f"connection_error:{exc.__class__.__name__}", "alias": alias, "tables": []}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return {
            "enabled": False,
            "reason": f"db_unavailable:{exc.__class__.__name__}:{str(exc)[:120]}",
            "alias": alias,
            "tables": [],
        }

    try:
        available_tables = [str(name) for name in connection.introspection.table_names()]
    except Exception as exc:
        return {
            "enabled": False,
            "reason": f"introspection_error:{exc.__class__.__name__}:{str(exc)[:120]}",
            "alias": alias,
            "tables": [],
        }

    available_set = set(available_tables)
    focus_candidates = _focus_tables_from_page_context(page_context)
    model_tables = _football_model_tables()

    selected = []
    seen = set()
    for candidate in focus_candidates + model_tables + available_tables:
        name = _safe_table_name(candidate)
        if not name or name not in available_set or name in seen:
            continue
        seen.add(name)
        selected.append(name)
        if len(selected) >= max(1, int(max_tables or DEFAULT_MAX_TABLES)):
            break

    tables = []
    with connection.cursor() as cursor:
        for table_name in selected:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {_quote_table(connection, table_name)}")
                row_count = int((cursor.fetchone() or [0])[0] or 0)
            except Exception:
                row_count = 0
            columns = _table_columns(cursor, connection, table_name, limit=column_limit)
            duplicates = _duplicate_summary(cursor, connection, table_name, columns, limit=duplicate_limit)
            tables.append({
                "name": table_name,
                "row_count": row_count,
                "columns": columns,
                "duplicate_values": duplicates,
            })

    tables_sorted = sorted(tables, key=lambda row: (-int(row.get("row_count") or 0), str(row.get("name") or "")))
    return {
        "enabled": True,
        "reason": "connected",
        "alias": alias,
        "vendor": str(getattr(connection, "vendor", "") or ""),
        "table_count": len(available_tables),
        "selected_count": len(tables_sorted),
        "focus_tables": focus_candidates[:10],
        "tables": tables_sorted,
    }
