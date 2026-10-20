"""Keep the selected NetExec release on its compatible Certipy distribution."""

from pathlib import Path
import sys
import tomllib

CERTIPY_COMMIT = "069e03113095aa02772aa3d8debea90654933fe4"
ORIGINAL = "certipy-ad @ git+https://github.com/Pennyw0rth/Certipy"
PINNED = ORIGINAL + "@" + CERTIPY_COMMIT


def pin_certipy(source: str) -> str:
    dependencies = tomllib.loads(source)["project"]["dependencies"]
    if dependencies.count(ORIGINAL) != 1 or source.count(ORIGINAL) != 1:
        raise ValueError("NetExec Certipy declaration changed; review the dependency before building")
    result = source.replace(ORIGINAL, PINNED)
    expected = [PINNED if item == ORIGINAL else item for item in dependencies]
    if tomllib.loads(result)["project"]["dependencies"] != expected:
        raise ValueError("NetExec dependency rewrite did not preserve the selected requirements")
    return result


def main() -> None:
    target = Path(sys.argv[1])
    target.write_text(pin_certipy(target.read_text()))


if __name__ == "__main__":
    main()
