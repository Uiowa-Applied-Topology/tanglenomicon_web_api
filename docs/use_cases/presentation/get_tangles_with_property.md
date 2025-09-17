# Use case: Get tangles with property

## Primary actor:

Client

## Goal:

Get tangles from the database with a specific property.

Ex: all tangles with crossing number 4

## Preconditions:

- Server is initialized
- LTS is connected

## Trigger:

A client requests a page of tangles with a specific criteria

## Scenario:

1. Client makes a `get` request to the server
2. Server replies with the data for tangles with specific criteria
