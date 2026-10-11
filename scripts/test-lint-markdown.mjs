import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { test } from "node:test";

const command = path.resolve("scripts/lint-markdown.mjs");
const config = path.resolve(".markdownlint.json");
const directory = mkdtempSync(path.join(tmpdir(), "literal-markdown-"));
const good = path.join(directory, "good.md");
const bad = path.join(directory, "bad.md");
const literal = path.join(directory, "literal{a,b}[1].md");
const disabled = path.join(directory, "disabled.md");
writeFileSync(good, "# Good\n\nText.\n");
writeFileSync(bad, "# Bad\n\nText.   \n");
writeFileSync(literal, "# Literal\n\nText.\n");
writeFileSync(disabled, "<!-- markdownlint-disable MD009 -->\n# Disabled\n\nText.   \n");
const run = (...args) => spawnSync(process.execPath, [command, "--config", config, ...args], { encoding: "utf8" });

try {
  test("valid files and inline rule suppression keep success behavior", () => {
    assert.equal(run(good, disabled).status, 0);
  });
  test("enabled MD009 violations fail with their rule name", () => {
    const result = run(bad);
    assert.equal(result.status, 1);
    assert.match(result.stderr, /MD009\/no-trailing-spaces/);
  });
  test("brace and bracket filename is read literally", () => {
    assert.equal(run(literal).status, 0);
  });
  test("glob expressions do not select other files", () => {
    const result = run(path.join(directory, "*.md"));
    assert.equal(result.status, 1);
    assert.match(result.stderr, /ENOENT/);
  });
  test("no file arguments retain successful usage output", () => {
    const result = run();
    assert.equal(result.status, 0);
    assert.match(result.stdout, /Usage:/);
  });
  test("unsupported options and missing config fail", () => {
    assert.equal(run("--fix", good).status, 1);
    assert.equal(run("--config").status, 1);
  });
} finally {
  // node:test runs these synchronous bodies before process exit.
  process.on("exit", () => rmSync(directory, { recursive: true, force: true }));
}
