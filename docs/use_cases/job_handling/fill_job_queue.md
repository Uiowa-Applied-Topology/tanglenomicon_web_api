# Use case: Fill Job Queue

## Primary actor:

Time

## Goal:

Build jobs to fill queue

## Preconditions:

- Server is initialized
- LTS is connected

## Trigger:

A timed event refills queue with jobs.

## Scenario:

1. Determine how many jobs to build
2. build n jobs
3. enqueue jobs
