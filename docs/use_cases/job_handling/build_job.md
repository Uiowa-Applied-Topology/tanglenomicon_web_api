# Use case: Build Job

## Primary actor:

N/A

## Goal:

Construct a job to be distributed

## Preconditions:

- Server is initialized
- LTS is connected

## Trigger:

An upstream actor requests the initialization of a new job.

## Scenario:

1. Reads record sets
2. Formats job for distribution
3. enqueues job
4. marks job as `new`
