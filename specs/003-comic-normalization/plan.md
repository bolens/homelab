# Implementation plan: comic normalization

**Date**: 2026-09-23

**Spec**: [spec.md](spec.md)

## Summary

Add an optional Komga Compose worker using the digest-pinned published
archiving-utils image. Reuse its verified comic-to-cbz operation, with a narrow
adapter for stable-file discovery, persistent receipts, preserved originals,
and library refresh. Do not duplicate archive codecs.

## Technical context

- Python standard library, archiving-utils, Komga book import/upgrade API,
  and read-only Mylar series lookup with its recheckFiles API.
- One non-root worker, read-only container root, no exposed ports or Docker socket.
- Writable comic/manga mounts, separate persistent state/originals directory,
  and read-only integration configuration. Komga needs writable library mounts
  to execute supported book upgrades and a read-only view of prepared CBZs.
- Preserve book metadata and progress through Komga's upgrade operation, recording replacement IDs. Verify this contract
  against upstream implementation and an isolated fixture before live use.
- Poll stable files with one conversion at a time. Keep API retries independent
  of archive conversion so a failed refresh does not rewrite a comic.

## Constitution check

Portable examples use placeholder paths and credentials. Optional override activation
is explicit. Mount write access and service networks are documented contract changes.
Preparation must not create missing media roots or deploy containers. Live work is
explicitly authorized in this conversation and requires verified backups.

## Source ownership

- `stacks/komga/normalizer/`: worker, integration config example, regression tests.
- Komga Compose, environment example, preparation, metadata, README: deployment contract.
- Mylar README: conversion and file-recheck integration.
- Ingress remains unchanged: the worker exposes no HTTP service.

## Validation and deployment

Test real CB7, CBT, compressed TAR, and mislabeled archives with preserved member
hashes. Test collisions, unstable inputs, failures, and interrupted API operations.
Run focused Compose/metadata checks and `make validate`.

Before live changes, verify state backups by isolated restore and verify recoverable
original media. Preserve all existing records and reader progress. Roll back on data
loss or corruption; retain backups if verification is inconclusive. Delete only
operation-specific temporary backups after successful verification.
