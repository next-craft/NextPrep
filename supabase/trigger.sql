-- Run this ONCE in the Supabase SQL editor (Dashboard → SQL Editor).
-- NOT managed by Alembic — Alembic cannot write to the auth schema.

CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.users (id, full_name, avatar_url, is_verified)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'full_name', 'User'),
        NEW.raw_user_meta_data->>'avatar_url',
        COALESCE((NEW.raw_user_meta_data->>'email_verified')::boolean, FALSE)
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();
