-- A schema that breaks one rule per object, so a check that misses one is visible.
-- Every violation is annotated with the rule it is meant to trip.

create extension if not exists pgcrypto;

create table workspaces (
    id uuid primary key default gen_random_uuid(),
    name varchar(128) not null
);

create table users (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null references workspaces (id),
    email varchar(128) not null,
    deleted_at timestamptz
);

-- K1: an integer primary key.
create table legacy_notes (
    id bigserial primary key,
    workspace_id uuid not null references workspaces (id),
    body text
);

create table accounts (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null references workspaces (id),

    -- C1: 300 is not a power of two and names no standard.
    nickname varchar(300),

    -- C5: json rather than jsonb.
    settings json,

    -- D2: an _at column that is not an instant.
    reviewed_at date,

    -- D2: an _on column that is not a date.
    signed_on timestamptz,

    -- M1 and M2: a float amount, and no currency column beside it.
    balance_amount double precision,

    -- M3: a currency in the column name.
    fee_usd bigint,

    deleted_at timestamptz
);

-- K5: closed_by is neither users_id nor an allowlisted role.
create table deals (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null references workspaces (id),
    account_id uuid not null references accounts (id),
    closed_by uuid references users (id),
    owner_id uuid references users (id),
    amount_minor bigint not null default 0,
    currency varchar(3) not null default 'KES'
);

-- U1: unique on a soft-deleted table with no partial predicate, so a deleted row
-- holds the address forever.
create unique index users_email_unique on users (email);

-- L5: declared append-only in the config with no trigger to enforce it.
create table audit_logs (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null references workspaces (id),
    action varchar(128) not null,
    created_at timestamptz not null default now()
);

-- T3: the tenant column with row-level security enabled but not forced.
alter table accounts enable row level security;

-- T3: the tenant column with no row-level security at all is deals, left as created.
