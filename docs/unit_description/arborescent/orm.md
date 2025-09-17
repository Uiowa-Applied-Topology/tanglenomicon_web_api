# Unit Montesinos ORM

## Description

Describes the orm module for the montesinos tangle module.

## Diagrams

```mermaid

classDiagram
    namespace Interfaces {
        class schema["Montesinos Schema"] {
            <<struct>>
            + string _id
            + string parent_stencil
            + int crossing_num
        }

        class schema_sten_job["Stencil Job Schema"] {
            <<struct>>
            + string job_id
            + List[int] cursor
        }

        class schema_sten["Stencil Schema"] {
            <<struct>>
            + ObjectId _id
            + List[int] stencil_array
            + string str_rep
            + int crossing_num
            + List[int] head
            + int state
            + List[Stencil Job Schema] open_jobs
        }

        class age["ORM"] {
            <<interface>>
            + get_stencil_collection()
            + get_montesinos_collection()
        }
    }
```

## Unit test description

No testing required for data only classes.
