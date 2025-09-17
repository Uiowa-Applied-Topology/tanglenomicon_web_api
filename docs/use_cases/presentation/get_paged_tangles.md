# Use case: Get paged tangles

## Primary actor:

Client

## Goal:

Get a page of tangles from the database

## Preconditions:

- Server is initialized
- LTS is connected

## Trigger:

A client requests the tangle table

## Scenario:

1. Client makes a `get` request to the server
2. Server replies with a page of tangle data
