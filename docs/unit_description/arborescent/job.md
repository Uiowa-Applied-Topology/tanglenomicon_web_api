# Unit: Arborescent Job

## Description

Implementation of the Job interface for the arborescent job type.

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


namespace arborescent {

    class mj["arborescent Generation Job"]{
        + List~List~string~~ grafting_lists
        + int TCN
        - connection jobdb
        - List~ObjectId~ _page
        - arborescen_results job_res
        + set_jobdb()
        + get_jobdb()
        + get_lists()
        + store()
        + update_results()
    }
    class mjr["arborescent Job Results"]{
        + List~string~ arbor_list
    }
    class sm["arborescent Submodule"]{
    }

}


mj ..|> aj
mjr ..|> ajr
mj --|> mjr
sm -- mj
sm -- mjr
```

### Get Lists

Retrieve list of arborescent tangles for a job. Next $n$ tangles of a given TCN starting at the
given cursor.

```mermaid
stateDiagram-v2

    state "Get rootstock list." as fr
    state "Get good scion list." as sl
    [*] --> fr
    fr --> sl
    sl --> [*]

```

### Build Job

Build and enqueue jobs from stencils into the jobs database store.

```mermaid
stateDiagram-v2

    state "Get least open stencil." as en
    state "Mark stencil as started" as mas
    state "Walk arborescent tangles to paginate into jobs." as wat
    state "Mark stencil as complete" as msc
    state all_sten_done <<choice>>
    [*] --> en
    en --> mas
    mas --> wat
    wat --> msc
    msc --> all_sten_done
    all_sten_done --> en : Else
    all_sten_done --> [*] : All stencils are done

```

### Load Jobs

Load jobs from the job database store into the active job queue.

```mermaid
stateDiagram-v2

   state "Get number of jobs needed to fill queue" as nj
   state "Get and enqueue n jobs from job database" as gej

   [*]--> nj
   nj --> gej
   gej --> [*]

```

### Startup

Run at startup to initialize the arborescent use case.

```mermaid
stateDiagram-v2

    state "Find open jobs from DB" as ffdb
    state "Count arborescent jobs in queue" as cmjiq
    state "Get and enqueue n jobs from job database" as gej
    [*] --> ffdb
    ffdb --> cmjiq
    cmjiq --> gej
    gej --> [*]

```

### Time Task

Cyclic task used for maintaining the job queue and general stencil state.

```mermaid
stateDiagram-v2
    state "Fill job queue" as fjq
    state open_sten_empy <<choice>>
    state job_col_empty <<choice>>
    state job_queue_empty <<choice>>
    state "Increment ACN" as iacn
    state "Run Build Jobs" as rbj
    [*]--> fjq
    fjq --> job_queue_empty
    job_queue_empty --> [*]: Else
    job_queue_empty --> job_col_empty: Job queue is empty
    job_col_empty --> [*] : Else
    job_col_empty --> open_sten_empy: Job collection is empty
    open_sten_empy --> [*] : Else
    open_sten_empy --> iacn : No open stencils remaining
    iacn --> rbj
    rbj --> [*]
```

### Store

Logic for committing computed data to the arborescent data store.

```mermaid
stateDiagram-v2
    state "Write data to arborescent collection" as wd
    state "Remove job from jobs collection" as rjc
    [*]--> wd
    wd --> rjc
    rjc --> [*]
```

## Unit test description

### Get Lists

#### Positive Tests

##### Get lists for jobs

This tests the behavior of the get lists function.

###### Inputs:

- Mocked arborescent collection.
- Mocked job.

###### Expected Output:

The system is expected to generate the correct rootstock and scion lists.

#### Negative Tests

##### Arborescent collection is empty

This tests the behavior of the get lists function when an empty arborescent collection is provided.

###### Inputs:

- Mocked empty arborescent collection.
- Mocked job.

###### Expected Output:

The system is expected to raise an empty arborescent exception.

### Build Jobs

#### Positive Tests

##### Stencils exist and are processed

This tests the behavior of the build function in the case valid stencils are present.

###### Inputs:

- Mocked stencil collection stencils.
- Mocked arborescent collection.

###### Expected Output:

The system is expected to return and enqueue jobs into the mocked jobdb.

#### Negative Tests

##### Stencil collection is empty

This tests the behavior of the build jobs function when an empty stencil collection is provided.

###### Inputs:

- Mocked empty stencil collection.
- Mocked arborescent collection.
- Mocked job collection.

###### Expected Output:

The system is expected to return and enqueue no data.

##### Arborescent collection is empty

This tests the behavior of the build jobs function when an empty arborescent collection is provided.

###### Inputs:

- Mocked valid stencil collection.
- Mocked arborescent collection.
- Mocked job collection.

###### Expected Output:

The system is expected to raise an empty arborescent exception.

### Load Jobs

#### Positive Tests

##### The requested count is 2

This tests the behavior of the get jobs function when the requested count is 2. This is the normal
positive behaviour.

###### Inputs:

- Mocked stencil collection two stencils.
- Mocked arborescent collection.

###### Expected Output:

The system is expected to return and enqueue jobs into the mocked jobdb.

#### Negative Tests

##### Stencil collection is empty

This tests the behavior of the get jobs function when an empty Stencil collection is provided.

###### Inputs:

- Mocked empty stencil collection.
- Mocked arborescent collection.
- Mocked job collection.

###### Expected Output:

The system is expected to return and enqueue no data.

##### Arborescent collection is empty

This tests the behavior of the get jobs function when an empty arborescent collection is provided.

###### Inputs:

- Mocked valid stencil collection.
- Mocked arborescent collection.

###### Expected Output:

The system is expected to raise an empty arborescent exception.

##### Requested count is 0

This tests the behavior of the get jobs function when the requested count is 0.

###### Inputs:

- Mocked valid stencil collection.
- Mocked arborescent collection.

###### Expected Output:

The system is expected to return and enqueue no data.

### Startup Task

#### Positive Tests

##### Load from collection

Successfully loads open jobs from collection.

###### Inputs:

- Mocked valid stencil collection
- Mocked job collection.

###### Expected Output:

Enqueue jobs with the correct id

#### Negative Tests

I can't think of any at the moment.

### Time Task

#### Positive Tests

##### The job queue is filled

Successfully loads open jobs from collection.

###### Inputs:

- Mocked job collection.

###### Expected Output:

Enqueue jobs with the correct id

##### Increment TCN

Tests program flow that increases completed TCN.

###### Inputs:

- Mocked valid stencil collection
- Empty job queue
- Mocked job collection.

###### Expected Output:

Enqueue new jobs.

#### Negative Tests

I can't think of any at the moment.

### Arborescent Job Store

#### Positive Test

Results are stored to database and stencil is updated

##### Inputs:

- Mocked valid stencil collection with min-new-count - 1 open jobs
- Mocked valid arborescent collection

##### Expected Output:

Enqueue jobs with the correct id

#### Negative Tests

I can't think of any at the moment.
