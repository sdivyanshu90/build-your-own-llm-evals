"""Bounded parsers for supported dataset import formats."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterator
from enum import StrEnum
from typing import Any, BinaryIO

import pyarrow.parquet as parquet
from eval_platform_domain.errors import DomainError, ErrorCode


class ImportFormat(StrEnum):
    """Supported dataset wire formats."""

    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    PARQUET = "parquet"


def _normalize_envelope(value: Any, row: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DomainError(
            ErrorCode.VALIDATION,
            "each imported record must be a JSON object",
            details={"row": row},
        )
    if "key" in value and "payload" in value:
        payload = value["payload"]
        if not isinstance(payload, dict):
            raise DomainError(
                ErrorCode.VALIDATION,
                "record payload must be an object",
                details={"row": row},
            )
        return {
            "key": str(value["key"]),
            "payload": payload,
            "metadata": value.get("metadata", {}),
            "splits": value.get("splits", []),
        }
    key = value.get("id", row)
    payload = {field: item for field, item in value.items() if field != "id"}
    return {"key": str(key), "payload": payload, "metadata": {}, "splits": []}


def parse_records(
    stream: BinaryIO,
    import_format: ImportFormat,
    *,
    max_records: int,
) -> Iterator[dict[str, Any]]:
    """Stream normalized record envelopes with a hard record limit."""

    if max_records < 1:
        raise ValueError("max_records must be positive")
    count = 0
    if import_format is ImportFormat.JSONL:
        text = io.TextIOWrapper(stream, encoding="utf-8-sig", newline=None)
        for row, line in enumerate(text, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line, object_pairs_hook=_reject_duplicate_keys)
            except json.JSONDecodeError as error:
                raise DomainError(
                    ErrorCode.VALIDATION,
                    "invalid JSONL record",
                    details={"row": row, "column": error.colno},
                ) from error
            count += 1
            _check_limit(count, max_records)
            yield _normalize_envelope(value, row)
        return
    if import_format is ImportFormat.CSV:
        text = io.TextIOWrapper(stream, encoding="utf-8-sig", newline="")
        reader = csv.DictReader(text)
        if not reader.fieldnames:
            raise DomainError(ErrorCode.VALIDATION, "CSV file has no header")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise DomainError(ErrorCode.VALIDATION, "CSV header contains duplicate names")
        for row, value in enumerate(reader, start=2):
            count += 1
            _check_limit(count, max_records)
            yield _normalize_envelope(value, row)
        return
    if import_format is ImportFormat.PARQUET:
        source = parquet.ParquetFile(stream)
        row = 0
        for batch in source.iter_batches(batch_size=2_048):
            for value in batch.to_pylist():
                row += 1
                count += 1
                _check_limit(count, max_records)
                yield _normalize_envelope(value, row)
        return
    try:
        value = json.load(
            io.TextIOWrapper(stream, encoding="utf-8-sig"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except json.JSONDecodeError as error:
        raise DomainError(
            ErrorCode.VALIDATION,
            "invalid JSON import",
            details={"line": error.lineno, "column": error.colno},
        ) from error
    values = value.get("records") if isinstance(value, dict) and "records" in value else value
    if not isinstance(values, list):
        raise DomainError(ErrorCode.VALIDATION, "JSON import must be an array of records")
    for row, item in enumerate(values, start=1):
        count += 1
        _check_limit(count, max_records)
        yield _normalize_envelope(item, row)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DomainError(
                ErrorCode.VALIDATION,
                "JSON object contains duplicate keys",
                details={"key": key},
            )
        result[key] = value
    return result


def _check_limit(count: int, maximum: int) -> None:
    if count > maximum:
        raise DomainError(
            ErrorCode.VALIDATION,
            "dataset import exceeds the configured record limit",
            details={"limit": maximum},
        )
