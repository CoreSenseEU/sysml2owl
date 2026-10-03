# sysml2owl

`sysml2owl` is a generic converter that transforms a subset of **SysML v2 CORESENSE models into OWL/RDF ontologies**.

Although the converter is distributed as a **ROS 2 package**, the conversion itself is not ROS-specific. ROS 2 provides the packaging, installation, and integration mechanism, while the converter operates on SysML v2 models independently of the application domain.

The converter follows a simple pipeline:

```text
SysML v2 model
      │
      ▼
  SysMLParser
      │
      ▼
 Semantic Model
      │
      ▼
   OWLWriter
      │
      ▼
   OWL/RDF
```

The converter does not contain application-specific models or ontologies. Concrete models, such as the MIRTE model, are maintained by the corresponding application package.

---

## ROS 2 workspace integration

The converter can be built using the standard ROS 2 build system:

```bash
cd ~/ros2_ws
colcon build --packages-select sysml2owl
source install/setup.bash
```

It can then be executed through:

```bash
ros2 run sysml2owl sysml2owl
```

The converter does not depend on a predefined model directory or ontology output directory. Input and output paths are explicitly provided when the converter is executed.

---

## Command-line interface

The general syntax is:

```bash
ros2 run sysml2owl sysml2owl \
    <INPUT> [<INPUT> ...] \
    --base-iri <BASE_IRI> \
    --output <OUTPUT>
```

### Inputs

One or more SysML files or directories can be provided.

For example:

```bash
ros2 run sysml2owl sysml2owl \
    model/
```

or:

```bash
ros2 run sysml2owl sysml2owl \
    model/system.sysml \
    model/architecture.sysml
```

When a directory is provided, the converter parses the SysML files contained in that directory.

### Base IRI

The `--base-iri` option specifies the base IRI used for resources generated in the ontology.

Example:

```bash
--base-iri https://coresense.eu/mirte#
```

The base IRI is application/model specific and is therefore not hard-coded into the converter.

### Output

The `--output` option specifies where the generated OWL ontology is written.

Example:

```bash
--output ~/ros2_ws/src/cs_demo_mirte/ontology/sysml.owl
```

The output directory is created automatically if it does not already exist.

---

# Example: MIRTE execution

The MIRTE model is maintained by the `cs_demo_mirte` package rather than by `sysml2owl`.

The application contains:

```text
cs_demo_mirte/
├── model/
│   ├── MIRTE_ontology.sysml
│   ├── MIRTE_selfModel.sysml
│   ├── MIRTE_architecture.sysml
│   └── MIRTE_mission.sysml
│
└── ontology/
    └── sysml.owl
```

The SysML files can be converted into the MIRTE ontology with:

```bash
ros2 run sysml2owl sysml2owl \
    ~/ros2_ws/src/cs_demo_mirte/model/MIRTE_ontology.sysml \
    ~/ros2_ws/src/cs_demo_mirte/model/MIRTE_selfModel.sysml \
    ~/ros2_ws/src/cs_demo_mirte/model/MIRTE_architecture.sysml \
    ~/ros2_ws/src/cs_demo_mirte/model/MIRTE_mission.sysml \
    --base-iri https://coresense.eu/mirte# \
    --output ~/ros2_ws/src/cs_demo_mirte/ontology/sysml.owl
```

Alternatively, because the converter accepts directories:

```bash
ros2 run sysml2owl sysml2owl \
    ~/ros2_ws/src/cs_demo_mirte/model \
    --base-iri https://coresense.eu/mirte# \
    --output ~/ros2_ws/src/cs_demo_mirte/ontology/sysml.owl
```

The second form is the recommended approach when all SysML files belonging to the same model are stored in the same directory.

---

## Generated ontology

The resulting ontology is stored in the application package:

```text
cs_demo_mirte/ontology/sysml.owl
```

For MIRTE, the ontology uses:

```text
https://coresense.eu/mirte#
```

as its base IRI.

The generated ontology can subsequently be consumed by other components or ROS 2 packages as the semantic representation of the MIRTE system.

For example:

```text
cs_demo_mirte/model/*.sysml
              │
              │ sysml2owl
              ▼
cs_demo_mirte/ontology/sysml.owl
              │
              ▼
       MIRTE runtime components
```