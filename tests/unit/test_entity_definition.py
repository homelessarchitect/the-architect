import pytest
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from factory.primitives import EntityDefinition, FieldDef


class LeadStatus(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    CONVERTED = "converted"


class TestFieldDef:
    def test_basic_string_field(self):
        f = FieldDef("name", str, required=True, max_length=255)
        assert f.name == "name"
        assert f.type is str
        assert f.required is True
        assert f.max_length == 255
        assert f.python_type_str == "str"
        assert f.sqlalchemy_type_str == "String(255)"

    def test_integer_field(self):
        f = FieldDef("score", int, default=0)
        assert f.required is False  # default implies not required
        assert f.default == 0
        assert f.python_type_str == "int"
        assert f.sqlalchemy_type_str == "Integer"

    def test_enum_field(self):
        f = FieldDef("status", LeadStatus, default=LeadStatus.NEW)
        assert f.is_enum is True
        assert f.python_type_str == "LeadStatus"
        assert f.sqlalchemy_type_str == "String(50)"

    def test_fk_field(self):
        f = FieldDef("brand_id", UUID, fk="brand.id")
        assert f.is_fk is True
        assert f.fk == "brand.id"

    def test_jsonb_dict_field(self):
        f = FieldDef("metadata", dict)
        assert f.is_jsonb is True
        assert f.sqlalchemy_type_str == "JSONB"

    def test_jsonb_list_field(self):
        f = FieldDef("tags", list)
        assert f.is_jsonb is True

    def test_email_field(self):
        f = FieldDef("email", str, email=True)
        assert f.email is True

    def test_nullable_field(self):
        f = FieldDef("notes", str, nullable=True, required=False)
        assert f.nullable is True
        assert f.required is False

    def test_invalid_name_uppercase(self):
        with pytest.raises(ValueError, match="snake_case"):
            FieldDef("FirstName", str)

    def test_invalid_name_starts_with_number(self):
        with pytest.raises(ValueError, match="snake_case"):
            FieldDef("1field", str)

    def test_invalid_fk_format(self):
        with pytest.raises(ValueError, match="entity_name.field"):
            FieldDef("ref", UUID, fk="invalid")

    def test_valid_fk_format(self):
        f = FieldDef("brand_id", UUID, fk="brand.id")
        assert f.fk == "brand.id"

    def test_datetime_field(self):
        f = FieldDef("published_at", datetime, nullable=True, required=False)
        assert f.python_type_str == "datetime"
        assert f.sqlalchemy_type_str == "DateTime(timezone=True)"

    def test_bool_field(self):
        f = FieldDef("is_active", bool, default=True)
        assert f.python_type_str == "bool"
        assert f.sqlalchemy_type_str == "Boolean"

    def test_text_field_no_max_length(self):
        f = FieldDef("description", str)
        assert f.sqlalchemy_type_str == "Text"

    def test_default_makes_not_required(self):
        f = FieldDef("count", int, required=True, default=0)
        assert f.required is False

    def test_date_field(self):
        from datetime import date

        f = FieldDef("publish_date", date, nullable=True, required=False)
        assert f.python_type_str == "date"
        assert f.sqlalchemy_type_str == "Date"


class TestEntityDefinition:
    def _lead_entity(self) -> EntityDefinition:
        return EntityDefinition(
            name="lead",
            fields=[
                FieldDef("name", str, required=True, max_length=255),
                FieldDef("email", str, email=True, nullable=True, required=False),
                FieldDef("lead_score", int, default=0),
                FieldDef("status", LeadStatus, default=LeadStatus.NEW),
                FieldDef("business_name", str, max_length=255, required=False),
                FieldDef("metadata", dict, required=False),
            ],
            indexes=[["email"]],
            unique_constraints=[["name", "business_name"]],
        )

    def test_basic_creation(self):
        entity = self._lead_entity()
        assert entity.name == "lead"
        assert len(entity.fields) == 6

    def test_class_name(self):
        entity = self._lead_entity()
        assert entity.class_name == "Lead"

    def test_class_name_multi_word(self):
        entity = EntityDefinition(
            name="content_piece",
            fields=[FieldDef("title", str)],
        )
        assert entity.class_name == "ContentPiece"

    def test_table_name_without_slug(self):
        entity = self._lead_entity()
        assert entity.table_name == "leads"

    def test_table_name_with_slug(self):
        entity = self._lead_entity()
        entity.slug = "asos"
        assert entity.table_name == "asos_leads"

    def test_table_name_pluralization_y(self):
        entity = EntityDefinition(
            name="category",
            fields=[FieldDef("name", str)],
        )
        assert entity.table_name == "categories"

    def test_table_name_pluralization_s(self):
        entity = EntityDefinition(
            name="status",
            fields=[FieldDef("name", str)],
        )
        assert entity.table_name == "statuses"

    def test_duplicate_fields_raises(self):
        with pytest.raises(ValueError, match="Duplicate field names"):
            EntityDefinition(
                name="bad",
                fields=[
                    FieldDef("name", str),
                    FieldDef("name", int),
                ],
            )

    def test_reserved_field_id_raises(self):
        with pytest.raises(ValueError, match="auto-generated"):
            EntityDefinition(
                name="bad",
                fields=[FieldDef("id", UUID)],
            )

    def test_reserved_field_created_at_raises(self):
        with pytest.raises(ValueError, match="auto-generated"):
            EntityDefinition(
                name="bad",
                fields=[FieldDef("created_at", datetime)],
            )

    def test_invalid_entity_name(self):
        with pytest.raises(ValueError, match="snake_case"):
            EntityDefinition(name="MyEntity", fields=[FieldDef("name", str)])

    def test_index_field_not_found(self):
        with pytest.raises(ValueError, match="Index field 'missing'"):
            EntityDefinition(
                name="test",
                fields=[FieldDef("name", str)],
                indexes=[["missing"]],
            )

    def test_unique_constraint_field_not_found(self):
        with pytest.raises(ValueError, match="Unique constraint field"):
            EntityDefinition(
                name="test",
                fields=[FieldDef("name", str)],
                unique_constraints=[["missing"]],
            )

    def test_fk_fields_property(self):
        entity = EntityDefinition(
            name="piece",
            fields=[
                FieldDef("title", str),
                FieldDef("brand_id", UUID, fk="brand.id"),
            ],
        )
        assert len(entity.fk_fields) == 1
        assert entity.fk_fields[0].name == "brand_id"

    def test_required_fields_property(self):
        entity = self._lead_entity()
        required = entity.required_fields
        assert all(f.required for f in required)

    def test_optional_fields_property(self):
        entity = self._lead_entity()
        optional = entity.optional_fields
        assert all(not f.required for f in optional)

    def test_enum_types_property(self):
        entity = self._lead_entity()
        assert LeadStatus in entity.enum_types

    def test_enum_types_no_duplicates(self):
        entity = EntityDefinition(
            name="test",
            fields=[
                FieldDef("status_a", LeadStatus, default=LeadStatus.NEW),
                FieldDef("status_b", LeadStatus, default=LeadStatus.NEW),
            ],
        )
        assert len(entity.enum_types) == 1

    def test_indexed_fields_property(self):
        entity = EntityDefinition(
            name="test",
            fields=[
                FieldDef("name", str, index=True),
                FieldDef("email", str),
            ],
        )
        assert len(entity.indexed_fields) == 1
        assert entity.indexed_fields[0].name == "name"

    def test_description(self):
        entity = EntityDefinition(
            name="lead",
            fields=[FieldDef("name", str)],
            description="A sales lead in the CRM pipeline",
        )
        assert entity.description == "A sales lead in the CRM pipeline"

    def test_expose_rest_default(self):
        entity = EntityDefinition(name="test", fields=[FieldDef("name", str)])
        assert entity.expose_rest is True

    def test_enable_bulk_default(self):
        entity = EntityDefinition(name="test", fields=[FieldDef("name", str)])
        assert entity.enable_bulk is False
