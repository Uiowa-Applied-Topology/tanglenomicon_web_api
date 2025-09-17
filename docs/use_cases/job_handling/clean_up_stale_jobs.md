# Use case: Clean up stale jobs

## Primary actor:

Time

## Goal:

Remove stale jobs from queue

## Preconditions:

- Server is initialized
- LTS is connected

## Trigger:

A timed event cleans the queue of stale jobs.

## Scenario:

1. Walks list of jobs
2. sets stale jobs to `new`
