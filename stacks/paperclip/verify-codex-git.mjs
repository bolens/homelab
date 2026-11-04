import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const expectedBroker = !process.argv.includes("--expect-missing");
for (const path of [
  "/app/packages/adapter-utils/src/acpx-engine/execute.ts",
  "/app/packages/adapters/codex-local/src/server/execute.ts",
]) {
  const source = await readFile(path, "utf8");
  const matches = [...source.matchAll(/Object\.keys\(env\)\.filter\(key => [^\n]+?\)/g)];
  // Read the actual upstream filter, including its nested test(key) call.
  const start = source.indexOf("Object.keys(env).filter(key =>");
  assert.equal(matches.length, 1, `Expected one shell allowlist in ${path}`);
  const expression = source.slice(start, source.indexOf("\n", start)).replace(/,\s*$/, "");
  const env = Object.fromEntries([
    "PATH", "PAPERCLIP_API_KEY", "PAPERCLIP_GITHUB_BROKER_TOKEN",
    "GH_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY", "SERVICE_SECRET", "DATABASE_PASSWORD_KEY",
  ].map(key => [key, "fixture"]));
  const allowed = new Function("env", `return ${expression}`)(env);
  assert(allowed.includes("PATH"));
  assert(allowed.includes("PAPERCLIP_API_KEY"));
  assert.equal(allowed.includes("PAPERCLIP_GITHUB_BROKER_TOKEN"), expectedBroker);
  for (const key of ["GH_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY", "SERVICE_SECRET", "DATABASE_PASSWORD_KEY"])
    assert(!allowed.includes(key), `${key} must remain excluded`);
}
console.log(`Both Codex shell policies verified: scoped broker ${expectedBroker ? "forwarded" : "missing"}, provider credentials excluded.`);
