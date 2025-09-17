# Unit: Security Model

## Description

This class defines the secturity model for the tanglenomicon api. It's mostly wholsale lifted from
[FastAPI docs](https://web.archive.org/web/20240324095137/https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)

## Diagrams

```mermaid

classDiagram

    class tk["Token"]{ }
    class tkd["Token Data"]{ }
    class user["User"]{ }
    class user_db["User In DB"]{ }
    class user_db["User In DB"]{ }
    class security_model["Security Model"]{

        - CryptContext pwd_context
        - OAuth2PasswordBearer oauth2_scheme
        - APIRouter router
        - verify_password()
        - get_password_hash()
        - get_user()
        + authenticate_user()
        + get_collection()
        + create_access_token()
        + auth_current_user()
        + get_current_user()
        + get_current_active_user()
        + read_users_me()
        + login_for_access_token()
    }
```

## Function flow

### clean_stale_jobs

```mermaid


stateDiagram-v2

    [*] --> for
    state "for each job" as for {
    state if_state <<choice>>
    state "Get State" as staleChk
    state "Set state to new" as setNew
    [*] --> staleChk
     staleChk --> if_state
    if_state --> setNew: if is Stale
    if_state --> [*] : if is not Stale
    setNew --> [*]
    }
    for   --> [*]
```

### clean_complete_jobs

```mermaid


stateDiagram-v2

    [*] --> for
    state "for each job" as for {
    state if_state <<choice>>
    state "Get State" as staleChk
    state "Commit to storage" as setNew
    [*] --> staleChk
     staleChk --> if_state
    if_state --> setNew: if is complete
    if_state --> [*] : if is not complete
    setNew --> [*]
    }
    for   --> [*]
```

### add_new_jobs

```mermaid


stateDiagram-v2

    state if_state <<choice>>
    state "Get queue fill" as staleChk
    state "Build job from storage" as setNew
    [*] --> staleChk
    staleChk --> if_state
    if_state --> setNew: if is underfilled
    if_state --> [*] : if is not underfilled
    setNew --> staleChk
```

### mark_job_complete

```mermaid


stateDiagram-v2
    state if_state <<choice>>

    state "Get job state" as getjs
    state "Update job payload" as updateJob
    state "Set state of job to complete" as setNew

    [*] --> getjs
    getjs --> if_state
    if_state --> updateJob : if is pending
    if_state --> [*] : if is not pending
    updateJob --> setNew
    setNew --> [*]
```

### get_next_job

```mermaid


stateDiagram-v2
    state "Get lowest index new job of 'type'" as staleChk

    [*] --> staleChk
    staleChk --> [*]
```

## Unit test description

These tests will be run manually. Since this is lifted from the fastAPI guide we trust it, this is
perhaps a dubious thing to do.
