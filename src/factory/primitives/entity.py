from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class FieldDef:
    """Declarative field definition for an entity."""

    name: str
    type: type
    required: bool = True
    default: Any = None
    nullable: bool = False
    unique: bool = False
    index: bool = False
    max_length: int | None = None
    min_length: int | None = None
    email: bool = False
    fk: str | None = None  # "entity_name.field" e.g. "brand.id"
    description: str = ""

    def __post_init__(self) -> None:
        if not re.match(r"^[a-z][a-z0-9_]*$", self.name):
            raise ValueError(
                f"Field name '{self.name}' must be snake_case (lowercase, starts with letter)"
            )
        if self.fk and not re.match(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$", self.fk):
            raise ValueError(
                f"FK reference '{self.fk}' must be 'entity_name.field' format"
            )
        if self.default is not None and self.required:
            object.__setattr__(self, "required", False)

    @property
    def is_enum(self) -> bool:
        return isinstance(self.type, type) and issubclass(self.type, StrEnum)

    @property
    def is_fk(self) -> bool:
        return self.fk is not None

    @property
    def is_jsonb(self) -> bool:
        return self.type in (dict, list)

    @property
    def python_type_str(self) -> str:
        type_map: dict[type, str] = {
            str: "str",
            int: "int",
            float: "float",
            bool: "bool",
            date: "date",
            datetime: "datetime",
            UUID: "UUID",
            dict: "dict",
            list: "list",
        }
        if self.is_enum:
            return self.type.__name__
        return type_map.get(self.type, "str")

    @property
    def sqlalchemy_type_str(self) -> str:
        from uuid import UUID as _UUID

        type_map: dict[type, str] = {
            str: f"String({self.max_length})" if self.max_length else "Text",
            int: "Integer",
            float: "Float",
            bool: "Boolean",
            date: "Date",
            datetime: "DateTime(timezone=True)",
            _UUID: "PG_UUID(as_uuid=True)",
            dict: "JSONB",
            list: "JSONB",
        }
        if self.is_enum:
            return "String(50)"
        return type_map.get(self.type, "Text")


def _pluralize(name: str) -> str:
    if name.endswith("s"):
        return f"{name}es"
    if name.endswith("y"):
        return f"{name[:-1]}ies"
    return f"{name}s"


@dataclass
class EntityDefinition:
    """Declarative entity definition -- generates models, schemas, tools, etc."""

    name: str
    fields: list[FieldDef]
    slug: str = ""  # Set by WorkflowDefinition
    expose_rest: bool = True
    enable_bulk: bool = False
    indexes: list[list[str]] = field(default_factory=list)
    unique_constraints: list[list[str]] = field(default_factory=list)
    description: str = ""

    def __post_init__(self) -> None:
        if not re.match(r"^[a-z][a-z0-9_]*$", self.name):
            raise ValueError(
                f"Entity name '{self.name}' must be snake_case"
            )
        field_names = [f.name for f in self.fields]
        duplicates = [n for n in field_names if field_names.count(n) > 1]
        if duplicates:
            raise ValueError(
                f"Duplicate field names in entity '{self.name}': {set(duplicates)}"
            )
        reserved = {"id", "created_at", "updated_at"}
        conflicts = reserved & set(field_names)
        if conflicts:
            raise ValueError(
                f"Fields {conflicts} are auto-generated — do not declare them in entity '{self.name}'"
            )
        for idx_fields in self.indexes:
            for idx_field in idx_fields:
                if idx_field not in field_names:
                    raise ValueError(
                        f"Index field '{idx_field}' not found in entity '{self.name}'"
                    )
        for uc_fields in self.unique_constraints:
            for uc_field in uc_fields:
                if uc_field not in field_names:
                    raise ValueError(
                        f"Unique constraint field '{uc_field}' not found in entity '{self.name}'"
                    )

    @property
    def class_name(self) -> str:
        return "".join(word.capitalize() for word in self.name.split("_"))

    @property
    def table_name(self) -> str:
        prefix = f"{self.slug}_" if self.slug else ""
        return f"{prefix}{_pluralize(self.name)}"

    @property
    def fk_fields(self) -> list[FieldDef]:
        return [f for f in self.fields if f.is_fk]

    @property
    def required_fields(self) -> list[FieldDef]:
        return [f for f in self.fields if f.required]

    @property
    def optional_fields(self) -> list[FieldDef]:
        return [f for f in self.fields if not f.required]

    @property
    def indexed_fields(self) -> list[FieldDef]:
        return [f for f in self.fields if f.index]

    @property
    def enum_types(self) -> list[type]:
        seen: set[str] = set()
        result: list[type] = []
        for f in self.fields:
            if f.is_enum and f.type.__name__ not in seen:
                seen.add(f.type.__name__)
                result.append(f.type)
        return result
