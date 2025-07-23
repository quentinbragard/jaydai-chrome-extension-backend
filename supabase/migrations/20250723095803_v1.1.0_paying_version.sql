create table "public"."share_invitations" (
    "id" uuid not null default gen_random_uuid(),
    "user_id" uuid not null,
    "inviter_email" text not null,
    "inviter_name" text not null,
    "friend_email" text,
    "invitation_type" text not null,
    "status" text not null default 'pending'::text,
    "created_at" timestamp with time zone default now(),
    "updated_at" timestamp with time zone default now(),
    "sent_at" timestamp with time zone,
    "metadata" jsonb default '{}'::jsonb,
    "locale" text
);


alter table "public"."share_invitations" enable row level security;

create table "public"."stripe_subscriptions" (
    "id" uuid not null default gen_random_uuid(),
    "user_id" uuid not null,
    "stripe_customer_id" text not null,
    "stripe_subscription_id" text not null,
    "stripe_price_id" text not null,
    "stripe_product_id" text not null,
    "status" text not null,
    "current_period_start" timestamp with time zone,
    "current_period_end" timestamp with time zone,
    "cancel_at_period_end" boolean default false,
    "cancelled_at" timestamp with time zone,
    "trial_start" timestamp with time zone,
    "trial_end" timestamp with time zone,
    "created_at" timestamp with time zone default now(),
    "updated_at" timestamp with time zone default now(),
    "metadata" jsonb default '{}'::jsonb
);


create table "public"."stripe_webhook_events" (
    "id" uuid not null default gen_random_uuid(),
    "stripe_event_id" character varying(255) not null,
    "event_type" character varying(100) not null,
    "event_data" jsonb not null,
    "processed" boolean default false,
    "created_at" timestamp with time zone default now(),
    "processed_at" timestamp with time zone
);


alter table "public"."stripe_webhook_events" enable row level security;

create table "public"."subscription_audit_log" (
    "id" uuid not null default gen_random_uuid(),
    "user_id" uuid not null,
    "old_status" text,
    "new_status" text,
    "old_plan" text,
    "new_plan" text,
    "stripe_event_id" text,
    "changed_by" text,
    "changed_at" timestamp with time zone default now(),
    "metadata" jsonb
);


alter table "public"."subscription_audit_log" enable row level security;

alter table "public"."prompt_templates" add column "is_free" boolean default true;

alter table "public"."users_metadata" add column "data_collection" boolean default true;

alter table "public"."users_metadata" add column "first_block_created" boolean default false;

alter table "public"."users_metadata" add column "first_template_created" boolean default false;

alter table "public"."users_metadata" add column "first_template_used" boolean default false;

alter table "public"."users_metadata" add column "keyboard_shortcut_used" boolean default false;

alter table "public"."users_metadata" add column "onboarding_dismissed" boolean default false;

alter table "public"."users_metadata" add column "stripe_customer_id" character varying(255);

alter table "public"."users_metadata" add column "stripe_subscription_id" character varying(255);

alter table "public"."users_metadata" add column "subscription_cancel_at_period_end" boolean default false;

alter table "public"."users_metadata" add column "subscription_current_period_end" timestamp with time zone;

alter table "public"."users_metadata" add column "subscription_plan" character varying(50);

alter table "public"."users_metadata" add column "subscription_status" character varying(50) default 'free'::character varying;

CREATE INDEX idx_share_invitations_status ON public.share_invitations USING btree (status);

CREATE INDEX idx_share_invitations_type ON public.share_invitations USING btree (invitation_type);

CREATE INDEX idx_share_invitations_user_id ON public.share_invitations USING btree (user_id);

CREATE INDEX idx_stripe_webhook_events_processed ON public.stripe_webhook_events USING btree (processed);

CREATE INDEX idx_stripe_webhook_events_stripe_id ON public.stripe_webhook_events USING btree (stripe_event_id);

CREATE INDEX idx_stripe_webhook_events_type ON public.stripe_webhook_events USING btree (event_type);

CREATE INDEX idx_users_metadata_stripe_customer ON public.users_metadata USING btree (stripe_customer_id);

CREATE INDEX idx_users_metadata_stripe_subscription ON public.users_metadata USING btree (stripe_subscription_id);

CREATE INDEX idx_users_metadata_subscription_status ON public.users_metadata USING btree (subscription_status);

CREATE UNIQUE INDEX share_invitations_pkey ON public.share_invitations USING btree (id);

CREATE UNIQUE INDEX stripe_subscriptions_pkey ON public.stripe_subscriptions USING btree (id);

CREATE UNIQUE INDEX stripe_subscriptions_stripe_subscription_id_key ON public.stripe_subscriptions USING btree (stripe_subscription_id);

CREATE UNIQUE INDEX stripe_webhook_events_pkey ON public.stripe_webhook_events USING btree (id);

CREATE UNIQUE INDEX stripe_webhook_events_stripe_event_id_key ON public.stripe_webhook_events USING btree (stripe_event_id);

CREATE UNIQUE INDEX subscription_audit_log_pkey ON public.subscription_audit_log USING btree (id);

alter table "public"."share_invitations" add constraint "share_invitations_pkey" PRIMARY KEY using index "share_invitations_pkey";

alter table "public"."stripe_subscriptions" add constraint "stripe_subscriptions_pkey" PRIMARY KEY using index "stripe_subscriptions_pkey";

alter table "public"."stripe_webhook_events" add constraint "stripe_webhook_events_pkey" PRIMARY KEY using index "stripe_webhook_events_pkey";

alter table "public"."subscription_audit_log" add constraint "subscription_audit_log_pkey" PRIMARY KEY using index "subscription_audit_log_pkey";

alter table "public"."share_invitations" add constraint "share_invitations_invitation_type_check" CHECK ((invitation_type = ANY (ARRAY['friend'::text, 'team'::text, 'referral'::text]))) not valid;

alter table "public"."share_invitations" validate constraint "share_invitations_invitation_type_check";

alter table "public"."share_invitations" add constraint "share_invitations_status_check" CHECK ((status = ANY (ARRAY['pending'::text, 'sent'::text, 'accepted'::text, 'declined'::text, 'failed'::text]))) not valid;

alter table "public"."share_invitations" validate constraint "share_invitations_status_check";

alter table "public"."share_invitations" add constraint "valid_friend_invitation" CHECK ((((invitation_type = 'friend'::text) AND (friend_email IS NOT NULL)) OR ((invitation_type = ANY (ARRAY['team'::text, 'referral'::text])) AND (friend_email IS NULL)))) not valid;

alter table "public"."share_invitations" validate constraint "valid_friend_invitation";

alter table "public"."stripe_subscriptions" add constraint "stripe_subscriptions_stripe_subscription_id_key" UNIQUE using index "stripe_subscriptions_stripe_subscription_id_key";

alter table "public"."stripe_subscriptions" add constraint "stripe_subscriptions_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE not valid;

alter table "public"."stripe_subscriptions" validate constraint "stripe_subscriptions_user_id_fkey";

alter table "public"."stripe_webhook_events" add constraint "stripe_webhook_events_stripe_event_id_key" UNIQUE using index "stripe_webhook_events_stripe_event_id_key";

set check_function_bodies = off;

CREATE OR REPLACE FUNCTION public.get_user_subscription(user_uuid uuid)
 RETURNS TABLE(is_active boolean, plan_id text, current_period_end timestamp with time zone, cancel_at_period_end boolean, stripe_customer_id text, stripe_subscription_id text)
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
    RETURN QUERY
    SELECT 
        CASE 
            WHEN um.subscription_status IN ('active', 'trialing') THEN true 
            ELSE false 
        END as is_active,
        um.subscription_plan as plan_id,
        um.subscription_current_period_end as current_period_end,
        COALESCE(um.subscription_cancel_at_period_end, false) as cancel_at_period_end,
        um.stripe_customer_id as stripe_customer_id,
        um.stripe_subscription_id as stripe_subscription_id
    FROM users_metadata um
    WHERE um.user_id = user_uuid;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.get_user_subscription_status(check_user_id uuid DEFAULT NULL::uuid)
 RETURNS TABLE(user_id uuid, is_active boolean, plan_id text, current_period_end timestamp with time zone, cancel_at_period_end boolean, has_stripe_customer boolean)
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    target_user_id UUID;
BEGIN
    -- If no user_id provided, use the authenticated user
    IF check_user_id IS NULL THEN
        target_user_id := auth.uid();
    ELSE
        target_user_id := check_user_id;
    END IF;
    
    -- Security check: users can only access their own data
    IF (current_setting('role') != 'service_role' AND auth.uid() != target_user_id) THEN
        RAISE EXCEPTION 'Access denied: can only view your own subscription status';
    END IF;
    
    RETURN QUERY
    SELECT 
        um.user_id,
        CASE 
            WHEN um.subscription_status IN ('active', 'trialing') THEN true 
            ELSE false 
        END as is_active,
        um.subscription_plan as plan_id,
        um.subscription_current_period_end as current_period_end,
        COALESCE(um.subscription_cancel_at_period_end, false) as cancel_at_period_end,
        CASE 
            WHEN um.stripe_customer_id IS NOT NULL THEN true 
            ELSE false 
        END as has_stripe_customer
    FROM users_metadata um
    WHERE um.user_id = target_user_id;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.has_active_subscription(user_uuid uuid)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM users_metadata 
        WHERE user_id = user_uuid 
        AND subscription_status IN ('active', 'trialing')
    );
END;
$function$
;

CREATE OR REPLACE FUNCTION public.log_subscription_changes()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
    -- Only log if subscription-related fields changed
    IF (OLD.subscription_status IS DISTINCT FROM NEW.subscription_status OR
        OLD.subscription_plan IS DISTINCT FROM NEW.subscription_plan) THEN
        
        INSERT INTO subscription_audit_log (
            user_id,
            old_status,
            new_status,
            old_plan,
            new_plan,
            changed_by,
            metadata
        ) VALUES (
            NEW.user_id,
            OLD.subscription_status,
            NEW.subscription_status,
            OLD.subscription_plan,
            NEW.subscription_plan,
            CASE 
                WHEN current_setting('role') = 'service_role' THEN 'webhook'
                ELSE 'manual'
            END,
            jsonb_build_object(
                'stripe_customer_id', NEW.stripe_customer_id,
                'stripe_subscription_id', NEW.stripe_subscription_id
            )
        );
    END IF;
    
    RETURN NEW;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.prevent_stripe_column_updates()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
    -- Check if any Stripe-related columns are being updated by non-service roles
    IF (current_setting('role') != 'service_role') THEN
        -- Prevent updates to critical Stripe columns
        IF (OLD.stripe_customer_id IS DISTINCT FROM NEW.stripe_customer_id OR
            OLD.subscription_status IS DISTINCT FROM NEW.subscription_status OR
            OLD.subscription_plan IS DISTINCT FROM NEW.subscription_plan OR
            OLD.stripe_subscription_id IS DISTINCT FROM NEW.stripe_subscription_id OR
            OLD.subscription_current_period_end IS DISTINCT FROM NEW.subscription_current_period_end OR
            OLD.subscription_cancel_at_period_end IS DISTINCT FROM NEW.subscription_cancel_at_period_end) THEN
            
            RAISE EXCEPTION 'Stripe subscription data can only be updated by the service'
                USING HINT = 'Use the Stripe customer portal or API to modify subscription data';
        END IF;
    END IF;
    
    RETURN NEW;
END;
$function$
;

CREATE OR REPLACE FUNCTION public.user_has_active_subscription(check_user_id uuid DEFAULT NULL::uuid)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    target_user_id UUID;
BEGIN
    -- If no user_id provided, use the authenticated user
    IF check_user_id IS NULL THEN
        target_user_id := auth.uid();
    ELSE
        target_user_id := check_user_id;
    END IF;
    
    -- Security check: users can only check their own status (unless service role)
    IF (current_setting('role') != 'service_role' AND auth.uid() != target_user_id) THEN
        RAISE EXCEPTION 'Access denied: can only check your own subscription status';
    END IF;
    
    RETURN EXISTS (
        SELECT 1 FROM users_metadata 
        WHERE user_id = target_user_id 
        AND subscription_status IN ('active', 'trialing')
    );
END;
$function$
;

CREATE OR REPLACE FUNCTION public.user_subscription_expires_at(check_user_id uuid DEFAULT NULL::uuid)
 RETURNS timestamp with time zone
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    expiry_date TIMESTAMP WITH TIME ZONE;
    target_user_id UUID;
BEGIN
    -- If no user_id provided, use the authenticated user
    IF check_user_id IS NULL THEN
        target_user_id := auth.uid();
    ELSE
        target_user_id := check_user_id;
    END IF;
    
    -- Security check: users can only check their own status (unless service role)
    IF (current_setting('role') != 'service_role' AND auth.uid() != target_user_id) THEN
        RAISE EXCEPTION 'Access denied: can only check your own subscription expiry';
    END IF;
    
    SELECT subscription_current_period_end INTO expiry_date
    FROM users_metadata 
    WHERE user_id = target_user_id 
    AND subscription_status IN ('active', 'trialing');
    
    RETURN expiry_date;
END;
$function$
;

grant delete on table "public"."share_invitations" to "anon";

grant insert on table "public"."share_invitations" to "anon";

grant references on table "public"."share_invitations" to "anon";

grant select on table "public"."share_invitations" to "anon";

grant trigger on table "public"."share_invitations" to "anon";

grant truncate on table "public"."share_invitations" to "anon";

grant update on table "public"."share_invitations" to "anon";

grant delete on table "public"."share_invitations" to "authenticated";

grant insert on table "public"."share_invitations" to "authenticated";

grant references on table "public"."share_invitations" to "authenticated";

grant select on table "public"."share_invitations" to "authenticated";

grant trigger on table "public"."share_invitations" to "authenticated";

grant truncate on table "public"."share_invitations" to "authenticated";

grant update on table "public"."share_invitations" to "authenticated";

grant delete on table "public"."share_invitations" to "service_role";

grant insert on table "public"."share_invitations" to "service_role";

grant references on table "public"."share_invitations" to "service_role";

grant select on table "public"."share_invitations" to "service_role";

grant trigger on table "public"."share_invitations" to "service_role";

grant truncate on table "public"."share_invitations" to "service_role";

grant update on table "public"."share_invitations" to "service_role";

grant delete on table "public"."stripe_subscriptions" to "anon";

grant insert on table "public"."stripe_subscriptions" to "anon";

grant references on table "public"."stripe_subscriptions" to "anon";

grant select on table "public"."stripe_subscriptions" to "anon";

grant trigger on table "public"."stripe_subscriptions" to "anon";

grant truncate on table "public"."stripe_subscriptions" to "anon";

grant update on table "public"."stripe_subscriptions" to "anon";

grant delete on table "public"."stripe_subscriptions" to "authenticated";

grant insert on table "public"."stripe_subscriptions" to "authenticated";

grant references on table "public"."stripe_subscriptions" to "authenticated";

grant select on table "public"."stripe_subscriptions" to "authenticated";

grant trigger on table "public"."stripe_subscriptions" to "authenticated";

grant truncate on table "public"."stripe_subscriptions" to "authenticated";

grant update on table "public"."stripe_subscriptions" to "authenticated";

grant delete on table "public"."stripe_subscriptions" to "service_role";

grant insert on table "public"."stripe_subscriptions" to "service_role";

grant references on table "public"."stripe_subscriptions" to "service_role";

grant select on table "public"."stripe_subscriptions" to "service_role";

grant trigger on table "public"."stripe_subscriptions" to "service_role";

grant truncate on table "public"."stripe_subscriptions" to "service_role";

grant update on table "public"."stripe_subscriptions" to "service_role";

grant delete on table "public"."stripe_webhook_events" to "anon";

grant insert on table "public"."stripe_webhook_events" to "anon";

grant references on table "public"."stripe_webhook_events" to "anon";

grant select on table "public"."stripe_webhook_events" to "anon";

grant trigger on table "public"."stripe_webhook_events" to "anon";

grant truncate on table "public"."stripe_webhook_events" to "anon";

grant update on table "public"."stripe_webhook_events" to "anon";

grant delete on table "public"."stripe_webhook_events" to "authenticated";

grant insert on table "public"."stripe_webhook_events" to "authenticated";

grant references on table "public"."stripe_webhook_events" to "authenticated";

grant select on table "public"."stripe_webhook_events" to "authenticated";

grant trigger on table "public"."stripe_webhook_events" to "authenticated";

grant truncate on table "public"."stripe_webhook_events" to "authenticated";

grant update on table "public"."stripe_webhook_events" to "authenticated";

grant delete on table "public"."stripe_webhook_events" to "service_role";

grant insert on table "public"."stripe_webhook_events" to "service_role";

grant references on table "public"."stripe_webhook_events" to "service_role";

grant select on table "public"."stripe_webhook_events" to "service_role";

grant trigger on table "public"."stripe_webhook_events" to "service_role";

grant truncate on table "public"."stripe_webhook_events" to "service_role";

grant update on table "public"."stripe_webhook_events" to "service_role";

grant delete on table "public"."subscription_audit_log" to "anon";

grant insert on table "public"."subscription_audit_log" to "anon";

grant references on table "public"."subscription_audit_log" to "anon";

grant select on table "public"."subscription_audit_log" to "anon";

grant trigger on table "public"."subscription_audit_log" to "anon";

grant truncate on table "public"."subscription_audit_log" to "anon";

grant update on table "public"."subscription_audit_log" to "anon";

grant delete on table "public"."subscription_audit_log" to "authenticated";

grant insert on table "public"."subscription_audit_log" to "authenticated";

grant references on table "public"."subscription_audit_log" to "authenticated";

grant select on table "public"."subscription_audit_log" to "authenticated";

grant trigger on table "public"."subscription_audit_log" to "authenticated";

grant truncate on table "public"."subscription_audit_log" to "authenticated";

grant update on table "public"."subscription_audit_log" to "authenticated";

grant delete on table "public"."subscription_audit_log" to "service_role";

grant insert on table "public"."subscription_audit_log" to "service_role";

grant references on table "public"."subscription_audit_log" to "service_role";

grant select on table "public"."subscription_audit_log" to "service_role";

grant trigger on table "public"."subscription_audit_log" to "service_role";

grant truncate on table "public"."subscription_audit_log" to "service_role";

grant update on table "public"."subscription_audit_log" to "service_role";

create policy "Users can create their own invitations"
on "public"."share_invitations"
as permissive
for insert
to public
with check ((auth.uid() = user_id));


create policy "Users can update their own invitations"
on "public"."share_invitations"
as permissive
for update
to public
using ((auth.uid() = user_id));


create policy "Users can view their own invitations"
on "public"."share_invitations"
as permissive
for select
to public
using ((auth.uid() = user_id));


create policy "Allow webhook insertion"
on "public"."stripe_webhook_events"
as permissive
for insert
to anon
with check (true);


create policy "Service role full access to webhook events"
on "public"."stripe_webhook_events"
as permissive
for all
to service_role
using (true)
with check (true);


create policy "Service role can manage audit log"
on "public"."subscription_audit_log"
as permissive
for all
to service_role
using (true)
with check (true);


create policy "Users can view own audit log"
on "public"."subscription_audit_log"
as permissive
for select
to authenticated
using ((auth.uid() = user_id));


create policy "Service role full access to user metadata"
on "public"."users_metadata"
as permissive
for all
to service_role
using (true)
with check (true);


create policy "Users can insert own metadata"
on "public"."users_metadata"
as permissive
for insert
to authenticated
with check ((auth.uid() = user_id));


create policy "Users can view own metadata"
on "public"."users_metadata"
as permissive
for select
to authenticated
using ((auth.uid() = user_id));


create policy "all"
on "public"."users_metadata"
as permissive
for insert
to public
with check (true);


CREATE TRIGGER prevent_stripe_updates_trigger BEFORE UPDATE ON public.users_metadata FOR EACH ROW EXECUTE FUNCTION prevent_stripe_column_updates();

CREATE TRIGGER subscription_audit_trigger AFTER UPDATE ON public.users_metadata FOR EACH ROW EXECUTE FUNCTION log_subscription_changes();


