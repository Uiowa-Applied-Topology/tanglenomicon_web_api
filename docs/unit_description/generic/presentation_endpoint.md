# Unit: Montesinos api presentation endpoint

## Description

Implementation of the presentation endpoint interface for the generic tangle use case.

## Diagrams

```mermaid

classDiagram

namespace Interfaces {
    class age["Presentation Endpoint"]{
        <<interface>>
    }
}


namespace Generic {
    class mge["Generic Presentation Endpoint"]{
        + get_tangle_by_id()
    }


}


mge ..|> age

```

### get_tangle_by_id

```mermaid
stateDiagram-v2
    state "Get tangle from db" as vj
    [*] --> vj
    vj  -->  [*]

```

### get_tangles

Retrieves a page of tangles.

```mermaid
stateDiagram-v2
    state "Get tangles from db" as vj
    [*] --> vj
    vj  -->  [*]

```

## Unit test description

### get_tangles

#### Positive Test

Retrieve a page of tangles.

###### Inputs:

Populated tangle database.

###### Expected Output:

A page of tangles are returned.

#### Negative Tests

##### Empty table

Attempt to retrieve a tangle from an empty tangle.

###### Inputs:

Empty tangle.

###### Expected Output:

Empty list is returned.

##### Zero size request

Attempt to retrieve no tangles from the tangle table.

###### Inputs:

Populated tangle database.

###### Expected Output:

Empty list is returned.

### get_tangle_by_id

#### Positive Test

Retrieve a tangle from the database.

###### Inputs:

Populated tangle database.

###### Expected Output:

A tangle is returned.

#### Negative Tests

##### Empty table

Attempt to retrieve a tangle from an empty tangle.

###### Inputs:

Empty tangle.

###### Expected Output:

Not found error is returned.
