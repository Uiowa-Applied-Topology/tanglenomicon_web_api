# Use case: Get Montesinos Job

## Primary actor:

Client

## Goal:

Passes a new job to a client.

## Preconditions:

- Client and server are on the same network.
- Client is on known runner list.

## Trigger:

Client asks for a new montesinos job.

## Scenario:

1. Client makes a `get` job request to the server
2. Server verifies client ID
3. Server distributes job to client
