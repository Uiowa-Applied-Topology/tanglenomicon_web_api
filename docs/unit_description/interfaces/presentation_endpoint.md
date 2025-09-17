# Unit: presentation api endpoint

## Description

The presentation endpoint interface. To be implemented by each tangle presentation use case.

## Diagrams

```mermaid

classDiagram

namespace Interfaces {
    class age["Presentation Endpoint"]{
        <<interface>>
        + Get_tangles(criteria)
    }
}

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
