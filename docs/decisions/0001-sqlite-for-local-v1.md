# ADR 0001: SQLite for the local version

## Status

Accepted.

## Context

Version 1 runs on one local machine, permits one active interview, and stores large artifacts on the
filesystem. Persistent metadata consists of sessions, ordered state transitions, consent timestamps,
and failure details.

## Decision

Use SQLite through SQLAlchemy and Alembic.

## Why not MongoDB

MongoDB would add another service, network dependency, startup condition, and credential surface to
the demo. Flexible document storage does not help because audio and transcript files remain outside
the database, while the metadata benefits from transactions and explicit constraints.

## Upgrade path

The domain depends on a repository protocol. A multi-instance deployment can replace SQLite with
PostgreSQL without changing interview orchestration. MongoDB remains reasonable if future needs are
dominated by high-volume, schema-variable event ingestion, but that is not a current requirement.

