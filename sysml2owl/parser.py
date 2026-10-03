"""A domain-neutral, pragmatic SysML v2 parser.

It intentionally targets the structural subset needed by the CoreSense models while
keeping the parser independent from OWL and from any particular application domain.
"""
import re
from pathlib import Path
from .semantic_model import *

_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
_QNAME = rf"{_IDENT}(?:::{_IDENT})*"


class SysMLParser:
    def parse_file(self, filename: str, model: SemanticModel | None = None) -> SemanticModel:
        model = model or SemanticModel()
        text = Path(filename).read_text(encoding="utf-8")
        model.source_files.append(str(filename))
        self.parse_text(text, model)
        return model

    def parse_directory(self, directory: str, pattern="*.sysml") -> SemanticModel:
        model = SemanticModel()
        files = sorted(Path(directory).glob(pattern))
        if not files:
            raise FileNotFoundError(f"No SysML files matching {pattern} in {directory}")
        for f in files:
            self.parse_file(str(f), model)
        return model

    def parse_text(self, text: str, model: SemanticModel):
        text = self._strip_comments(text)
        package = re.search(rf"\bpackage\s+({_IDENT})\s*\{{", text)
        if package and model.package == "model":
            model.package = package.group(1)

        model.imports.extend(re.findall(rf"\b(?:private\s+)?import\s+({_QNAME}(?:::\*)?)\s*;", text))
        self._parse_type_defs(text, model)
        self._parse_action_defs(text, model)
        self._parse_connections(text, model)
        self._parse_instances(text, model)
        self._parse_connection_instances(text, model)
        self._parse_constraints(text, model)

    @staticmethod
    def _strip_comments(text):
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r"//[^\n]*", "", text)
        return text

    @staticmethod
    def _block(text, brace):
        depth = 0
        quote = None
        escape = False
        for i in range(brace, len(text)):
            c = text[i]
            if quote:
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == quote:
                    quote = None
                continue
            if c in ('"', "'"):
                quote = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[brace + 1:i]
        raise ValueError("Unbalanced SysML block")

    @staticmethod
    def _split_types(value: str) -> list[str]:
        return [x.strip() for x in value.split(",") if x.strip()]

    @staticmethod
    def _mult(mult):
        if not mult:
            return None, None
        mult = mult.strip()
        if mult == "*":
            return "0", "*"
        if ".." in mult:
            a, b = mult.split("..", 1)
            return a.strip(), b.strip()
        return mult, mult

    @staticmethod
    def _direct_members_text(body: str) -> str:
        """Return only text belonging to the current block level.

        Nested SysML blocks are parsed separately by the recursive instance/type
        parsers. Keeping their contents out of _members() prevents declarations
        such as `attribute :>> navigationX` inside `part kitchen { ... }` from
        being incorrectly attributed to the enclosing `MIRTEHouse` definition.
        """
        out = list(body)
        depth = 0
        quote = None
        escape = False

        for i, c in enumerate(body):
            if quote:
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == quote:
                    quote = None
                if depth > 0:
                    out[i] = " "
                continue

            if c in ("\"", "'"):
                quote = c
                if depth > 0:
                    out[i] = " "
                continue

            if c == "{":
                depth += 1
                out[i] = " "
                continue

            if c == "}":
                if depth > 0:
                    depth -= 1
                out[i] = " "
                continue

            if depth > 0:
                out[i] = " "

        return "".join(out)

    def _members(self, body: str, owner: str | None = None):
        attrs, refs, usages = [], [], []
        direct_body = self._direct_members_text(body)

        # Attributes: ordinary declarations and redefinitions such as
        # `attribute :>> name = "foo";` or `attribute :>> name : Real = 1.0 { ... }`.
        attr_re = re.compile(
            rf"\battribute\s+(?P<red>:>>\s*)?(?P<name>{_IDENT})"
            rf"(?:\s*:\s*(?P<type>{_QNAME}(?:\s*,\s*{_QNAME})*))?"
            rf"(?:\s*=\s*(?P<default>\([^;{{}}]*\)|\"[^\"]*\"|[^;{{}}\n]+?))?"
            rf"\s*(?:\{{[^{{}}]*\}})?\s*(?:;|(?=\n\s*(?:attribute|ref|part|item|port)\b)|$)"
        )
        for m in attr_re.finditer(direct_body):
            attrs.append(PropertyDef(
                m.group("name"), m.group("type") or "", "attribute",
                default=(m.group("default") or "").strip() or None,
                redefines=m.group("name") if m.group("red") else None,
                owner=owner))

        # References, including redefinitions with an assignment and no type.
        ref_re = re.compile(
            rf"\bref\s+(?P<red>:>>\s*)?(?P<name>{_IDENT})"
            rf"(?:\s*:\s*(?P<type>{_QNAME}(?:\s*,\s*{_QNAME})*))?\s*"
            rf"(?:\[(?P<mult>[^]]+)\])?"
            rf"(?:\s*=\s*(?P<default>[^;]+))?\s*;"
        )
        for m in ref_re.finditer(direct_body):
            lo, hi = self._mult(m.group("mult"))
            refs.append(PropertyDef(
                m.group("name"), m.group("type") or "", "ref", lo, hi,
                default=(m.group("default") or "").strip() or None,
                redefines=m.group("name") if m.group("red") else None,
                owner=owner))

        # Simple owned usages. Nested/block usages are handled recursively by
        # _parse_instance_scope, but their declaration is still useful in the IR.
        usage_re = re.compile(
            rf"\b(?P<kind>part|item|port)\s+(?P<red>:>>\s*)?(?P<name>{_IDENT})"
            rf"(?:\s*:\s*(?P<type>{_QNAME}(?:\s*,\s*{_QNAME})*))?\s*"
            rf"(?:\[(?P<mult>[^]]+)\])?\s*;"
        )
        for m in usage_re.finditer(direct_body):
            lo, hi = self._mult(m.group("mult"))
            usages.append(PropertyDef(
                m.group("name"), m.group("type") or "", m.group("kind"), lo, hi,
                redefines=m.group("name") if m.group("red") else None, owner=owner))
        return attrs, refs, usages

    def _parse_type_defs(self, text, model):
        for keyword in ("item", "part", "interface", "port"):
            pat = re.compile(
                rf"(?P<abstract>abstract\s+)?{keyword}\s+def\s+(?P<name>{_IDENT})\s*"
                rf"(?::>\s*(?P<parent>{_QNAME}(?:\s*,\s*{_QNAME})*))?\s*(?P<brace>\{{)?"
            )
            for m in pat.finditer(text):
                body = self._block(text, m.end()-1) if m.group("brace") else ""
                attrs, refs, usages = self._members(body, m.group("name"))
                model.types.append(TypeDef(
                    m.group("name"), keyword,
                    self._split_types(m.group("parent") or ""),
                    bool(m.group("abstract")), None, attrs, refs, usages
                ))

    def _parse_action_defs(self, text, model):
        pat = re.compile(
            rf"(?P<abstract>abstract\s+)?action\s+def\s+(?P<name>{_IDENT})\s*"
            rf"(?::>\s*(?P<parent>{_QNAME}(?:\s*,\s*{_QNAME})*))?\s*\{{"
        )
        for m in pat.finditer(text):
            body = self._block(text, m.end()-1)
            attrs, refs, usages = self._members(body, m.group("name"))
            params = []
            for pm in re.finditer(
                rf"\bin\s+(?P<name>{_IDENT})\s*:\s*(?P<type>{_QNAME}(?:\s*,\s*{_QNAME})*)"
                rf"\s*(?:\[(?P<mult>[^]]+)\])?\s*;", body):
                lo, hi = self._mult(pm.group("mult"))
                params.append(PropertyDef(pm.group("name"), pm.group("type"), "parameter", lo, hi,
                                          direction="in", owner=m.group("name")))
            action = ActionDef(m.group("name"), self._split_types(m.group("parent") or ""),
                               params, attrs, [], [], None, bool(m.group("abstract")))
            action.items = self._parse_action_items(body, action.name)
            model.actions.append(action)

    def _parse_action_items(self, body, owner):
        out = []
        pat = re.compile(rf"\bitem\s+(?P<name>{_IDENT})\s*:\s*(?P<type>{_QNAME})\s*\{{")
        for m in pat.finditer(body):
            b = self._block(body, m.end()-1)
            attrs, refs, usages = self._members(b, f"{owner}.{m.group('name')}")
            out.append(InstanceDef(m.group("name"), [m.group("type")], "item", owner,
                                   attrs, refs, usages))
        return out

    def _parse_connections(self, text, model):
        pat = re.compile(rf"connection\s+def\s+(?P<name>{_IDENT})\s*"
                         rf"(?::>\s*(?P<parent>{_QNAME}(?:\s*,\s*{_QNAME})*))?\s*\{{")
        for m in pat.finditer(text):
            body = self._block(text, m.end()-1)
            ends = []
            end_re = re.compile(rf"end\s+(?:item\s+)?(?P<name>{_IDENT})\s*:\s*"
                                rf"(?P<type>{_QNAME})\s*(?:\[(?P<mult>[^]]+)\])?\s*;")
            for e in end_re.finditer(body):
                lo, hi = self._mult(e.group("mult"))
                ends.append(EndDef(e.group("name"), e.group("type"), lo, hi))
            model.connections.append(ConnectionDef(m.group("name"),
                                                   self._split_types(m.group("parent") or ""), ends))

    def _parse_instances(self, text, model):
        self._parse_instance_scope(text, model, None)

    def _parse_instance_scope(self, text, model, owner):
        pat = re.compile(
            rf"\b(?P<kind>part|item|port)\s+(?:(?P<red>:>>\s*))?(?P<name>{_IDENT})"
            rf"(?:\s*:\s*(?P<type>{_QNAME}(?:\s*,\s*{_QNAME})*))?\s*"
            rf"(?:\[(?P<mult>[^]]+)\])?\s*(?P<brace>\{{)?"
        )
        pos = 0
        while True:
            m = pat.search(text, pos)
            if not m:
                break
            prefix = text[max(0, m.start()-16):m.start()]
            if m.group("name") == "def" or re.search(r"\b(def|abstract\s+def)\s*$", prefix):
                pos = m.end()
                continue

            body = self._block(text, m.end()-1) if m.group("brace") else ""
            type_names = self._split_types(m.group("type") or "")
            inst = InstanceDef(m.group("name"), type_names, m.group("kind"), owner)
            attrs, refs, usages = self._members(body, inst.name if owner is None else f"{owner}.{inst.name}")
            inst.attributes, inst.references, inst.usages = attrs, refs, usages
            model.instances.append(inst)

            if body:
                nested_owner = inst.name if owner is None else f"{owner}.{inst.name}"
                self._parse_instance_scope(body, model, nested_owner)
                # Skip the complete owned block in this scope. Its contents have
                # already been recursively parsed and must not be emitted twice.
                pos = m.end() - 1 + len(body) + 1
            else:
                pos = m.end()

    def _parse_connection_instances(self, text, model):
        known = {c.name for c in model.connections}
        if not known:
            return
        pat = re.compile(rf"\bconnection\s+(?P<name>{_IDENT})\s*:\s*(?P<type>{_QNAME})\s*\{{")
        for m in pat.finditer(text):
            if m.group("type") not in known:
                continue
            body = self._block(text, m.end()-1)
            vals = {}
            # values can be multiline tuples; capture until semicolon.
            for v in re.finditer(rf"(?P<k>{_IDENT})\s*=\s*(?P<v>[^;]+)\s*;", body):
                vals[v.group("k")] = v.group("v").strip()
            model.connection_instances.append(ConnectionInstance(m.group("name"), m.group("type"), vals))

    def _parse_constraints(self, text, model):
        """
        Parse constraints and preserve the definition that owns each one.

        A constraint is semantically attached to the nearest enclosing SysML
        definition (item/part/interface/port/action).  The previous
        implementation discarded that information, which made it impossible
        for downstream writers to translate constraints such as
        `LivingRoom::classification` into OWL restrictions.
        """

        # Collect the source spans of definitions that can own constraints.
        # We use the existing brace-aware _block() helper so nested braces in
        # a definition do not confuse the owner calculation.
        owner_spans = []

        def collect(pattern):
            for dm in re.finditer(pattern, text):
                brace = dm.end() - 1
                if brace >= len(text) or text[brace] != "{":
                    continue
                body = self._block(text, brace)
                owner_spans.append(
                    (dm.start(), brace + 1 + len(body), dm.group("name"))
                )

        collect(
            rf"(?P<abstract>abstract\s+)?"
            rf"(?:item|part|interface|port)\s+def\s+"
            rf"(?P<name>{_IDENT})\s*"
            rf"(?:\:\>\s*(?P<parent>{_QNAME}(?:\s*,\s*{_QNAME})*))?\s*\{{"
        )
        collect(
            rf"(?P<abstract>abstract\s+)?action\s+def\s+"
            rf"(?P<name>{_IDENT})\s*"
            rf"(?:\:\>\s*(?P<parent>{_QNAME}(?:\s*,\s*{_QNAME})*))?\s*\{{"
        )

        def owner_for(position):
            matches = [
                (start, end, name)
                for start, end, name in owner_spans
                if start <= position < end
            ]
            if not matches:
                return None
            # If definitions are nested, choose the innermost one.
            return min(matches, key=lambda span: span[1] - span[0])[2]

        pat = re.compile(
            rf"\b(?:assert\s+)?constraint(?:\s+def)?"
            rf"(?:\s+(?P<name>{_IDENT}))?\s*\{{"
        )
        for m in pat.finditer(text):
            body = self._block(text, m.end() - 1).strip()
            if body:
                model.constraints.append(
                    ConstraintDef(
                        expression=body,
                        name=m.group("name"),
                        owner=owner_for(m.start()),
                    )
                )

        for m in re.finditer(r"\bconstraint\s*:\s*([^;]+);", text):
            model.constraints.append(
                ConstraintDef(
                    expression=m.group(1).strip(),
                    owner=owner_for(m.start()),
                )
            )
