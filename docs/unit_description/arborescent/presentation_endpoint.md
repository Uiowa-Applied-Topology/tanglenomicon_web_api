# Unit: Montesinos api presentation endpoint

## Description

Implementation of the presentation endpoint interface for the montesinos tangle use case.

## Diagrams

```mermaid

classDiagram
    namespace Interfaces {
        class age["Presentation Endpoint"] {
            <<interface>>
        }
    }

    namespace Generic {
        class mge["Montesinos Presentation Endpoint"] {
        }
    }

    mge ..|> age

```

### get_tangles

```mermaid
stateDiagram-v2
    state "Get tangles from db" as vj
    [*] --> vj
    vj  -->  [*]

```

## Unit test description

### get_tangle_by_id

#### Positive Test

##### test

[//]: # "@@@ TODO: "

###### Inputs:

[//]: # "@@@ TODO: "

###### Expected Output:

[//]: # "@@@ TODO: "

#### Negative Tests

##### test

[//]: # "@@@ TODO: "

##### Inputs:

[//]: # "@@@ TODO: "

##### Expected Output:

[//]: # "@@@ TODO: "
