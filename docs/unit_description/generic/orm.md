# Unit: Generic ORM

## Description

Describes the orm module for the generic tangle module.

## Diagrams

```mermaid

classDiagram
    namespace Interfaces {
        class schema["Generic Schema"] {
            <<struct>>
            + string _id
        }

        class age["ORM"] {
            <<interface>>
            + get_rational_collection()
        }
    }
```

## Unit test description

Object defines an abstract interface no unit testing.
