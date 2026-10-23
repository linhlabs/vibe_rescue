"""Resolve Python import spellings to indexed modules without executing code.

Repositories that alter sys.path often import a local module by a shorter name.
A suffix is accepted only when exactly one indexed module has that suffix. This
is source-level evidence, not proof of the module loaded at runtime.
"""

from collections import defaultdict


def unique_suffixes(modules):
    matches = defaultdict(set)
    for module in modules:
        parts = module.split(".")
        for start in range(len(parts)):
            matches[".".join(parts[start:])].add(module)
    return {alias: next(iter(found)) for alias, found in matches.items() if len(found) == 1}


def resolve_qualified(name, suffixes):
    """Replace the longest uniquely mapped module prefix in a qualified name."""
    parts = name.split(".")
    for size in range(len(parts), 0, -1):
        prefix = ".".join(parts[:size])
        if prefix in suffixes:
            return ".".join((suffixes[prefix], *parts[size:]))
    return name


def from_base(current_module, imported_module, level):
    """Return the absolute lexical base for an ImportFrom node."""
    if not level:
        return imported_module or ""
    parts = current_module.split(".")[:-level]
    return ".".join((*parts, *((imported_module or "").split(".") if imported_module else ())))
