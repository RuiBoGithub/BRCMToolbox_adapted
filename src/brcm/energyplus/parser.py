"""MATLAB-compatible positional IDF parser with an adapter interface."""
from __future__ import annotations
from abc import ABC,abstractmethod
from pathlib import Path
import re
import warnings
from .records import IDFObject
from ..exceptions import DataFormatError

SUPPORTED_VERSIONS=("7.0","7.1","7.2","8.0","8.1","23.2")

def _strip_comments(text: str) -> str:
    lines=[]
    for line in text.splitlines():
        quoted=False; out=[]
        for char in line:
            if char=='"': quoted=not quoted
            if char=='!' and not quoted: break
            out.append(char)
        lines.append(''.join(out))
    return '\n'.join(lines)

def get_objects_from_string(text: str) -> list[IDFObject]:
    text=_strip_comments(text); objects=[]; fields=[]; token=[]; quoted=False
    for char in text:
        if char=='"': quoted=not quoted; continue
        if char in ',;' and not quoted:
            fields.append(''.join(token).strip()); token=[]
            if char==';':
                if not fields[0]: raise DataFormatError("IDF object type is empty")
                objects.append(IDFObject(fields[0],tuple(fields[1:]))); fields=[]
        else: token.append(char)
    if quoted: raise DataFormatError("Unterminated quoted IDF field")
    if ''.join(token).strip() or fields: raise DataFormatError("IDF object is missing its terminating semicolon")
    return objects

def get_idf_objects(path: str|Path) -> tuple[list[IDFObject],list[str]]:
    objects=get_objects_from_string(Path(path).read_text(encoding='utf-8-sig'))
    return objects,sorted({o.object_type for o in objects})

def parse_idd(path: str|Path) -> dict[str,tuple[str,...]]:
    """Extract ordered ``\field`` labels from a legacy EnergyPlus IDD."""
    result={}; current=None; labels=[]
    for line in Path(path).read_text(encoding='latin-1').splitlines():
        bare=line.split('!',1)[0]
        # Object declarations are the only unindented identifier/comma lines.
        # Extensible IDD objects may never terminate their declared fields with
        # a semicolon, so the next declaration is the reliable object boundary.
        match=re.match(r'^([A-Za-z][A-Za-z0-9:_.-]*)\s*,\s*$',bare)
        if match:
            if current is not None: result[current.casefold()]=tuple(labels)
            current=match.group(1).strip(); labels=[]
            continue
        if current is None: continue
        declaration=re.match(r'^\s*[AN]\d+\s*[,;].*?\\field\s+(.+?)\s*$',bare)
        if declaration:
            labels.append(declaration.group(1).strip())
    if current is not None: result[current.casefold()]=tuple(labels)
    return result

def get_idd_version(path: str|Path) -> str|None:
    """Read the EnergyPlus version declared by an IDD header."""
    with Path(path).open(encoding='latin-1') as stream:
        for _ in range(20):
            line=stream.readline()
            if not line: break
            match=re.match(r'!IDD_Version\s+(\S+)',line.strip(),re.IGNORECASE)
            if match: return match.group(1)
    return None

class EnergyPlusParser(ABC):
    @abstractmethod
    def parse(self,source: str|Path) -> list[IDFObject]: ...

class LegacyIDDParser(EnergyPlusParser):
    def __init__(self,idd_directory: str|Path|None=None,idd_path: str|Path|None=None):
        if idd_directory is not None and idd_path is not None:
            raise ValueError("Pass either idd_directory or idd_path, not both")
        self.idd_directory=Path(idd_directory) if idd_directory else Path(__file__).parents[3]/'origin_matlab'/'toolbox'/'EP2BRCM'/'IDDFiles'
        self.idd_path=Path(idd_path) if idd_path else None
    def parse(self,source):
        objects,_=get_idf_objects(source); version=next((o.values[0] for o in objects if o.object_type.casefold()=='version'),None)
        if not version: raise DataFormatError("IDF has no Version object")
        if self.idd_path is not None:
            resolved_idd=self.idd_path
        elif version.startswith('23.2'):
            resolved_idd=Path(__file__).parents[3]/'_E+'/'idd'/'23.2'/'Energy+.idd'
        else:
            newer_eight=version.startswith('8.') and not version.startswith(('8.0','8.1'))
            prefix='8.1' if newer_eight else next((v for v in SUPPORTED_VERSIONS[:5] if version.startswith(v)),None)
            if prefix is None: raise DataFormatError(f"Unsupported EnergyPlus version {version}; pass idd_path explicitly")
            if newer_eight:
                warnings.warn(f"Using the bundled EnergyPlus 8.1 IDD for version {version}, matching MATLAB legacy behavior",UserWarning,stacklevel=2)
            names={'7.0':'V7-0-0-Energy+.idd','7.1':'V7-1-0-Energy+.idd','7.2':'V7-2-0-Energy+.idd','8.0':'V8-0-0-Energy+.idd','8.1':'V8-1-0-Energy+.idd'}
            resolved_idd=self.idd_directory/names[prefix]
        if not resolved_idd.is_file():
            raise DataFormatError(f"EnergyPlus IDD does not exist for version {version}: {resolved_idd}")
        if self.idd_path is not None:
            declared=get_idd_version(resolved_idd)
            requested='.'.join(version.split('.')[:2])
            actual='.'.join(declared.split('.')[:2]) if declared else None
            if actual != requested:
                raise DataFormatError(
                    f"EnergyPlus IDF version {version} does not match IDD version {declared or 'unknown'}: {resolved_idd}")
        labels=parse_idd(resolved_idd); extended=[]
        for obj in objects:
            field_names=labels.get(obj.object_type.casefold())
            if field_names is None: raise DataFormatError(f"Object {obj.object_type!r} not found in resolved IDD {resolved_idd}")
            # Detailed surfaces are extensible; synthesize vertex labels beyond the IDD base declaration.
            names_for_object=list(field_names)
            if obj.object_type.casefold() in ('buildingsurface:detailed','fenestrationsurface:detailed'):
                base=10 if obj.object_type.casefold()=='buildingsurface:detailed' else 9
                while len(names_for_object)<len(obj.values):
                    n=(len(names_for_object)-base)//3+1; axis='XYZ'[(len(names_for_object)-base)%3]
                    names_for_object.append(f"Vertex {n} {axis}-coordinate")
            extended.append(IDFObject(obj.object_type,obj.values,tuple(names_for_object[:len(obj.values)])))
        return extended

# The adapter now handles both legacy and explicitly supplied modern IDDs.
IDDParser=LegacyIDDParser

getObjectsFromString=get_objects_from_string
getIDFObjects=get_idf_objects
getIDDObjects=parse_idd
def get_extended_idf_objects(path,parser=None):
    objects=(parser or LegacyIDDParser()).parse(path); return objects,sorted({o.object_type for o in objects})
getExtendedIDFObjects=get_extended_idf_objects
