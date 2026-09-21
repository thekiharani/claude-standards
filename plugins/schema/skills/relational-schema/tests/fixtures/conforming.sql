-- A schema that follows every checkable rule. It must produce zero failures, because a checker
-- that cries wolf on a correct schema is one somebody adds --skip to within a week.

create table workspaces (
    id uuid primary key default uuidv7(),
    name varchar(128) not null,
    deleted_at timestamptz
);

create table users (
    id uuid primary key default uuidv7(),
    workspace_id uuid not null references workspaces (id) on delete cascade,
    email varchar(128) not null,
    full_name varchar(128) not null,
    joined_on date,
    last_seen_at timestamptz,
    deleted_at timestamptz
);

create table accounts (
    id uuid primary key default uuidv7(),
    workspace_id uuid not null references workspaces (id) on delete cascade,
    owner_id uuid references users (id),
    name varchar(128) not null,
    metadata jsonb not null default '{}',
    balance_minor bigint not null default 0,
    currency varchar(3) not null default 'KES',
    deleted_at timestamptz,
    constraint accounts_balance_minor_bounds
        check (balance_minor <= 9000000000000000 and balance_minor >= -9000000000000000)
);

create table audit_logs (
    id uuid primary key default uuidv7(),
    workspace_id uuid not null references workspaces (id) on delete cascade,
    actor_id uuid references users (id),
    action varchar(128) not null,
    created_at timestamptz not null default now()
);

-- T6: a parent carries unique (tenant, id) so a child can re-declare its key as a composite,
-- which makes a cross-tenant reference unrepresentable rather than merely prevented by policy.
alter table accounts add constraint accounts_tenant_unique unique (workspace_id, id);

create table account_notes (
    id uuid primary key default uuidv7(),
    workspace_id uuid not null references workspaces (id) on delete cascade,
    account_id uuid not null,
    body text,
    constraint account_notes_account_tenant_fk
        foreign key (workspace_id, account_id) references accounts (workspace_id, id)
        on delete cascade
);

-- T7 and G7: every index leads with the tenant column, which also covers the foreign keys.
create index users_workspace_idx on users (workspace_id, id);
create index accounts_workspace_idx on accounts (workspace_id, id);
create index accounts_owner_idx on accounts (workspace_id, owner_id);
create index audit_logs_workspace_idx on audit_logs (workspace_id, id);
create index audit_logs_actor_idx on audit_logs (workspace_id, actor_id);
create index account_notes_workspace_idx on account_notes (workspace_id, account_id);
create index users_tenant_idx on users (workspace_id, email);

-- U1: unique on a soft-deleted table, scoped so a deleted row releases the key.
create unique index users_email_unique on users (workspace_id, email) where deleted_at is null;

-- L/B: append-only enforced where it counts, not by convention.
create function reject_mutation() returns trigger as $$
begin
    raise exception 'Table % is append-only', tg_table_name using errcode = 'restrict_violation';
end;
$$ language plpgsql;

create trigger audit_logs_append_only
    before update or delete on audit_logs
    for each row execute function reject_mutation();

-- T3: enabled and forced, or the owner is exempt.
do $$
declare t text;
begin
    foreach t in array array['workspaces', 'users', 'accounts', 'audit_logs', 'account_notes'] loop
        execute format('alter table %I enable row level security', t);
        execute format('alter table %I force row level security', t);
    end loop;
end $$;
