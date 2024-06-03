from dataclasses import dataclass, make_dataclass, Field, fields, _MISSING_TYPE
from typing import List, Optional, Any, Iterable
import pydantic

def _get_pydantic_field_kwargs(dcls: type) -> dict[str, tuple[type, Any]]:
    # get attribute names and types from dataclass into pydantic format
    pydantic_field_kwargs = dict()
    for _field in fields(dcls):
        # check is field has default value
        if isinstance(_field.default, _MISSING_TYPE):
            # no default
            default = ...
        else:
            default = _field.default

        pydantic_field_kwargs[_field.name] = (_field.type, default)
    return pydantic_field_kwargs

def convert_flat_dataclass_to_pydantic(
    dcls: type, name: Optional[str] = None
) -> type[pydantic.BaseModel]:
    if name is None:
        name_ = f"Pydantic{dcls.__name__}"
    else:
        name_ = name
    return pydantic.create_model(  # type: ignore
        name_,
        **_get_pydantic_field_kwargs(dcls),
    )


def _get_dataclass_fields(
    pydantic_cls: type[pydantic.BaseModel],
) -> Iterable[str | tuple[str, type] | tuple[str, type, Field[Any]]]:
    # get attribute names and types from pydantic into dataclass format
    dataclass_fields = []
    for _field in pydantic_cls.__fields__.values():
        if _field.required:
            field_tuple = (_field.name, _field.type_)
        else:
            field_tuple = (  # type: ignore
                _field.name,
                _field.type_,
                _field.default,
            )

        dataclass_fields.append(field_tuple)
    return dataclass_fields

def convert_flat_pydantic_to_dataclass(
    pydantic_cls: type[pydantic.BaseModel],
    name: Optional[str] = None,
    slots: bool = True,
) -> type:
    if name is None:
        name_ = f"DataClass{pydantic_cls.__name__}"
    else:
        name_ = name
    return make_dataclass(
        name_,
        _get_dataclass_fields(pydantic_cls),
        slots=slots,
    )