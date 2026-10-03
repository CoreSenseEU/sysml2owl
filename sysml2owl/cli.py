import argparse
from pathlib import Path

from .parser import SysMLParser
from .owl_writer import OWLWriter


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Generic SysML v2 subset to OWL/RDF translator"
    )

    p.add_argument(
        "inputs",
        nargs="+",
        help="SysML files or directories to parse"
    )

    p.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output OWL file"
    )

    p.add_argument(
        "--base-iri",
        required=True,
        help="Base IRI for the generated ontology"
    )

    args = p.parse_args(argv)

    # Validate input paths
    for item in args.inputs:
        path = Path(item)

        if not path.exists():
            p.error(f"Input path does not exist: {path}")

    # Validate output path
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    parser = SysMLParser()
    model = None

    for item in args.inputs:
        path = Path(item)

        parsed = (
            parser.parse_directory(str(path))
            if path.is_dir()
            else parser.parse_file(str(path))
        )

        if model is None:
            model = parsed
        else:
            model.types += parsed.types
            model.instances += parsed.instances
            model.connections += parsed.connections
            model.connection_instances += parsed.connection_instances
            model.actions += parsed.actions
            model.constraints += parsed.constraints
            model.imports += parsed.imports
            model.source_files += parsed.source_files

    triples = OWLWriter(args.base_iri).write(
        model,
        str(output_path)
    )

    print(f"Generated {output_path} ({triples} RDF triples)")


if __name__ == "__main__":
    main()
