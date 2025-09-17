# Unit: ORM interface

## Description

Describes the generic orm needed by every module.

## Diagrams

```mermaid

classDiagram

namespace Interfaces {

    class schema["Schema"]{
        <<struct>>
    }

    class age["ORM"]{
        <<interface>>
        + get_*collection*()
    }

}
```

## Unit test description

Object defines an abstract interface no unit testing.
