# Unit: Job

## Description

The interface that describes the minimum members of the job class.

## Diagrams

```mermaid

classDiagram

namespace Interfaces {

    class js["Job States"]{
        <<Enum>>
        new = 0
        pending = 1
        complete = 2
    }

    class aj["Generation Job"]{
        <<interface>>
        + string id
        + time last_modified
        + job_state current_state
        + string client_id
        - job_results results
        + store()
        + update_results()
    }
    class ajr["Job Results"]{
        <<interface>>
        + string id
        + string client_id
    }
    class cr["Confirm Job Reciept"]{
        <<interface>>
        + bool accepted
    }
    class sm["Job"]{
        <<module>>
        + get_jobs()
        + startup_task()
    }

}

aj --> js
aj --> ajr
cr ..> ajr
sm -- aj
sm -- ajr
sm -- cr
sm -- js
```

## Unit test description

Object defines an abstract interface no unit testing.
