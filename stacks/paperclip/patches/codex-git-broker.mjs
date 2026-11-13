import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";

// The pinned runtime bundles these workspace source modules. Rebuild that
// runtime after patching; changing TypeScript alone leaves the old policy active.
// Refuse other releases rather than silently patching an unknown implementation.
const sources = [
  ["/app/packages/adapter-utils/src/acpx-engine/execute.ts",
    "00635e57744c7407070618453852ede5002382159a81a4f31ceeac0551d3e725"],
  ["/app/packages/adapters/codex-local/src/server/execute.ts",
    "956ae4298849902a07cb02d2a15fc4d9073882725c06423912e67bffd35c7dfb"],
];
const policyPath = "/app/packages/adapter-utils/src/codex-shell-environment.ts";
const policyDigest = "cf2db3af2f9c248884b0d121786589b804593ca49cfce6e29d55a20efff163a6";
const before = 'key === "PAPERCLIP_API_KEY" || configuredSecrets.has(key) || !SECRET_NAME.test(key)';
const after = 'key === "PAPERCLIP_API_KEY" || key === "PAPERCLIP_GITHUB_BROKER_TOKEN" || configuredSecrets.has(key) || !SECRET_NAME.test(key)';
// Bind the build operation as well as both security-sensitive inputs.
const bundlerPath = "/app/server/scripts/bundle-runtime.mjs";
const bundler = await readFile(bundlerPath);
if (createHash("sha256").update(bundler).digest("hex") !== "26982026e7eae10fd92b2bc545f82bda36d9f86a1d53daf1c29b07cb73d16594") {
  throw new Error("Unexpected upstream runtime bundler");
}
// Both adapters must still call the exact shared policy being patched.
for (const [path, digest] of sources) {
  const source = await readFile(path, "utf8");
  if (createHash("sha256").update(source).digest("hex") !== digest
      || source.split("codexShellEnvironmentKeys(").length !== 2) {
    throw new Error(`Unexpected upstream Codex environment policy: ${path}`);
  }

}
const policy = await readFile(policyPath, "utf8");
if (createHash("sha256").update(policy).digest("hex") !== policyDigest
    || policy.split(before).length !== 2) {
  throw new Error("Unexpected upstream shared Codex environment policy");
}
await writeFile(policyPath, policy.replace(before, after));
const { bundleRuntime } = await import(bundlerPath);
await bundleRuntime({
  entry: "/app/server/dist/index.js",
  outdir: "/app/server/dist-runtime",
});
console.log("Rebuilt runtime with patched Codex CLI and ACP scoped GitHub broker capability forwarding.");
