"""Schema-aware dataset canonicalization and content hashing."""

from __future__ import annotations

import hashlib
import math
import struct
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import jcs
from jsonschema import Draft202012Validator, FormatChecker

from eval_platform_domain.datasets import DatasetRecord, SourceProvenance
from eval_platform_domain.errors import DomainError, ErrorCode

CANONICALIZATION_VERSION = "dataset-c14n/1"
_MAX_SAFE_INTEGER = (1 << 53) - 1


def _text(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def _allows_null(schema: Mapping[str, Any]) -> bool:
    declared = schema.get("type")
    return declared == "null" or (
        isinstance(declared, Sequence) and not isinstance(declared, str) and "null" in declared
    )


def _normalize_timestamp(value: str) -> str:
    candidate = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as error:
        raise DomainError(ErrorCode.VALIDATION, "invalid RFC3339 date-time") from error
    if parsed.tzinfo is None:
        raise DomainError(ErrorCode.VALIDATION, "date-time requires an explicit offset")
    normalized = parsed.astimezone(UTC)
    fraction = f".{normalized.microsecond:06d}".rstrip("0") if normalized.microsecond else ""
    return normalized.strftime("%Y-%m-%dT%H:%M:%S") + fraction + "Z"


def normalize_json(value: Any, schema: Mapping[str, Any] | None = None) -> Any:
    """Normalize a JSON-compatible value according to the canonicalization contract."""

    active_schema = schema or {}
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = _text(value)
        if active_schema.get("format") == "date-time":
            return _normalize_timestamp(normalized)
        return normalized
    if isinstance(value, int):
        if abs(value) > _MAX_SAFE_INTEGER:
            raise DomainError(
                ErrorCode.VALIDATION,
                "integer is outside the interoperable JSON range",
            )
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DomainError(ErrorCode.VALIDATION, "JSON numbers must be finite")
        if value == 0:
            return 0
        return value
    if isinstance(value, Mapping):
        properties = active_schema.get("properties", {})
        if not isinstance(properties, Mapping):
            properties = {}
        normalized_items: dict[str, Any] = {}
        original_keys: dict[str, str] = {}
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise DomainError(ErrorCode.VALIDATION, "JSON object keys must be strings")
            key = _text(raw_key)
            if key in normalized_items:
                raise DomainError(
                    ErrorCode.VALIDATION,
                    "Unicode normalization created a duplicate object key",
                    details={"key": key, "first": original_keys[key], "second": raw_key},
                )
            child_schema = properties.get(key, {})
            normalized_items[key] = normalize_json(
                item,
                child_schema if isinstance(child_schema, Mapping) else {},
            )
            original_keys[key] = raw_key
        for raw_key, child_schema in properties.items():
            if (
                isinstance(raw_key, str)
                and raw_key not in normalized_items
                and isinstance(child_schema, Mapping)
            ):
                if _allows_null(child_schema):
                    normalized_items[raw_key] = None
                elif "default" in child_schema and child_schema.get("x-materialize-default", False):
                    normalized_items[raw_key] = normalize_json(
                        child_schema["default"],
                        child_schema,
                    )
        return normalized_items
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        item_schema = active_schema.get("items", {})
        if not isinstance(item_schema, Mapping):
            item_schema = {}
        return [normalize_json(item, item_schema) for item in value]
    raise DomainError(
        ErrorCode.VALIDATION,
        f"unsupported JSON value type: {type(value).__name__}",
    )


def canonical_bytes(value: Any, schema: Mapping[str, Any] | None = None) -> bytes:
    """Return version-1 canonical bytes after validation and normalization."""

    normalized = normalize_json(value, schema)
    if schema is not None:
        errors = sorted(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(normalized),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
        if errors:
            first = errors[0]
            pointer = "/" + "/".join(str(part) for part in first.absolute_path)
            raise DomainError(
                ErrorCode.VALIDATION,
                "record does not match its dataset schema",
                details={"pointer": pointer, "reason": first.message},
            )
    result = jcs.canonicalize(normalized)
    if not isinstance(result, bytes):
        raise RuntimeError("JCS implementation returned a non-byte result")
    return result


def content_hash(value: Any, schema: Mapping[str, Any] | None = None) -> str:
    """Hash canonical bytes with SHA-256."""

    return hashlib.sha256(canonical_bytes(value, schema)).hexdigest()


def _frame(parts: Sequence[bytes]) -> bytes:
    framed = bytearray()
    for part in parts:
        framed.extend(struct.pack(">Q", len(part)))
        framed.extend(part)
    return bytes(framed)


def build_record(
    *,
    key: str,
    payload: dict[str, Any],
    metadata: dict[str, Any] | None,
    splits: Sequence[str],
    source: SourceProvenance,
    schema: Mapping[str, Any],
) -> DatasetRecord:
    """Validate, normalize, and hash a source record."""

    normalized_key = _text(key).strip()
    if not normalized_key:
        raise DomainError(ErrorCode.VALIDATION, "record key must not be empty")
    normalized_payload = normalize_json(payload, schema)
    payload_bytes = canonical_bytes(normalized_payload, schema)
    payload_digest = hashlib.sha256(payload_bytes).hexdigest()
    normalized_metadata = normalize_json(metadata or {})
    normalized_splits = tuple(sorted({_text(split).strip().lower() for split in splits}))
    if any(not split for split in normalized_splits):
        raise DomainError(ErrorCode.VALIDATION, "split names must not be empty")
    source_value = {
        "kind": source.kind,
        "uri": source.uri,
        "row": source.row,
        "source_hash": source.source_hash,
    }
    envelope = _frame(
        [
            normalized_key.encode(),
            payload_digest.encode(),
            canonical_bytes(normalized_metadata),
            canonical_bytes(list(normalized_splits)),
            canonical_bytes(source_value),
        ]
    )
    return DatasetRecord(
        key=normalized_key,
        payload=normalized_payload,
        metadata=normalized_metadata,
        splits=normalized_splits,
        source=source,
        payload_hash=payload_digest,
        envelope_hash=hashlib.sha256(envelope).hexdigest(),
    )


def version_hash(
    *,
    schema: Mapping[str, Any],
    metadata: Mapping[str, Any],
    records: Sequence[DatasetRecord],
) -> str:
    """Hash a deterministic dataset manifest independent of import order."""

    ordered = sorted(records, key=lambda record: record.key.encode())
    parts = [
        CANONICALIZATION_VERSION.encode(),
        hashlib.sha256(canonical_bytes(schema)).digest(),
        hashlib.sha256(canonical_bytes(metadata)).digest(),
    ]
    parts.extend(bytes.fromhex(record.envelope_hash) for record in ordered)
    return hashlib.sha256(b"llm-eval-dataset\x00" + _frame(parts)).hexdigest()
