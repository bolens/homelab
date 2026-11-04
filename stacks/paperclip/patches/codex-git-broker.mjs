import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";

// These are the source modules loaded by the pinned image's tsx loader.
// Refuse other releases rather than silently patching an unknown implementation.
const sources = [
  ["/app/packages/adapter-utils/src/acpx-engine/execute.ts",
    "aa8bcf22818f0a0755c927a5f896023068ca506d5669d0898696afe3dc6635ea"],
  ["/app/packages/adapters/codex-local/src/server/execute.ts",
    "f273c0747f8fa3bcf409656246ea87023d855bbf361b9946d1a8df8c3b8c9666"],
];
const before = 'key === "PAPERCLIP_API_KEY" || !/key|secret|token/i.test(key)';
const after = 'key === "PAPERCLIP_API_KEY" || key === "PAPERCLIP_GITHUB_BROKER_TOKEN" || !/key|secret|token/i.test(key)';
const updates = [];
for (const [path, digest] of sources) {
  const source = await readFile(path, "utf8");
  if (createHash("sha256").update(source).digest("hex") !== digest
      || source.split(before).length !== 2) {
    throw new Error(`Unexpected upstream Codex environment policy: ${path}`);
  }
  updates.push([path, source.replace(before, after)]);
}
for (const [path, source] of updates) await writeFile(path, source);
console.log("Patched Codex CLI and ACP scoped GitHub broker capability forwarding.");
