# ADR 0001: Separate public repository

- Status: accepted

## Decision

Build the cloud/API edition in a new repository with a clean initial history. Treat the private
local-first application as read-only reference and manually port only generic behavior.

## Why

The source repository explicitly forbids model API calls and contains private product assumptions,
machine-specific documentation, and personal course catalog metadata. A clean repository prevents
accidental history disclosure and lets the cloud edition enforce different trust boundaries.

## Consequences

Fixes are not automatically shared. Generic algorithms and schemas must be reviewed and ported
deliberately, which is preferable to coupling private and public release processes.

