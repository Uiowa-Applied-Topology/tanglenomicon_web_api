# Unit: Montesinos job

## Description

Implementation of the Job interface for the Montesinos job type.

### Strategy

Info on abstract strategy can be found in the core project.

## Diagrams

### Class diagram

```mermaid

classDiagram

namespace Interfaces {

    class aj["Job"]{
        <<interface>>
    }
    class ajr["Job Results"]{
        <<interface>>
    }

}


namespace montesinos {

    class mj["Montesinos Generation Job"]{
        + List~List~string~~ rat_list
        - mont_results job_res
    }
    class mjr["Montesinos Job Results"]{
        + List~string~ mont_list
    }
    class sm["Montesinos Submodule"]{
    }

}


mj ..|> aj
mjr ..|> ajr
mj --|> mjr
sm -- mj
sm -- mjr
```

### Get Jobs

Retrieve $n$ jobs for $n\in \Z^+$

```mermaid
stateDiagram-v2


    state "i from 0 to count" as fr {
        state "Build Job" as bj
        state "Move Head" as mh
        [*] --> bj
        bj --> mh
        mh --> [*]
    }

    [*] --> fr
    fr --> [*]

```

#### Build Job

```mermaid
stateDiagram-v2

    state "Enqueue Job" as en
    state "Entry k in stencil" as fr {
        state "Get rational page k" as bj
        [*] --> bj
        bj --> [*]
    }

    [*] --> fr
    fr --> en
    en --> [*]

```

#### Move Head

```mermaid
stateDiagram-v2

    state if_check_headroom <<choice>>
    state "Set overflow as true" as so
    state "Return headroom" as rh
    state "Return no headroom" as rnh
    state "Entry k in stencil" as fr {
        state "Set head entry to 0" as heo
        state "Set overflow as true" as sot
        state "Set overflow as false" as sof
        state "Increment head entry at k" as ihe
        state if_state <<choice>>
        state if_should_overflow <<choice>>
        [*] --> if_state
        if_state --> sof: if overflow
        sof --> ihe
        ihe --> if_should_overflow
        if_should_overflow --> sot: if stencil[k]==head[k]
        sot --> heo
        heo --> [*]
        if_should_overflow --> [*]: if stencil[k]!=head[k]
        if_state --> break : if not overflow
        break --> [*]
    }

    [*] --> so
    so --> fr
    fr --> if_check_headroom
    if_check_headroom --> rnh: if overflow
    if_check_headroom --> rh: if not overflow
    rh --> [*]
    rnh --> [*]

```

### Startup

```mermaid
stateDiagram-v2

    state "Find open jobs from DB" as ffdb
    state "Count Montesinos jobs in queue" as cmjiq
    state "Build enough additional jobs to full queue" as baj
    state "For each job" as fr {
        state "Build job" as bj
        [*] --> bj
        bj --> [*]
    }

    [*] --> ffdb
    ffdb --> fr
    fr --> cmjiq
    cmjiq --> baj
    baj --> [*]

```

### Store

## Unit test description

### Get Jobs

#### Positive Tests

##### Requested count is 2

This tests the behavior of the get jobs function when the requested count is 2. This is the normal
positive behaviour.

###### Inputs:

- Mocked stencil collection two stencils one with no headroom.
- Mocked valid rational collection.
- Count set to 2.

###### Expected Output:

The system is expected to return and enqueue 2 jobs. Stencils updated with open jobs

#### Negative Tests

##### Stencil collection is empty

This tests the behavior of the get jobs function when an empty Stencil collection is provided.

###### Inputs:

- Mocked empty stencil collection.
- Mocked valid rational collection.
- Count set to 2.

###### Expected Output:

The system is expected to return and enqueue no data.

##### Rational collection is empty

This tests the behavior of the get jobs function when an empty rational collection is provided.

###### Inputs:

- Mocked valid stencil collection.
- Mocked empty rational collection.
- Count set to 2.

###### Expected Output:

The system is expected to raise an empty rational exception.

##### Requested count is 0

This tests the behavior of the get jobs function when the requested count is 0.

###### Inputs:

- Mocked valid stencil collection.
- Mocked valid rational collection.
- Count set to 0.

###### Expected Output:

The system is expected to return and enqueue no data.

### Startup Task

#### Positive Tests

##### Load from collection

Successfully loads open jobs from collection.

###### Inputs:

- Mocked valid stencil collection with min-new-count - 1 open jobs
- Mocked valid rational collection

###### Expected Output:

Enqueue jobs with correct id

##### Collection has no open jobs

Collection has no open jobs so new jobs are created.

###### Inputs:

- Mocked valid stencil collection with all stencils in new state
- Mocked valid rational collection
- Empty job queue

###### Expected Output:

Enqueue new jobs.

#### Negative Tests

I can't think of any at the moment.

### MontesinosJob.Store

#### Positive Test

Results are stored to database and stencil is updated

##### Inputs:

- Mocked valid stencil collection with min-new-count - 1 open jobs
- Mocked valid rational collection

##### Expected Output:

Enqueue jobs with correct id

#### Negative Tests

I can't think of any at the moment.
