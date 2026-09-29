# Research

Decision: extend the existing normalizer. It already has reader credentials, Mylar catalog access and shared writer coordination. A separate Mylar HTTP notifier would duplicate credential and retry ownership. Native processing completion alone is insufficient when conversion/tagging follow-up is pending.

Decision: batch five new ready additions, flush tails after five minutes, and pace requests at two minutes. This bounds added scans without changing scheduled scans. No claim is made that this threshold is benchmark-optimal for every filesystem.

Komga exposes library roots in [GET libraries](https://komga.org/docs/openapi/get-libraries/) and accepts administrator [library scan requests](https://komga.org/docs/openapi/library-scan/). The existing Reader client already uses these endpoints. Keep existing conversion recovery scans independent because they are needed to complete reader upgrades.

Decision: first activation baselines catalog paths, then only new pending archives are inspected. Files with unresolved tagging or conversion receipts wait. A stable readable tagged CBZ is a readiness signal, not a new decompression/integrity audit. No unresolved design questions remain.
