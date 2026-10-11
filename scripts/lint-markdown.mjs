#!/usr/bin/env node
// Literal file paths only: no glob/brace parser in the Markdown lint toolchain.
import { lint, readConfig } from "markdownlint/promise";

let configFile = ".markdownlint.json";
const files = [];
const args = process.argv.slice(2);
let literal = false;
for (let index = 0; index < args.length; index += 1) {
  const argument = args[index];
  if (!literal && argument === "--") {
    literal = true;
  } else if (!literal && argument === "--config") {
    index += 1;
    if (!args[index]) {
      throw new Error("--config requires a file path");
    }
    configFile = args[index];
  } else if (!literal && argument.startsWith("--")) {
    throw new Error(`Unsupported option: ${argument}`);
  } else {
    files.push(argument);
  }
}
if (files.length === 0) {
  console.log("Usage: node scripts/lint-markdown.mjs [--config FILE] [--] FILE ...");
} else {
  const config = await readConfig(configFile);
  const results = await lint({ files, config });
  let errors = 0;
  for (const [file, issues] of Object.entries(results)) {
    for (const issue of issues) {
      const severity = issue.severity ?? "error";
      console.error(`${file}:${issue.lineNumber} ${issue.ruleNames.join("/")} ${issue.ruleDescription}${issue.errorDetail ? ` [${issue.errorDetail}]` : ""}`);
      if (severity === "error") {
        errors += 1;
      }
    }
  }
  if (errors > 0) {
    process.exitCode = 1;
  }
}
