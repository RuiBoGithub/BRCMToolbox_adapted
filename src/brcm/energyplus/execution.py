"""Prepare EnergyPlus input files and their external resources for execution."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path, PureWindowsPath
import hashlib
import os
import shutil

from .parser import get_objects_from_string


# Object field positions are zero-based after the object type.  Additions to
# this registry must be backed by an EnergyPlus schema: path-looking strings in
# arbitrary fields are deliberately not treated as files.
_EXTERNAL_FILE_FIELDS = {
    "construction:windowdatafile": (1,),
    "schedule:file": (2,),
}


def _tokens_with_spans(text: str) -> list[tuple[str, int, int]]:
    """Return IDF tokens and their editable spans, ignoring comments."""
    result = []
    chars: list[str] = []
    positions: list[int] = []
    quoted = comment = False
    for index, char in enumerate(text):
        if comment:
            if char in "\r\n":
                comment = False
            else:
                continue
        if char == "!" and not quoted:
            comment = True
            continue
        if char == '"':
            quoted = not quoted
            continue
        if char in ",;" and not quoted:
            value = "".join(chars).strip()
            significant = [p for c, p in zip(chars, positions) if not c.isspace()]
            start = significant[0] if significant else index
            end = significant[-1] + 1 if significant else index
            result.append((value, start, end))
            chars, positions = [], []
        else:
            chars.append(char)
            positions.append(index)
    return result


def _external_references(text: str) -> list[tuple[str, int, int]]:
    objects = get_objects_from_string(text)
    tokens = _tokens_with_spans(text)
    references = []
    cursor = 0
    for obj in objects:
        object_tokens = tokens[cursor : cursor + len(obj.values) + 1]
        cursor += len(obj.values) + 1
        for field_index in _EXTERNAL_FILE_FIELDS.get(obj.object_type.casefold(), ()):
            if field_index < len(obj.values) and obj.values[field_index].strip():
                _, start, end = object_tokens[field_index + 1]
                references.append((obj.values[field_index].strip(), start, end))
    return references


def _path_parts(reference: str) -> Path:
    # EnergyPlus IDFs commonly carry Windows separators even when run elsewhere.
    return Path(*PureWindowsPath(reference).parts) if "\\" in reference else Path(reference)


def _resolve_resource(reference: str, source_directory: Path,
                      search_paths: tuple[Path, ...]) -> Path | None:
    path = _path_parts(reference)
    candidates = [path] if path.is_absolute() else [source_directory / path]
    if not path.is_absolute():
        candidates.extend(root / path for root in search_paths)
        candidates.extend(root / path.name for root in search_paths)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    # A search root denotes an installation/resource tree, not a prescribed
    # directory layout.  Match the requested leaf only when it is unambiguous.
    if not path.is_absolute():
        matches = []
        for root in search_paths:
            if root.is_dir():
                matches.extend(item for item in root.rglob(path.name) if item.is_file())
        if len(matches) == 1:
            return matches[0].resolve()
    return None


def _default_search_paths() -> tuple[Path, ...]:
    roots = []
    for variable in ("ENERGYPLUS_HOME", "ENERGYPLUS_ROOT"):
        if os.environ.get(variable):
            roots.append(Path(os.environ[variable]))
    executable = shutil.which("energyplus") or shutil.which("EnergyPlus")
    if executable:
        roots.append(Path(executable).resolve().parent)
    # Standard installation roots are optional generic search trees; no
    # particular resource subdirectory or filename is assumed.
    roots.extend(Path("/Applications").glob("EnergyPlus-*"))
    roots.extend(Path("C:/").glob("EnergyPlus*"))
    return tuple(roots)


def prepare_energyplus_case(idf_path: str | Path, work_directory: str | Path,
                            external_search_paths: Iterable[str | Path] | None = None) -> Path:
    """Copy an IDF into *work_directory* and stage the external files it names.

    Relative references that remain inside the run directory retain their
    spelling.  Other resolved resources are copied below ``external_files`` and
    only the corresponding parsed IDF field is rewritten.
    """
    source = Path(idf_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"EnergyPlus IDF does not exist: {source}")
    work = Path(work_directory).resolve()
    work.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8-sig")
    references = _external_references(text)
    search_paths = tuple(Path(item).resolve() for item in external_search_paths) if external_search_paths is not None else _default_search_paths()
    replacements = []
    used_destinations: dict[Path, Path] = {}
    for original, start, end in references:
        resolved = _resolve_resource(original, source.parent, search_paths)
        if resolved is None:
            raise FileNotFoundError(f"Unable to resolve EnergyPlus external resource {original!r} referenced by {source}")
        referenced_path = _path_parts(original)
        if referenced_path.is_absolute():
            continue
        destination = (work / referenced_path).resolve()
        try:
            destination.relative_to(work)
            replacement = original
        except ValueError:
            digest = hashlib.sha256(str(resolved).encode()).hexdigest()[:10]
            destination = work / "external_files" / digest / resolved.name
            replacement = destination.relative_to(work).as_posix()
        previous = used_destinations.get(destination)
        if previous is not None and previous != resolved:
            raise FileExistsError(f"External resources collide at {destination}: {previous} and {resolved}")
        used_destinations[destination] = resolved
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination != resolved:
            shutil.copy2(resolved, destination)
        if replacement != original:
            replacements.append((start, end, replacement))
    for start, end, replacement in reversed(replacements):
        text = text[:start] + replacement + text[end:]
    working_idf = work / source.name
    working_idf.write_text(text, encoding="utf-8")
    return working_idf
