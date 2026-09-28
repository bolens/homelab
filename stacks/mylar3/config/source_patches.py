"""Checked source boundaries for independently maintained native adapters."""

import ast


def function_span(source, name):
    matches = [
        n
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.FunctionDef) and n.name == name
    ]
    if len(matches) != 1:
        raise ValueError("Upstream function changed: " + name)
    node = matches[0]
    lines = source.splitlines(keepends=True)
    return "".join(lines[node.lineno - 1 : node.end_lineno])


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError("Native source changed; review candidate image")
    return source.replace(before, after, 1)
