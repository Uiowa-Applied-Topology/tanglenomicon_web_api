# Use case: Clean up complete jobs

## Primary actor:

Time

## Goal:

Remove completed jobs from queue

## Preconditions:

- Server is initialized
- LTS is connected

## Trigger:

A timed event cleans the queue of completed jobs.

## Scenario:

1. Walks list of jobs
2. Sends records to LTS
3. Sends progress update to LTS
