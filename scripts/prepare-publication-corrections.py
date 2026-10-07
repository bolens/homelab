#!/usr/bin/env python3
"""Prepare private reviewed correction plans without executing any mutation."""

import argparse
import json

from publication_corrections_plan import prepare, read, write


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope-file", required=True)
    parser.add_argument("--review-file", required=True)
    parser.add_argument("--output", required=True)
    values = parser.parse_args(argv)
    try:
        scope, _ = read(values.scope_file)
        review, _ = read(values.review_file)
        plan = prepare(scope, review)
        write(plan, values.output)
    except Exception:
        print(json.dumps({"state": "review-required", "executable": False}))
        return 1
    print(
        json.dumps({"state": "prepared", "executable": False, "token": plan["token"]})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
