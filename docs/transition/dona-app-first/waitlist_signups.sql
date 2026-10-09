-- docs/transition/dona-app-first/waitlist_signups.sql
-- Lista de espera de usadona.com ("plazas completas"). Tabla aditiva en el
-- proyecto Supabase "Dona", aplicada con la migración de Supabase
-- "create_waitlist_signups". Fuera de Alembic a propósito: la escribe solo
-- la landing (POST /api/waitlist) con una credencial de servidor.
-- RLS activo SIN políticas: anon y authenticated no leen ni escriben;
-- service_role (servidor) la usa saltándose RLS.

create table if not exists public.waitlist_signups (
  id          bigint generated always as identity primary key,
  email       text not null unique check (email = lower(email) and char_length(email) <= 254),
  phone       text null check (phone is null or phone ~ '^\+?[0-9]{7,15}$'),
  source      text not null default 'usadona-pausa',
  created_at  timestamptz not null default now()
);

alter table public.waitlist_signups enable row level security;
revoke all on table public.waitlist_signups from anon, authenticated;

comment on table public.waitlist_signups is
  'Lista de espera usadona.com (plazas completas). Escribe solo la landing vía service_role.';
