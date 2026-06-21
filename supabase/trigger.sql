-- Run this ONCE in the Supabase SQL editor (Dashboard → SQL Editor).
-- NOT managed by Alembic — Alembic cannot write to the auth schema.

CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    -- is_verified is NOT set here: it is an EARNED badge (books_sold >= 10), no longer
    -- derived from the OAuth email_verified claim (which would grant it to nearly every
    -- user). It defaults to FALSE at the DB level. See migration 0006.
    INSERT INTO public.users (id, full_name, avatar_url)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'full_name', 'User'),
        NEW.raw_user_meta_data->>'avatar_url'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();
