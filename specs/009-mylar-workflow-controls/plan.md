# Implementation Plan: Mylar workflow controls

**Branch**: `feat/mylar-workflow-controls` | **Date**: 2026-09-24 | **Spec**: [spec.md](spec.md)

## Summary

Add persistent activity and operator controls inside the existing Mylar image.
Use native serialized search/download boundaries, preserve source files, and extend
the optional maintenance worker for guided import submissions. Deliver both tested
GHCR images through a reviewed PR and verified live rollout.

## Technical Context

Python in pinned Mylar/normalizer images, SQLite, CherryPy sessions, Mako and the
existing jQuery interface. No additional runtime dependency or service. Durable
workflow state lives in Mylar's existing private config volume; worker proposals
live in its existing state directory. Tests use temporary databases, fake clocks,
native source fixtures, disposable archives and isolated browser pages. Linux amd64
is the verified deployment target. Poll responses and reports are bounded; no
whole-library scan is added to a search or web request.

## Constitution Check

Before and after design: all five principles pass. Existing mounts, network scopes,
credentials, ports and privileges suffice. Code, state ownership, preparation
messages, examples, metadata and documentation will describe the same contract.
Generated catalog/topology/site surfaces will be regenerated where affected.
Runtime secrets stay outside Git. Deployment requires a fresh application-consistent
backup and isolated restore, data comparison, rollback on failure, and cleanup only
after success. No database deletion or volume removal is part of deployment.

## Project Structure

- `stacks/mylar3/config/workflow_store.py`: bounded events, reservations, policies,
  guided commands and aliases in a private workflow database.
- `workflow.py`, `patch_workflow.py`, `workflow.html`: native integration,
  authenticated reads/actions and linked Activity interface.
- `queue_control.py`: atomic DDL claim boundary and reservation checks.
- `cooldown_health.py`, `health.py`, `reliability.py`: expected waits and stall policy.
- `stacks/komga/normalizer/guided_match.py`: private proposals, candidate evidence,
  selected import execution and exact aliases, using existing recovery receipts.
- Native patch installer, image verification and tests in each image context.
- `specs/009-mylar-workflow-controls/`: specification, research, contracts and evidence.

## Implementation order and ownership

The root agent owns integration, Git, workflow state, Mylar native hooks and UI.
After foundational contracts, independent work units may implement cooldown health
and worker-side guided matching in disjoint files. Shared installers, documentation,
metadata and browser integration remain with the root agent. Each unit must return
changed paths, fixture evidence and verification gaps before integration.

Build shared state first, then activity, handoff/health, matching, and intake. Tests
bracket each stateful feature. Complete all five stories before delivery. Observers
must not crash native workers; uncertain side effects remain reserved for review.
