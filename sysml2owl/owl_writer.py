"""OWL 2 writer for the SysML semantic intermediate representation."""

from pathlib import Path
import re

from rdflib import (
    Graph,
    Namespace,
    RDF,
    RDFS,
    OWL,
    XSD,
    Literal,
    URIRef,
    BNode,
)

from .semantic_model import *


class OWLWriter:

    def __init__(self, base_iri="https://coresense.eu/sysml2owl#"):

        if not base_iri.endswith(("#", "/")):
            base_iri += "#"

        self.base = Namespace(base_iri)

        # Indexes over the semantic model.
        #
        # They are useful when resolving concrete instances and their
        # nested usages while generating OWL assertions.
        self._instance_index = {}
        self._type_index = {}
        self._redefined_properties = set()


    # ======================================================================
    # Main writer
    # ======================================================================

    def write(self, model: SemanticModel, output: str):

        g = Graph()

        # Collect canonical property names for SysML redefinitions (:>>).
        self._redefined_properties.clear()
        for t in model.types:
            for p in list(t.attributes) + list(t.references) + list(t.usages):
                if p.redefines:
                    self._redefined_properties.add(self._local(p.redefines))
        for i in model.instances:
            for p in list(i.attributes) + list(i.references) + list(i.usages):
                if p.redefines:
                    self._redefined_properties.add(self._local(p.redefines))

        # The generated model namespace is the user-supplied base IRI.
        # No sysml2owl-specific vocabulary is emitted by default.

        g.bind("sysml", self.base)
        g.bind("owl", OWL)
        g.bind("rdfs", RDFS)
        g.bind("xsd", XSD)

        ont = self.base.ontology

        g.add((ont, RDF.type, OWL.Ontology))

        g.add(
            (
                ont,
                RDFS.label,
                Literal(
                    f"OWL representation of SysML package "
                    f"{model.package}"
                ),
            )
        )

        for imp in model.imports:
            g.add(
                (
                    ont,
                    RDFS.comment,
                    Literal(f"SysML import: {imp}"),
                )
            )

        for source in model.source_files:
            g.add(
                (
                    ont,
                    RDFS.comment,
                    Literal(f"SysML source: {source}"),
                )
            )

        # ------------------------------------------------------------------
        # Types
        # ------------------------------------------------------------------

        for t in model.types:
            self._type(g, t)
            self._type_index[self._local(t.name)] = t

        # ------------------------------------------------------------------
        # Connections
        # ------------------------------------------------------------------

        for c in model.connections:
            self._connection(g, c)

        # ------------------------------------------------------------------
        # Actions
        # ------------------------------------------------------------------

        for a in model.actions:
            self._action(g, a)

        # ------------------------------------------------------------------
        # Register all instances before resolving nested usages.
        # ------------------------------------------------------------------

        for i in model.instances:
            self._register_instance(i)

        # ------------------------------------------------------------------
        # Instances
        # ------------------------------------------------------------------

        for i in model.instances:
            self._instance(g, i)

        # ------------------------------------------------------------------
        # Connection instances
        # ------------------------------------------------------------------

        for ci in model.connection_instances:
            self._connection_instance(g, ci)

        # ------------------------------------------------------------------
        # Constraints
        # ------------------------------------------------------------------

        for c in model.constraints:
            self._constraint(g, c)

        Path(output).parent.mkdir(parents=True, exist_ok=True)

        g.serialize(
            destination=output,
            format="turtle",
        )

        return len(g)


    # ======================================================================
    # IRI helpers
    # ======================================================================

    def _iri(self, name, owner=None):

        if "::" in name:
            return self.base[
                self._safe(
                    name.replace("::", "__")
                )
            ]

        if owner:
            return self.base[
                self._safe(
                    owner.replace("::", "__")
                    + "__"
                    + name
                )
            ]

        return self.base[self._safe(name)]


    @staticmethod
    def _safe(s):
        return re.sub(
            r"[^A-Za-z0-9_.-]",
            "_",
            s,
        )


    @staticmethod
    def _local(name):
        return name.split("::")[-1].split(".")[-1]


    # ======================================================================
    # Model indexes
    # ======================================================================

    def _register_instance(self, i):

        key = (
            i.name
            if not i.owner
            else f"{i.owner}.{i.name}"
        )

        self._instance_index[key] = i


    # ======================================================================
    # Types
    # ======================================================================

    def _type(self, g, t):

        x = self._iri(
            t.name,
            t.owner,
        )

        g.add(
            (
                x,
                RDF.type,
                OWL.Class,
            )
        )

        g.add(
            (
                x,
                RDFS.label,
                Literal(t.name),
            )
        )

        if t.abstract:
            g.add(
                (
                    x,
                    self.base.abstract,
                    Literal(
                        True,
                        datatype=XSD.boolean,
                    ),
                )
            )

        for parent in t.parent:
            g.add(
                (
                    x,
                    RDFS.subClassOf,
                    self._iri(parent),
                )
            )

        for p in t.attributes:
            self._datatype_property(
                g,
                x,
                p,
            )

        for p in t.references:
            self._object_property(
                g,
                x,
                p,
            )

        for p in t.usages:
            self._object_property(
                g,
                x,
                p,
            )

        if t.documentation:
            g.add(
                (
                    x,
                    RDFS.comment,
                    Literal(t.documentation),
                )
            )


    # ======================================================================
    # Properties
    # ======================================================================

    def _datatype_property(self, g, owner, p):

        if self._local(p.name) in self._redefined_properties:
            prop = self._iri(self._local(p.name))
        else:
            prop = self._iri(
                p.name,
                self._owner_name(owner),
            )

        g.add(
            (
                prop,
                RDF.type,
                OWL.DatatypeProperty,
            )
        )

        g.add(
            (
                prop,
                RDFS.domain,
                owner,
            )
        )

        g.add(
            (
                prop,
                RDFS.range,
                self._datatype(p.type),
            )
        )

        self._property_metadata(
            g,
            prop,
            p,
        )


    def _object_property(self, g, owner, p):

        prop = self._iri(
            p.name,
            self._owner_name(owner),
        )

        g.add(
            (
                prop,
                RDF.type,
                OWL.ObjectProperty,
            )
        )

        g.add(
            (
                prop,
                RDFS.domain,
                owner,
            )
        )

        typ = self._split_type(p.type)

        if typ:
            g.add(
                (
                    prop,
                    RDFS.range,
                    self._iri(typ),
                )
            )

        self._property_metadata(
            g,
            prop,
            p,
        )

        self._cardinality(
            g,
            owner,
            prop,
            p.lower,
            p.upper,
        )


    def _property_metadata(self, g, prop, p):

        if p.direction:
            g.add(
                (
                    prop,
                    RDFS.comment,
                    Literal(
                        f"SysML direction: {p.direction}"
                    ),
                )
            )

        if p.redefines:
            g.add(
                (
                    prop,
                    RDFS.subPropertyOf,
                    self._iri(p.redefines),
                )
            )

        if p.default is not None:
            g.add(
                (
                    prop,
                    RDFS.comment,
                    Literal(
                        f"SysML default: {p.default}"
                    ),
                )
            )


    # ======================================================================
    # Connections
    # ======================================================================

    def _connection(self, g, c):

        prop = self._iri(c.name)

        g.add(
            (
                prop,
                RDF.type,
                OWL.ObjectProperty,
            )
        )

        g.add(
            (
                prop,
                RDFS.label,
                Literal(c.name),
            )
        )

        for parent in c.parent:
            g.add(
                (
                    prop,
                    RDFS.subPropertyOf,
                    self._iri(parent),
                )
            )

        if c.ends:
            g.add(
                (
                    prop,
                    RDFS.domain,
                    self._iri(c.ends[0].type),
                )
            )

        if len(c.ends) >= 2:
            g.add(
                (
                    prop,
                    RDFS.range,
                    self._iri(c.ends[1].type),
                )
            )

        for end in c.ends:

            ep = self._iri(
                f"{c.name}__{end.name}"
            )

            g.add(
                (
                    ep,
                    RDF.type,
                    OWL.ObjectProperty,
                )
            )

            g.add(
                (
                    ep,
                    RDFS.subPropertyOf,
                    prop,
                )
            )

            g.add(
                (
                    ep,
                    RDFS.range,
                    self._iri(end.type),
                )
            )

            self._cardinality(
                g,
                prop,
                ep,
                end.lower,
                end.upper,
            )


    # ======================================================================
    # Instances
    # ======================================================================

    def _instance(self, g, i):

        x = self._iri(
            i.name,
            i.owner,
        )

        g.add(
            (
                x,
                RDFS.label,
                Literal(i.name),
            )
        )

        for typ in i.type:
            g.add(
                (
                    x,
                    RDF.type,
                    self._iri(typ),
                )
            )

        for p in i.attributes:
            self._instance_attribute(
                g,
                x,
                i,
                p,
            )

        for p in i.references:
            self._instance_reference(
                g,
                x,
                i,
                p,
            )

        # Nested part usages represent structural containment.
        #
        # Example:
        #
        #   part kitchen : Kitchen {
        #       part fridge : Fridge;
        #       part oven : Oven;
        #   }
        #
        # becomes:
        #
        #   kitchen Contains kitchen__fridge
        #   kitchen Contains kitchen__oven
        #
        # The generated Contains assertions represent the expected
        # structural containment of the concrete MIRTE house.

        for p in i.usages:
            self._instance_usage(
                g,
                x,
                i,
                p,
            )


    def _instance_usage(
        self,
        g,
        subject,
        instance,
        usage,
    ):

        if not usage.name:
            return

        # The semantic model represents a nested usage as part of its
        # containing instance. The OWL instance naming convention already
        # used by this writer is:
        #
        #   kitchen__fridge
        #
        # for:
        #
        #   part kitchen {
        #       part fridge;
        #   }
        #
        # Therefore derive the concrete target from the local subject
        # name rather than introducing another vocabulary.

        subject_local = str(subject).rsplit("#", 1)[-1]

        target_name = (
            f"{subject_local}__{usage.name}"
        )

        target = self._iri(target_name)

        contains = self._iri("Contains")

        g.add(
            (
                subject,
                contains,
                target,
            )
        )


    def _instance_attribute(
        self,
        g,
        subject,
        instance,
        p,
    ):

        owner = (
            instance.name
            if not instance.owner
            else f"{instance.owner}.{instance.name}"
        )

        if self._local(p.name) in self._redefined_properties:
            prop = self._iri(self._local(p.name))
        else:
            prop = self._iri(
                p.name,
                owner,
            )

        g.add(
            (
                prop,
                RDF.type,
                OWL.DatatypeProperty,
            )
        )

        if instance.type:
            g.add(
                (
                    prop,
                    RDFS.domain,
                    self._iri(instance.type[0]),
                )
            )

        g.add(
            (
                prop,
                RDFS.range,
                self._datatype(p.type),
            )
        )

        if p.default is not None:

            for value in self._tuple_values(
                p.default
            ):

                g.add(
                    (
                        subject,
                        prop,
                        Literal(value, datatype=self._datatype(p.type)),
                    )
                )


    def _instance_reference(
        self,
        g,
        subject,
        instance,
        p,
    ):

        owner = (
            instance.name
            if not instance.owner
            else f"{instance.owner}.{instance.name}"
        )

        prop = self._iri(
            p.name,
            owner,
        )

        g.add(
            (
                prop,
                RDF.type,
                OWL.ObjectProperty,
            )
        )

        if instance.type:
            g.add(
                (
                    prop,
                    RDFS.domain,
                    self._iri(instance.type[0]),
                )
            )

        if p.type:
            g.add(
                (
                    prop,
                    RDFS.range,
                    self._iri(
                        self._split_type(p.type)
                    ),
                )
            )

        self._cardinality(
            g,
            (
                self._iri(instance.type[0])
                if instance.type
                else subject
            ),
            prop,
            p.lower,
            p.upper,
        )

        if p.default:

            for value in self._tuple_values(
                p.default
            ):

                if self._looks_identifier(value):

                    g.add(
                        (
                            subject,
                            prop,
                            self._iri(value),
                        )
                    )

                else:

                    g.add(
                        (
                            subject,
                            prop,
                            Literal(value),
                        )
                    )


    # ======================================================================
    # Connection instances
    # ======================================================================

    def _connection_instance(self, g, c):

        x = self._iri(c.name)

        g.add(
            (
                x,
                RDF.type,
                self._iri(c.type),
            )
        )

        for k, v in c.values.items():

            prop = self._iri(
                f"{c.type}__{k}"
            )

            for value in self._tuple_values(v):

                target = (
                    self._iri(value)
                    if self._looks_identifier(value)
                    else Literal(value)
                )

                g.add(
                    (
                        x,
                        prop,
                        target,
                    )
                )


    # ======================================================================
    # Actions
    # ======================================================================

    def _action(self, g, a):

        x = self._iri(
            a.name,
            a.owner,
        )

        g.add(
            (
                x,
                RDF.type,
                OWL.Class,
            )
        )

        g.add(
            (
                x,
                RDFS.subClassOf,
                self.base.Action,
            )
        )

        if a.abstract:
            g.add(
                (
                    x,
                    self.base.abstract,
                    Literal(
                        True,
                        datatype=XSD.boolean,
                    ),
                )
            )

        for parent in a.parent:
            g.add(
                (
                    x,
                    RDFS.subClassOf,
                    self._iri(parent),
                )
            )

        for p in a.parameters:

            prop = self._iri(
                p.name,
                a.name + "__parameter",
            )

            g.add(
                (
                    prop,
                    RDF.type,
                    OWL.ObjectProperty,
                )
            )

            g.add(
                (
                    prop,
                    RDFS.domain,
                    x,
                )
            )

            if p.type:
                g.add(
                    (
                        prop,
                        RDFS.range,
                        self._iri(
                            self._split_type(p.type)
                        ),
                    )
                )

            self._cardinality(
                g,
                x,
                prop,
                p.lower,
                p.upper,
            )

        for p in a.attributes:
            self._datatype_property(
                g,
                x,
                p,
            )

        for item in a.items:

            ix = self._iri(
                item.name,
                a.name,
            )

            g.add(
                (
                    ix,
                    RDF.type,
                    self._iri(item.type[0]),
                )
            )


    # ======================================================================
    # Constraints
    # ======================================================================

    def _constraint(self, g, c):
        token = abs(hash((c.name, c.expression)))
        x = self._iri(f"constraint_{token}")

        target = self._iri(c.owner) if c.owner else self.base.ontology
        label = c.name or "constraint"

        g.add((
            target,
            RDFS.comment,
            Literal(f"SysML constraint {label}: {c.expression}")
        ))

        if label == "classification" and c.owner:
            self._classification_constraint(g, c.owner, c.expression)


    def _classification_constraint(self, g, room_class, expression):
        """
        Translate a SysML classification constraint of the form:

            objectsContained->...exists {
                in o : PhysicalObject;
                o istype Fridge
            }

        into OWL existential restrictions:

            room_class rdfs:subClassOf [
                a owl:Restriction ;
                owl:onProperty sysml:Contains ;
                owl:someValuesFrom sysml:Fridge
            ] .
        """

        # Each `o istype X` means:
        # the room must contain at least one object of type X.
        object_types = re.findall(
            r"\bo\s+istype\s+([A-Za-z_][A-Za-z0-9_]*)",
            expression
        )

        for object_type in object_types:
            restriction = BNode()

            g.add((restriction, RDF.type, OWL.Restriction))
            g.add((restriction, OWL.onProperty, self.base.Contains))
            g.add((
                restriction,
                OWL.someValuesFrom,
                self._iri(object_type)
            ))
            g.add((
                self._iri(room_class),
                RDFS.subClassOf,
                restriction
            ))

    # ======================================================================
    # Cardinalities
    # ======================================================================

    def _cardinality(
        self,
        g,
        owner,
        prop,
        lower,
        upper,
    ):

        if not lower and not upper:
            return

        b = BNode()

        g.add(
            (
                b,
                RDF.type,
                OWL.Restriction,
            )
        )

        g.add(
            (
                b,
                OWL.onProperty,
                prop,
            )
        )

        g.add(
            (
                owner,
                RDFS.subClassOf,
                b,
            )
        )

        if lower and lower.isdigit():

            g.add(
                (
                    b,
                    OWL.minCardinality,
                    Literal(
                        int(lower),
                        datatype=XSD.nonNegativeInteger,
                    ),
                )
            )

        if upper and upper.isdigit():

            g.add(
                (
                    b,
                    OWL.maxCardinality,
                    Literal(
                        int(upper),
                        datatype=XSD.nonNegativeInteger,
                    ),
                )
            )


    # ======================================================================
    # Type helpers
    # ======================================================================

    @staticmethod
    def _split_type(t):

        if not t:
            return ""

        return t.split(",")[0].strip()


    @staticmethod
    def _datatype(t):

        return {
            "Boolean": XSD.boolean,
            "Real": XSD.double,
            "Integer": XSD.integer,
            "String": XSD.string,
        }.get(
            t.split("::")[-1].strip(),
            XSD.string,
        )


    @staticmethod
    def _looks_identifier(v):

        return bool(
            re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_.]*"
                r"(?:::[A-Za-z_][A-Za-z0-9_]*)*",
                v,
            )
        )


    @staticmethod
    def _tuple_values(v):

        v = v.strip()

        if v.startswith("(") and v.endswith(")"):

            return [
                x.strip().strip('"')
                for x in v[1:-1].split(",")
                if x.strip()
            ]

        return [
            v.strip().strip('"')
        ]


    @staticmethod
    def _owner_name(owner):

        if isinstance(owner, URIRef):
            return str(owner).rsplit("#", 1)[-1]

        return str(owner)