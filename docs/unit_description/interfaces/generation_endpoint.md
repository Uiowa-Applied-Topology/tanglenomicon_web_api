# Unit: generation api endpoint

## Description

The generation endpoint interface. To be implemented by each generation use case.

## Diagrams

```mermaid

classDiagram

namespace Interfaces {
    class age["Generation Endpoint"]{
        <<interface>>
        + Get()
        + Post()
    }
}

```

## Unit test description

Object defines an abstract interface no unit testing.
