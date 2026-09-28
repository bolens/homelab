"""Checked native database transactions adaptation."""

import ast
from pathlib import Path
import sys
from source_patches import replace_once
from source_patches import function_span

MARKER = "# homelab-database-transactions-v1"


def patched(name, source):
    if MARKER in source:
        return source
    if name == "db.py":
        before = function_span(source, "action")
        after = replace_once(
            before, "                    break", "                    return sqlResult"
        )
        after = replace_once(
            after,
            "                        time.sleep(1)",
            "                        if attempt >= 5:\n                            logger.error('Database action failed after %s attempts: %s' % (attempt, e))\n                            return None",
        )
        after = replace_once(
            after,
            "\n            return sqlResult",
            "\n                finally:\n                    if self.connection.in_transaction:\n                        self.connection.rollback()\n                time.sleep(1)\n            return None",
        )
        source = replace_once(source, before, after)
        source = replace_once(
            source,
            "\n        self.action(query, list(valueDict.values()) + list(keyDict.values()))\n",
            "\n        sqlResult = self.action(query, list(valueDict.values()) + list(keyDict.values()))\n        if sqlResult is None:\n            return\n",
        )
    else:
        raise ValueError("Unsupported patch target: " + name)
    source = MARKER + "\n" + source
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    changes = {
        root / name: patched(name, (root / name).read_text()) for name in ("db.py",)
    }
    for path, value in changes.items():
        path.write_text(value)


if __name__ == "__main__":
    main(sys.argv[1])
