"""Cross-format dataset parser tests."""

from __future__ import annotations

import io
import json

import pyarrow as pa
import pyarrow.parquet as parquet
import pytest
from eval_platform_application.dataset_import import ImportFormat, parse_records
from eval_platform_domain.errors import DomainError


def test_json_jsonl_csv_and_parquet_produce_equivalent_payloads() -> None:
    expected = [{"key": "1", "payload": {"input": "hello"}, "metadata": {}, "splits": []}]
    json_records = list(
        parse_records(
            io.BytesIO(json.dumps([{"id": "1", "input": "hello"}]).encode()),
            ImportFormat.JSON,
            max_records=10,
        )
    )
    jsonl_records = list(
        parse_records(
            io.BytesIO(b'{"id":"1","input":"hello"}\n'),
            ImportFormat.JSONL,
            max_records=10,
        )
    )
    csv_records = list(
        parse_records(
            io.BytesIO(b"id,input\r\n1,hello\r\n"),
            ImportFormat.CSV,
            max_records=10,
        )
    )
    parquet_bytes = io.BytesIO()
    parquet.write_table(pa.table({"id": ["1"], "input": ["hello"]}), parquet_bytes)
    parquet_bytes.seek(0)
    parquet_records = list(parse_records(parquet_bytes, ImportFormat.PARQUET, max_records=10))
    assert json_records == jsonl_records == csv_records == parquet_records == expected


def test_duplicate_json_keys_are_rejected() -> None:
    with pytest.raises(DomainError, match="duplicate"):
        list(
            parse_records(
                io.BytesIO(b'{"id":"1","id":"2"}\n'),
                ImportFormat.JSONL,
                max_records=10,
            )
        )


def test_record_limit_is_enforced_before_unbounded_growth() -> None:
    with pytest.raises(DomainError, match="record limit"):
        list(
            parse_records(
                io.BytesIO(b'{"id":"1"}\n{"id":"2"}\n'),
                ImportFormat.JSONL,
                max_records=1,
            )
        )
