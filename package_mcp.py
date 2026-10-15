"""Package an explicit source allowlist; never walk private local configurations."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
FILES = (
    "README.md", ".gitignore", "ticket_mcp.py", "demo_api.py",
    "smoke_mcp.py", "requirements-mcp.lock.txt",
    "tests/test_mcp.py", "tests/test_ticket_tool.py", "tests/test_cli.py", "tests/test_package.py", "package_mcp.py",
    "examples/mcp.example.json", "examples/ticket.env.example",
)


def create_package(destination: Path, root: Path = ROOT) -> None:
    """Validate every source before writing; exclude all non-allowlisted paths."""
    destination.parent.mkdir(exist_ok=True)
    for name in FILES:
        source = root / name
        if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Source must be a regular file inside the project: {name}")
        if not source.is_file():
            raise FileNotFoundError(f"Required source missing: {name}")
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(root / name, f"ticket-mcp-demo/{name}")


def main():
    destination = ROOT / "deliverables/raymond-lee-ticket-mcp-source.zip"
    create_package(destination)
    print(f"Packaged {len(FILES)} explicitly selected source files: {destination}")


if __name__ == "__main__":
    main()
