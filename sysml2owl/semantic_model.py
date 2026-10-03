"""Domain-neutral semantic intermediate representation for SysML2OWL."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PropertyDef:
    name: str
    type: str = ""
    kind: str = "attribute"          # attribute | ref | part | item | parameter
    lower: Optional[str] = None
    upper: Optional[str] = None
    default: Optional[str] = None
    direction: Optional[str] = None   # in | out | inout
    redefines: Optional[str] = None
    owner: Optional[str] = None


@dataclass
class TypeDef:
    name: str
    kind: str = "item"                # item | part | interface | port | datatype | enum
    parent: list[str] = field(default_factory=list)
    abstract: bool = False
    owner: Optional[str] = None
    attributes: list[PropertyDef] = field(default_factory=list)
    references: list[PropertyDef] = field(default_factory=list)
    usages: list[PropertyDef] = field(default_factory=list)
    documentation: Optional[str] = None


@dataclass
class InstanceDef:
    name: str
    type: list[str] = field(default_factory=list)
    kind: str = "part"                  # part | item | port
    owner: Optional[str] = None
    attributes: list[PropertyDef] = field(default_factory=list)
    references: list[PropertyDef] = field(default_factory=list)
    usages: list[PropertyDef] = field(default_factory=list)
    documentation: Optional[str] = None


@dataclass
class EndDef:
    name: str
    type: str = ""
    lower: Optional[str] = None
    upper: Optional[str] = None
    documentation: Optional[str] = None


@dataclass
class ConnectionDef:
    name: str
    parent: list[str] = field(default_factory=list)
    ends: list[EndDef] = field(default_factory=list)
    owner: Optional[str] = None
    documentation: Optional[str] = None


@dataclass
class ConnectionInstance:
    name: str
    type: str
    values: dict[str, str] = field(default_factory=dict)
    owner: Optional[str] = None


@dataclass
class ConstraintDef:
    expression: str
    name: Optional[str] = None
    owner: Optional[str] = None


@dataclass
class ActionDef:
    name: str
    parent: list[str] = field(default_factory=list)
    parameters: list[PropertyDef] = field(default_factory=list)
    attributes: list[PropertyDef] = field(default_factory=list)
    items: list[InstanceDef] = field(default_factory=list)
    constraints: list[ConstraintDef] = field(default_factory=list)
    owner: Optional[str] = None
    abstract: bool = False
    documentation: Optional[str] = None


@dataclass
class SemanticModel:
    package: str = "model"
    imports: list[str] = field(default_factory=list)
    types: list[TypeDef] = field(default_factory=list)
    instances: list[InstanceDef] = field(default_factory=list)
    connections: list[ConnectionDef] = field(default_factory=list)
    connection_instances: list[ConnectionInstance] = field(default_factory=list)
    actions: list[ActionDef] = field(default_factory=list)
    constraints: list[ConstraintDef] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)

    def all_named_elements(self):
        yield from self.types
        yield from self.instances
        yield from self.connections
        yield from self.connection_instances
        yield from self.actions
