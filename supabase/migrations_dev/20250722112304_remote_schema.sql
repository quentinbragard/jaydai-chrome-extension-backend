

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE EXTENSION IF NOT EXISTS "pg_net" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgsodium";






COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgjwt" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE OR REPLACE FUNCTION "public"."get_user_subscription"("user_uuid" "uuid") RETURNS TABLE("is_active" boolean, "plan_id" "text", "current_period_end" timestamp with time zone, "cancel_at_period_end" boolean, "stripe_customer_id" "text", "stripe_subscription_id" "text")
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
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
$$;


ALTER FUNCTION "public"."get_user_subscription"("user_uuid" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_user_subscription_status"("check_user_id" "uuid" DEFAULT NULL::"uuid") RETURNS TABLE("user_id" "uuid", "is_active" boolean, "plan_id" "text", "current_period_end" timestamp with time zone, "cancel_at_period_end" boolean, "has_stripe_customer" boolean)
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
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
$$;


ALTER FUNCTION "public"."get_user_subscription_status"("check_user_id" "uuid") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."get_user_subscription_status"("check_user_id" "uuid") IS 'Secure function to get user subscription status without exposing sensitive Stripe data';



CREATE OR REPLACE FUNCTION "public"."has_active_subscription"("user_uuid" "uuid") RETURNS boolean
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM users_metadata 
        WHERE user_id = user_uuid 
        AND subscription_status IN ('active', 'trialing')
    );
END;
$$;


ALTER FUNCTION "public"."has_active_subscription"("user_uuid" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."log_subscription_changes"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
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
$$;


ALTER FUNCTION "public"."log_subscription_changes"() OWNER TO "postgres";


COMMENT ON FUNCTION "public"."log_subscription_changes"() IS 'Automatically logs subscription status changes for audit purposes';



CREATE OR REPLACE FUNCTION "public"."prevent_stripe_column_updates"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
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
$$;


ALTER FUNCTION "public"."prevent_stripe_column_updates"() OWNER TO "postgres";


COMMENT ON FUNCTION "public"."prevent_stripe_column_updates"() IS 'Prevents unauthorized updates to Stripe-related columns';



CREATE OR REPLACE FUNCTION "public"."update_updated_at_column"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_updated_at_column"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."user_has_active_subscription"("check_user_id" "uuid" DEFAULT NULL::"uuid") RETURNS boolean
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
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
$$;


ALTER FUNCTION "public"."user_has_active_subscription"("check_user_id" "uuid") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."user_has_active_subscription"("check_user_id" "uuid") IS 'Safely check if a user has an active subscription';



CREATE OR REPLACE FUNCTION "public"."user_subscription_expires_at"("check_user_id" "uuid" DEFAULT NULL::"uuid") RETURNS timestamp with time zone
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
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
$$;


ALTER FUNCTION "public"."user_subscription_expires_at"("check_user_id" "uuid") OWNER TO "postgres";


COMMENT ON FUNCTION "public"."user_subscription_expires_at"("check_user_id" "uuid") IS 'Get subscription expiry date for a user';


SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."blog_posts" (
    "id" bigint NOT NULL,
    "title" "text" NOT NULL,
    "slug" "text" NOT NULL,
    "summary" "text" NOT NULL,
    "featured_image" "text",
    "author" "text" NOT NULL,
    "published_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "category" "text" NOT NULL,
    "tags" "text"[] DEFAULT '{}'::"text"[],
    "status" "text" DEFAULT 'draft'::"text" NOT NULL,
    "reading_time" integer DEFAULT 5 NOT NULL,
    "locale" "text" DEFAULT 'en'::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "call_to_action_metadata" "jsonb",
    "content_metadata" "jsonb"[],
    "page_metadata" "jsonb"
);


ALTER TABLE "public"."blog_posts" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."blog_posts_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."blog_posts_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."blog_posts_id_seq" OWNED BY "public"."blog_posts"."id";



CREATE TABLE IF NOT EXISTS "public"."chats" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "user_id" "uuid",
    "chat_provider_id" "text",
    "provider_name" "text",
    "title" "text"
);


ALTER TABLE "public"."chats" OWNER TO "postgres";


ALTER TABLE "public"."chats" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."chats_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."companies" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "name" "text"
);


ALTER TABLE "public"."companies" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."landing_page_contact_form" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "name" "text",
    "email" "text",
    "subject" "text",
    "message" "text"
);


ALTER TABLE "public"."landing_page_contact_form" OWNER TO "postgres";


ALTER TABLE "public"."landing_page_contact_form" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."landing_page_contact_form_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."messages" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "user_id" "uuid",
    "chat_provider_id" "text",
    "message_provider_id" "text",
    "role" "text",
    "model" "text",
    "parent_message_provider_id" "text",
    "tools" "text"[],
    "content" "text"
);


ALTER TABLE "public"."messages" OWNER TO "postgres";


ALTER TABLE "public"."messages" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."messages_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."notifications" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "user_id" "uuid",
    "read_at" timestamp with time zone,
    "type" "text",
    "title" "text",
    "body" "text",
    "metadata" "jsonb"
);


ALTER TABLE "public"."notifications" OWNER TO "postgres";


ALTER TABLE "public"."notifications" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."notifications_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."official_folders" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "type" "text",
    "tags" "text"[],
    "name_en" "text",
    "name_fr" "text"
);


ALTER TABLE "public"."official_folders" OWNER TO "postgres";


ALTER TABLE "public"."official_folders" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."official_folders_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."organization_folders" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "type" "text",
    "tags" "text"[],
    "path" "text",
    "organization_id" "uuid",
    "name_en" "text",
    "name_fr" "text"
);


ALTER TABLE "public"."organization_folders" OWNER TO "postgres";


ALTER TABLE "public"."organization_folders" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."organization_folders_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."organizations" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "name" "text",
    "image_url" "text",
    "banner_url" "text",
    "website_url" "text"
);


ALTER TABLE "public"."organizations" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."prompt_blocks" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "company_id" "uuid",
    "organization_id" "uuid",
    "user_id" "uuid",
    "type" "text",
    "content" "jsonb",
    "title" "jsonb",
    "description" "jsonb",
    "published" boolean DEFAULT false NOT NULL
);


ALTER TABLE "public"."prompt_blocks" OWNER TO "postgres";


ALTER TABLE "public"."prompt_blocks" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."prompt_blocks_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."prompt_folders" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "user_id" "uuid",
    "organization_id" "uuid",
    "parent_folder_id" bigint,
    "title" "jsonb",
    "description" "jsonb",
    "company_id" "uuid",
    "type" "text"
);


ALTER TABLE "public"."prompt_folders" OWNER TO "postgres";


ALTER TABLE "public"."prompt_folders" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."prompt_folders_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."prompt_templates" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "folder_id" bigint,
    "tags" "text"[],
    "last_used_at" timestamp with time zone,
    "path" "text",
    "type" "text",
    "usage_count" bigint DEFAULT '0'::bigint,
    "user_id" "uuid",
    "content_custom" "text",
    "content_en" "text",
    "content_fr" "text",
    "title_custom" "text",
    "title_en" "text",
    "title_fr" "text",
    "title" "jsonb",
    "content" "jsonb",
    "description" "jsonb",
    "blocks" bigint[],
    "company_id" "uuid",
    "organization_id" "uuid",
    "metadata" "jsonb",
    "is_free" boolean DEFAULT true
);


ALTER TABLE "public"."prompt_templates" OWNER TO "postgres";


ALTER TABLE "public"."prompt_templates" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."prompt_templates_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."share_invitations" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "inviter_email" "text" NOT NULL,
    "inviter_name" "text" NOT NULL,
    "friend_email" "text",
    "invitation_type" "text" NOT NULL,
    "status" "text" DEFAULT 'pending'::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "sent_at" timestamp with time zone,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb",
    CONSTRAINT "share_invitations_invitation_type_check" CHECK (("invitation_type" = ANY (ARRAY['friend'::"text", 'team'::"text", 'referral'::"text"]))),
    CONSTRAINT "share_invitations_status_check" CHECK (("status" = ANY (ARRAY['pending'::"text", 'sent'::"text", 'accepted'::"text", 'declined'::"text", 'failed'::"text"]))),
    CONSTRAINT "valid_friend_invitation" CHECK (((("invitation_type" = 'friend'::"text") AND ("friend_email" IS NOT NULL)) OR (("invitation_type" = ANY (ARRAY['team'::"text", 'referral'::"text"])) AND ("friend_email" IS NULL))))
);


ALTER TABLE "public"."share_invitations" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stripe_subscriptions" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "stripe_customer_id" "text" NOT NULL,
    "stripe_subscription_id" "text" NOT NULL,
    "stripe_price_id" "text" NOT NULL,
    "stripe_product_id" "text" NOT NULL,
    "status" "text" NOT NULL,
    "current_period_start" timestamp with time zone,
    "current_period_end" timestamp with time zone,
    "cancel_at_period_end" boolean DEFAULT false,
    "cancelled_at" timestamp with time zone,
    "trial_start" timestamp with time zone,
    "trial_end" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "metadata" "jsonb" DEFAULT '{}'::"jsonb"
);


ALTER TABLE "public"."stripe_subscriptions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stripe_webhook_events" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "stripe_event_id" character varying(255) NOT NULL,
    "event_type" character varying(100) NOT NULL,
    "event_data" "jsonb" NOT NULL,
    "processed" boolean DEFAULT false,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "processed_at" timestamp with time zone
);


ALTER TABLE "public"."stripe_webhook_events" OWNER TO "postgres";


COMMENT ON TABLE "public"."stripe_webhook_events" IS 'Stores Stripe webhook events for processing and audit purposes';



CREATE TABLE IF NOT EXISTS "public"."subscription_audit_log" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "old_status" "text",
    "new_status" "text",
    "old_plan" "text",
    "new_plan" "text",
    "stripe_event_id" "text",
    "changed_by" "text",
    "changed_at" timestamp with time zone DEFAULT "now"(),
    "metadata" "jsonb"
);


ALTER TABLE "public"."subscription_audit_log" OWNER TO "postgres";


COMMENT ON TABLE "public"."subscription_audit_log" IS 'Audit trail for all subscription status changes (UUID user_id)';



CREATE TABLE IF NOT EXISTS "public"."user_folders" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "type" "text",
    "tags" "text"[],
    "path" "text",
    "user_id" "uuid",
    "description" "text",
    "locale" "text",
    "name" "text"
);


ALTER TABLE "public"."user_folders" OWNER TO "postgres";


ALTER TABLE "public"."user_folders" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."user_folders_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."users_metadata" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "user_id" "uuid",
    "name" "text",
    "phone_number" "text",
    "pinned_official_folder_ids" bigint[],
    "pinned_organization_folder_ids" bigint[],
    "preferences_metadata" "jsonb",
    "additional_email" "text",
    "additional_organization" "text",
    "linkedin_headline" "text",
    "linkedin_id" "text",
    "linkedin_profile_url" "text",
    "email" "text",
    "google_id" "text",
    "job_type" "text",
    "job_industry" "text",
    "job_seniority" "text",
    "interests" "text"[],
    "signup_source" "text",
    "organization_ids" "uuid"[],
    "company_id" "uuid",
    "pinned_folder_ids" bigint[],
    "pinned_template_ids" bigint[],
    "stripe_customer_id" character varying(255),
    "subscription_status" character varying(50) DEFAULT 'free'::character varying,
    "subscription_plan" character varying(50),
    "stripe_subscription_id" character varying(255),
    "subscription_current_period_end" timestamp with time zone,
    "subscription_cancel_at_period_end" boolean DEFAULT false,
    "data_collection" boolean DEFAULT true
);


ALTER TABLE "public"."users_metadata" OWNER TO "postgres";


COMMENT ON COLUMN "public"."users_metadata"."stripe_customer_id" IS 'Stripe customer ID for this user';



COMMENT ON COLUMN "public"."users_metadata"."subscription_status" IS 'Current subscription status: free, active, inactive, cancelled, past_due, trialing';



COMMENT ON COLUMN "public"."users_metadata"."subscription_plan" IS 'Current plan: monthly, yearly, or null for free';



COMMENT ON COLUMN "public"."users_metadata"."stripe_subscription_id" IS 'Stripe subscription ID';



COMMENT ON COLUMN "public"."users_metadata"."subscription_current_period_end" IS 'When the current billing period ends';



COMMENT ON COLUMN "public"."users_metadata"."subscription_cancel_at_period_end" IS 'Whether subscription is set to cancel at period end';



ALTER TABLE "public"."users_metadata" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."users_metadata_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



ALTER TABLE ONLY "public"."blog_posts" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."blog_posts_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."blog_posts"
    ADD CONSTRAINT "blog_posts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."blog_posts"
    ADD CONSTRAINT "blog_posts_slug_key" UNIQUE ("slug");



ALTER TABLE ONLY "public"."chats"
    ADD CONSTRAINT "chats_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."companies"
    ADD CONSTRAINT "companies_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."landing_page_contact_form"
    ADD CONSTRAINT "landing_page_contact_form_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."messages"
    ADD CONSTRAINT "messages_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."notifications"
    ADD CONSTRAINT "notifications_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."official_folders"
    ADD CONSTRAINT "official_folders_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."prompt_templates"
    ADD CONSTRAINT "official_prompt_templates_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organization_folders"
    ADD CONSTRAINT "organization_folders_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organizations"
    ADD CONSTRAINT "organizations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."prompt_blocks"
    ADD CONSTRAINT "prompt_blocks_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."prompt_folders"
    ADD CONSTRAINT "prompt_folders_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."share_invitations"
    ADD CONSTRAINT "share_invitations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."stripe_subscriptions"
    ADD CONSTRAINT "stripe_subscriptions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."stripe_subscriptions"
    ADD CONSTRAINT "stripe_subscriptions_stripe_subscription_id_key" UNIQUE ("stripe_subscription_id");



ALTER TABLE ONLY "public"."stripe_webhook_events"
    ADD CONSTRAINT "stripe_webhook_events_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."stripe_webhook_events"
    ADD CONSTRAINT "stripe_webhook_events_stripe_event_id_key" UNIQUE ("stripe_event_id");



ALTER TABLE ONLY "public"."subscription_audit_log"
    ADD CONSTRAINT "subscription_audit_log_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_folders"
    ADD CONSTRAINT "user_folders_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."users_metadata"
    ADD CONSTRAINT "users_metadata_pkey" PRIMARY KEY ("id");



CREATE INDEX "idx_blog_posts_category" ON "public"."blog_posts" USING "btree" ("category");



CREATE INDEX "idx_blog_posts_locale" ON "public"."blog_posts" USING "btree" ("locale");



CREATE INDEX "idx_blog_posts_published_at" ON "public"."blog_posts" USING "btree" ("published_at");



CREATE INDEX "idx_blog_posts_slug" ON "public"."blog_posts" USING "btree" ("slug");



CREATE INDEX "idx_blog_posts_status" ON "public"."blog_posts" USING "btree" ("status");



CREATE INDEX "idx_share_invitations_status" ON "public"."share_invitations" USING "btree" ("status");



CREATE INDEX "idx_share_invitations_type" ON "public"."share_invitations" USING "btree" ("invitation_type");



CREATE INDEX "idx_share_invitations_user_id" ON "public"."share_invitations" USING "btree" ("user_id");



CREATE INDEX "idx_stripe_webhook_events_processed" ON "public"."stripe_webhook_events" USING "btree" ("processed");



CREATE INDEX "idx_stripe_webhook_events_stripe_id" ON "public"."stripe_webhook_events" USING "btree" ("stripe_event_id");



CREATE INDEX "idx_stripe_webhook_events_type" ON "public"."stripe_webhook_events" USING "btree" ("event_type");



CREATE INDEX "idx_users_metadata_linkedin_id" ON "public"."users_metadata" USING "btree" ("linkedin_id");



CREATE INDEX "idx_users_metadata_stripe_customer" ON "public"."users_metadata" USING "btree" ("stripe_customer_id");



CREATE INDEX "idx_users_metadata_stripe_subscription" ON "public"."users_metadata" USING "btree" ("stripe_subscription_id");



CREATE INDEX "idx_users_metadata_subscription_status" ON "public"."users_metadata" USING "btree" ("subscription_status");



CREATE OR REPLACE TRIGGER "prevent_stripe_updates_trigger" BEFORE UPDATE ON "public"."users_metadata" FOR EACH ROW EXECUTE FUNCTION "public"."prevent_stripe_column_updates"();



CREATE OR REPLACE TRIGGER "subscription_audit_trigger" AFTER UPDATE ON "public"."users_metadata" FOR EACH ROW EXECUTE FUNCTION "public"."log_subscription_changes"();



ALTER TABLE ONLY "public"."chats"
    ADD CONSTRAINT "chats_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."messages"
    ADD CONSTRAINT "messages_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."notifications"
    ADD CONSTRAINT "notifications_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."organization_folders"
    ADD CONSTRAINT "organization_folders_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id");



ALTER TABLE ONLY "public"."prompt_blocks"
    ADD CONSTRAINT "prompt_blocks_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "public"."companies"("id");



ALTER TABLE ONLY "public"."prompt_blocks"
    ADD CONSTRAINT "prompt_blocks_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id");



ALTER TABLE ONLY "public"."prompt_blocks"
    ADD CONSTRAINT "prompt_blocks_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."prompt_folders"
    ADD CONSTRAINT "prompt_folders_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "public"."companies"("id");



ALTER TABLE ONLY "public"."prompt_folders"
    ADD CONSTRAINT "prompt_folders_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id");



ALTER TABLE ONLY "public"."prompt_folders"
    ADD CONSTRAINT "prompt_folders_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."prompt_templates"
    ADD CONSTRAINT "prompt_templates_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "public"."companies"("id");



ALTER TABLE ONLY "public"."prompt_templates"
    ADD CONSTRAINT "prompt_templates_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id");



ALTER TABLE ONLY "public"."prompt_templates"
    ADD CONSTRAINT "prompt_templates_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."stripe_subscriptions"
    ADD CONSTRAINT "stripe_subscriptions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_folders"
    ADD CONSTRAINT "user_folders_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id");



ALTER TABLE ONLY "public"."users_metadata"
    ADD CONSTRAINT "users_metadata_company_id_fkey" FOREIGN KEY ("company_id") REFERENCES "public"."companies"("id");



ALTER TABLE ONLY "public"."users_metadata"
    ADD CONSTRAINT "users_metadata_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id");



CREATE POLICY "Allow webhook insertion" ON "public"."stripe_webhook_events" FOR INSERT TO "anon" WITH CHECK (true);



CREATE POLICY "Enable insert access for all users" ON "public"."landing_page_contact_form" FOR INSERT WITH CHECK (true);



CREATE POLICY "Enable insert for authenticated users only" ON "public"."prompt_templates" FOR INSERT TO "authenticated" WITH CHECK (true);



CREATE POLICY "Enable insert for service role only" ON "public"."notifications" FOR INSERT TO "service_role" WITH CHECK (true);



CREATE POLICY "Enable insert for service role only" ON "public"."users_metadata" FOR INSERT WITH CHECK (true);



CREATE POLICY "Enable insert for users based on user_id" ON "public"."chats" FOR INSERT TO "authenticated" WITH CHECK ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



CREATE POLICY "Enable insert for users based on user_id" ON "public"."messages" FOR INSERT TO "authenticated" WITH CHECK ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



CREATE POLICY "Enable insert for users based on user_id" ON "public"."user_folders" FOR INSERT TO "authenticated" WITH CHECK ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



CREATE POLICY "Enable read access for all users" ON "public"."blog_posts" FOR SELECT USING (true);



CREATE POLICY "Enable read access for all users" ON "public"."prompt_blocks" FOR SELECT USING (true);



CREATE POLICY "Enable read access for authenticated users" ON "public"."official_folders" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "Enable read for authenticated users only" ON "public"."prompt_templates" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "Enable read for users based on user_id" ON "public"."chats" FOR SELECT TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



CREATE POLICY "Enable read for users based on user_id" ON "public"."messages" FOR SELECT TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



CREATE POLICY "Enable read for users based on user_id" ON "public"."notifications" FOR SELECT TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



CREATE POLICY "Enable read for users based on user_id" ON "public"."user_folders" FOR SELECT TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



CREATE POLICY "Enable read for users based on user_id" ON "public"."users_metadata" FOR SELECT TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "user_id"));



CREATE POLICY "Enable write access for all users" ON "public"."users_metadata" FOR INSERT WITH CHECK (true);



CREATE POLICY "Service role can manage audit log" ON "public"."subscription_audit_log" TO "service_role" USING (true) WITH CHECK (true);



CREATE POLICY "Service role full access to user metadata" ON "public"."users_metadata" TO "service_role" USING (true) WITH CHECK (true);



CREATE POLICY "Service role full access to webhook events" ON "public"."stripe_webhook_events" TO "service_role" USING (true) WITH CHECK (true);



CREATE POLICY "Users can create their own invitations" ON "public"."share_invitations" FOR INSERT WITH CHECK (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can insert own metadata" ON "public"."users_metadata" FOR INSERT TO "authenticated" WITH CHECK (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can update their own invitations" ON "public"."share_invitations" FOR UPDATE USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can view own audit log" ON "public"."subscription_audit_log" FOR SELECT TO "authenticated" USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can view own metadata" ON "public"."users_metadata" FOR SELECT TO "authenticated" USING (("auth"."uid"() = "user_id"));



CREATE POLICY "Users can view their own invitations" ON "public"."share_invitations" FOR SELECT USING (("auth"."uid"() = "user_id"));



ALTER TABLE "public"."blog_posts" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."chats" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."companies" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."landing_page_contact_form" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."messages" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."notifications" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."official_folders" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."organization_folders" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."organizations" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."prompt_blocks" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."prompt_folders" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."prompt_templates" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."share_invitations" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."stripe_webhook_events" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."subscription_audit_log" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."user_folders" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."users_metadata" ENABLE ROW LEVEL SECURITY;




ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";





GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";




















































































































































































GRANT ALL ON FUNCTION "public"."get_user_subscription"("user_uuid" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."get_user_subscription"("user_uuid" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_user_subscription"("user_uuid" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."get_user_subscription_status"("check_user_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."get_user_subscription_status"("check_user_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_user_subscription_status"("check_user_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."has_active_subscription"("user_uuid" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."has_active_subscription"("user_uuid" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."has_active_subscription"("user_uuid" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."log_subscription_changes"() TO "anon";
GRANT ALL ON FUNCTION "public"."log_subscription_changes"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."log_subscription_changes"() TO "service_role";



GRANT ALL ON FUNCTION "public"."prevent_stripe_column_updates"() TO "anon";
GRANT ALL ON FUNCTION "public"."prevent_stripe_column_updates"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."prevent_stripe_column_updates"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_updated_at_column"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_updated_at_column"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_updated_at_column"() TO "service_role";



GRANT ALL ON FUNCTION "public"."user_has_active_subscription"("check_user_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."user_has_active_subscription"("check_user_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."user_has_active_subscription"("check_user_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."user_subscription_expires_at"("check_user_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."user_subscription_expires_at"("check_user_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."user_subscription_expires_at"("check_user_id" "uuid") TO "service_role";



























GRANT ALL ON TABLE "public"."blog_posts" TO "anon";
GRANT ALL ON TABLE "public"."blog_posts" TO "authenticated";
GRANT ALL ON TABLE "public"."blog_posts" TO "service_role";



GRANT ALL ON SEQUENCE "public"."blog_posts_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."blog_posts_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."blog_posts_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."chats" TO "anon";
GRANT ALL ON TABLE "public"."chats" TO "authenticated";
GRANT ALL ON TABLE "public"."chats" TO "service_role";



GRANT ALL ON SEQUENCE "public"."chats_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."chats_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."chats_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."companies" TO "anon";
GRANT ALL ON TABLE "public"."companies" TO "authenticated";
GRANT ALL ON TABLE "public"."companies" TO "service_role";



GRANT ALL ON TABLE "public"."landing_page_contact_form" TO "anon";
GRANT ALL ON TABLE "public"."landing_page_contact_form" TO "authenticated";
GRANT ALL ON TABLE "public"."landing_page_contact_form" TO "service_role";



GRANT ALL ON SEQUENCE "public"."landing_page_contact_form_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."landing_page_contact_form_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."landing_page_contact_form_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."messages" TO "anon";
GRANT ALL ON TABLE "public"."messages" TO "authenticated";
GRANT ALL ON TABLE "public"."messages" TO "service_role";



GRANT ALL ON SEQUENCE "public"."messages_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."messages_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."messages_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."notifications" TO "anon";
GRANT ALL ON TABLE "public"."notifications" TO "authenticated";
GRANT ALL ON TABLE "public"."notifications" TO "service_role";



GRANT ALL ON SEQUENCE "public"."notifications_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."notifications_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."notifications_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."official_folders" TO "anon";
GRANT ALL ON TABLE "public"."official_folders" TO "authenticated";
GRANT ALL ON TABLE "public"."official_folders" TO "service_role";



GRANT ALL ON SEQUENCE "public"."official_folders_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."official_folders_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."official_folders_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."organization_folders" TO "anon";
GRANT ALL ON TABLE "public"."organization_folders" TO "authenticated";
GRANT ALL ON TABLE "public"."organization_folders" TO "service_role";



GRANT ALL ON SEQUENCE "public"."organization_folders_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."organization_folders_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."organization_folders_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."organizations" TO "anon";
GRANT ALL ON TABLE "public"."organizations" TO "authenticated";
GRANT ALL ON TABLE "public"."organizations" TO "service_role";



GRANT ALL ON TABLE "public"."prompt_blocks" TO "anon";
GRANT ALL ON TABLE "public"."prompt_blocks" TO "authenticated";
GRANT ALL ON TABLE "public"."prompt_blocks" TO "service_role";



GRANT ALL ON SEQUENCE "public"."prompt_blocks_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."prompt_blocks_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."prompt_blocks_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."prompt_folders" TO "anon";
GRANT ALL ON TABLE "public"."prompt_folders" TO "authenticated";
GRANT ALL ON TABLE "public"."prompt_folders" TO "service_role";



GRANT ALL ON SEQUENCE "public"."prompt_folders_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."prompt_folders_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."prompt_folders_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."prompt_templates" TO "anon";
GRANT ALL ON TABLE "public"."prompt_templates" TO "authenticated";
GRANT ALL ON TABLE "public"."prompt_templates" TO "service_role";



GRANT ALL ON SEQUENCE "public"."prompt_templates_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."prompt_templates_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."prompt_templates_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."share_invitations" TO "anon";
GRANT ALL ON TABLE "public"."share_invitations" TO "authenticated";
GRANT ALL ON TABLE "public"."share_invitations" TO "service_role";



GRANT ALL ON TABLE "public"."stripe_subscriptions" TO "anon";
GRANT ALL ON TABLE "public"."stripe_subscriptions" TO "authenticated";
GRANT ALL ON TABLE "public"."stripe_subscriptions" TO "service_role";



GRANT ALL ON TABLE "public"."stripe_webhook_events" TO "anon";
GRANT ALL ON TABLE "public"."stripe_webhook_events" TO "authenticated";
GRANT ALL ON TABLE "public"."stripe_webhook_events" TO "service_role";



GRANT ALL ON TABLE "public"."subscription_audit_log" TO "anon";
GRANT ALL ON TABLE "public"."subscription_audit_log" TO "authenticated";
GRANT ALL ON TABLE "public"."subscription_audit_log" TO "service_role";



GRANT ALL ON TABLE "public"."user_folders" TO "anon";
GRANT ALL ON TABLE "public"."user_folders" TO "authenticated";
GRANT ALL ON TABLE "public"."user_folders" TO "service_role";



GRANT ALL ON SEQUENCE "public"."user_folders_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."user_folders_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."user_folders_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."users_metadata" TO "anon";
GRANT ALL ON TABLE "public"."users_metadata" TO "authenticated";
GRANT ALL ON TABLE "public"."users_metadata" TO "service_role";



GRANT ALL ON SEQUENCE "public"."users_metadata_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."users_metadata_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."users_metadata_id_seq" TO "service_role";









ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";






























RESET ALL;
