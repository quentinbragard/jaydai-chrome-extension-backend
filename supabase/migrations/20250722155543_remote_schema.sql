alter table "public"."share_invitations" add column "locale" text;

alter table "public"."users_metadata" add column "first_block_created" boolean default false;

alter table "public"."users_metadata" add column "first_template_created" boolean default false;

alter table "public"."users_metadata" add column "first_template_used" boolean default false;

alter table "public"."users_metadata" add column "keyboard_shortcut_used" boolean default false;

alter table "public"."users_metadata" add column "onboarding_dismissed" boolean default false;


