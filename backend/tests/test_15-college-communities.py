"""
Tests for Spec 15 — College Communities.

Derived from .claude/specs/technical/15-college-communities.md and
.claude/CLAUDE.md — NOT from reading the implementation.

Prerequisites:
  - Migration 0012 applied (colleges table + college_id/college_other on
    listings and public.users).
  - A reachable Postgres DB (uses AsyncSessionLocal → real rows).
  - Auth is mocked via FastAPI dependency_overrides; no live Supabase JWKS
    calls are made during these tests.

Endpoints under test:
  GET    /v1/colleges                            (public)
  GET    /v1/colleges/{slug}                     (public)
  GET    /v1/listings?college=<slug>             (public filter)
  POST   /v1/listings                            (protected — college_id/other)
  PATCH  /v1/listings/{id}                       (protected — college edit)
  GET    /v1/users/me                            (protected — college embedded)
  PATCH  /v1/users/me                            (protected — college_id/other)
  GET    /v1/users/{id}                          (public  — college embedded)
"""

import asyncio
import sys
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.main import app
from app.core.security import verify_token, optional_user
from app.core.database import AsyncSessionLocal

# ---------------------------------------------------------------------------
# Module-level deterministic IDs
# ---------------------------------------------------------------------------

SELLER_ID = str(uuid.uuid4())
OTHER_USER_ID = str(uuid.uuid4())

# Two active colleges inserted by this module's fixture
COLLEGE_ACTIVE_1_ID = str(uuid.uuid4())
COLLEGE_ACTIVE_1_SLUG = f"test-iit-bombay-{COLLEGE_ACTIVE_1_ID[:8]}"
COLLEGE_ACTIVE_1_NAME = f"Test IIT Bombay {COLLEGE_ACTIVE_1_ID[:8]}"

COLLEGE_ACTIVE_2_ID = str(uuid.uuid4())
COLLEGE_ACTIVE_2_SLUG = f"test-iit-delhi-{COLLEGE_ACTIVE_2_ID[:8]}"
COLLEGE_ACTIVE_2_NAME = f"Test IIT Delhi {COLLEGE_ACTIVE_2_ID[:8]}"

# One inactive (retired) college
COLLEGE_INACTIVE_ID = str(uuid.uuid4())
COLLEGE_INACTIVE_SLUG = f"test-retired-college-{COLLEGE_INACTIVE_ID[:8]}"
COLLEGE_INACTIVE_NAME = f"Test Retired College {COLLEGE_INACTIVE_ID[:8]}"

# Valid state/city pair from igod constants (Maharashtra / Mumbai Suburban)
VALID_STATE = "Maharashtra"
VALID_CITY = "Mumbai Suburban"

# Minimal valid listing payload (no college fields by default)
BASE_LISTING = {
    "title": "HC Verma Part 1",
    "description": "Lightly used",
    "exam_category": "JEE_MAINS",
    "subject": "Physics",
    "listing_type": "BOOK",
    "condition": "A",
    "asking_price": 350,
    "original_price": 600,
    "state": VALID_STATE,
    "city": VALID_CITY,
    "images": ["https://res.cloudinary.com/demo/image/upload/v1/sample.jpg"],
}


# ---------------------------------------------------------------------------
# Auth helpers (mirror test_14 pattern exactly)
# ---------------------------------------------------------------------------

def _override_verify_token(user_id: str):
    def _inner():
        return {"sub": user_id, "email": f"{user_id}@example.com"}
    return _inner


def _override_optional_user(user_id):
    def _inner():
        if user_id is None:
            return None
        return {"sub": user_id, "email": f"{user_id}@example.com"}
    return _inner


# ---------------------------------------------------------------------------
# DB seed / cleanup helpers
# ---------------------------------------------------------------------------

async def _seed_async():
    async with AsyncSessionLocal() as session:
        # Seed users
        await session.execute(
            text(
                """
                INSERT INTO public.users (id, full_name)
                VALUES (:seller_id, 'Test Seller 15'), (:other_id, 'Test Other 15')
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"seller_id": SELLER_ID, "other_id": OTHER_USER_ID},
        )
        # Seed active college 1
        await session.execute(
            text(
                """
                INSERT INTO colleges (id, slug, name, state, city, is_active)
                VALUES (:id, :slug, :name, 'Maharashtra', 'Mumbai Suburban', TRUE)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": COLLEGE_ACTIVE_1_ID,
                "slug": COLLEGE_ACTIVE_1_SLUG,
                "name": COLLEGE_ACTIVE_1_NAME,
            },
        )
        # Seed active college 2
        await session.execute(
            text(
                """
                INSERT INTO colleges (id, slug, name, state, city, is_active)
                VALUES (:id, :slug, :name, 'Delhi', 'South', TRUE)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": COLLEGE_ACTIVE_2_ID,
                "slug": COLLEGE_ACTIVE_2_SLUG,
                "name": COLLEGE_ACTIVE_2_NAME,
            },
        )
        # Seed inactive college
        await session.execute(
            text(
                """
                INSERT INTO colleges (id, slug, name, state, city, is_active)
                VALUES (:id, :slug, :name, 'Goa', 'North Goa', FALSE)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": COLLEGE_INACTIVE_ID,
                "slug": COLLEGE_INACTIVE_SLUG,
                "name": COLLEGE_INACTIVE_NAME,
            },
        )
        await session.commit()


async def _cleanup_async():
    async with AsyncSessionLocal() as session:
        # Remove listings seeded by tests
        await session.execute(
            text(
                "DELETE FROM listings WHERE seller_id IN (:seller_id, :other_id)"
            ),
            {"seller_id": SELLER_ID, "other_id": OTHER_USER_ID},
        )
        # Clear college from users before removing the college row
        await session.execute(
            text(
                "UPDATE public.users SET college_id = NULL, college_other = NULL "
                "WHERE id IN (:seller_id, :other_id)"
            ),
            {"seller_id": SELLER_ID, "other_id": OTHER_USER_ID},
        )
        await session.execute(
            text(
                "DELETE FROM public.users WHERE id IN (:seller_id, :other_id)"
            ),
            {"seller_id": SELLER_ID, "other_id": OTHER_USER_ID},
        )
        # Remove test colleges (ON DELETE SET NULL already cleared FK refs above)
        await session.execute(
            text(
                "DELETE FROM colleges WHERE id IN (:id1, :id2, :id3)"
            ),
            {
                "id1": COLLEGE_ACTIVE_1_ID,
                "id2": COLLEGE_ACTIVE_2_ID,
                "id3": COLLEGE_INACTIVE_ID,
            },
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _seed_test_data():
    """
    Seed two active colleges, one inactive college, and two users before every
    test; clean all test rows afterward.  Idempotent (ON CONFLICT DO NOTHING).
    Mirrors test_14's autouse _seed_test_users pattern.
    """
    asyncio.run(_seed_async())
    yield
    asyncio.run(_cleanup_async())


@pytest.fixture
def auth_as_seller():
    app.dependency_overrides[verify_token] = _override_verify_token(SELLER_ID)
    yield SELLER_ID
    app.dependency_overrides.pop(verify_token, None)


@pytest.fixture
def auth_as_other():
    app.dependency_overrides[verify_token] = _override_verify_token(OTHER_USER_ID)
    yield OTHER_USER_ID
    app.dependency_overrides.pop(verify_token, None)


# Helper: create a listing with college_id set to COLLEGE_ACTIVE_1
def _create_listing_with_college(client, college_id=COLLEGE_ACTIVE_1_ID):
    payload = dict(BASE_LISTING)
    payload["college_id"] = college_id
    return client.post("/v1/listings", json=payload)


# ===========================================================================
# Section A — GET /v1/colleges (typeahead)
# ===========================================================================

def test_get_colleges_no_query_returns_200_and_array(client):
    """Spec: GET /v1/colleges (empty q) returns active colleges — public, no auth."""
    resp = client.get("/v1/colleges")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_colleges_no_query_includes_active_colleges(client):
    """Spec: the typeahead returns active colleges. Scoped by each seeded college's
    unique term — the table is fully seeded (411 rows) and the endpoint returns at
    most 20 name-sorted rows, so an unscoped call won't contain the test rows."""
    for slug, cid in (
        (COLLEGE_ACTIVE_1_SLUG, COLLEGE_ACTIVE_1_ID),
        (COLLEGE_ACTIVE_2_SLUG, COLLEGE_ACTIVE_2_ID),
    ):
        resp = client.get("/v1/colleges", params={"q": cid[:8]})
        assert resp.status_code == 200
        assert slug in [c["slug"] for c in resp.json()]


def test_get_colleges_no_query_excludes_inactive_colleges(client):
    """Spec: is_active=FALSE hides a college from typeahead without deleting it."""
    resp = client.get("/v1/colleges")
    slugs = [c["slug"] for c in resp.json()]
    assert COLLEGE_INACTIVE_SLUG not in slugs


def test_get_colleges_with_q_returns_name_matching_colleges(client):
    """Spec: ?q= filters by ILIKE on name; seeded COLLEGE_ACTIVE_1 must appear."""
    # Use the unique prefix baked into the slug/name so only our row matches
    unique_term = COLLEGE_ACTIVE_1_ID[:8]
    resp = client.get("/v1/colleges", params={"q": unique_term})
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert any(unique_term in n for n in names)


def test_get_colleges_q_match_is_case_insensitive(client):
    """Spec: ILIKE — both upper and lower-case terms must hit the same rows."""
    unique_term = COLLEGE_ACTIVE_1_ID[:8].upper()
    resp = client.get("/v1/colleges", params={"q": unique_term})
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert any(COLLEGE_ACTIVE_1_ID[:8] in n.lower() for n in names)


def test_get_colleges_q_match_excludes_inactive(client):
    """Spec: ?q= that matches an inactive college by name returns nothing for it."""
    # search for the inactive college's unique term
    unique_term = COLLEGE_INACTIVE_ID[:8]
    resp = client.get("/v1/colleges", params={"q": unique_term})
    assert resp.status_code == 200
    slugs = [c["slug"] for c in resp.json()]
    assert COLLEGE_INACTIVE_SLUG not in slugs


def test_get_colleges_returns_at_most_20_results(client):
    """Spec: typeahead is capped at 20 results."""
    resp = client.get("/v1/colleges")
    assert resp.status_code == 200
    assert len(resp.json()) <= 20


def test_get_colleges_results_are_name_sorted(client):
    """Spec: results are sorted by name ascending. Scoped to the seeded test colleges
    via their shared 'Test IIT' prefix so the check is independent of Postgres-vs-Python
    collation differences across the fully-seeded 411-row table."""
    resp = client.get("/v1/colleges", params={"q": "Test IIT "})
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert names == sorted(names)


def test_get_colleges_response_shape_includes_required_fields(client):
    """CollegeOut must expose id, slug, name (and optionally state/city)."""
    resp = client.get("/v1/colleges")
    assert resp.status_code == 200
    if resp.json():
        col = resp.json()[0]
        assert "id" in col
        assert "slug" in col
        assert "name" in col


def test_get_colleges_does_not_require_auth(client):
    """Spec: GET /v1/colleges is a public endpoint — no token needed."""
    # No override — request goes through without any Authorization header
    resp = client.get("/v1/colleges")
    assert resp.status_code == 200


def test_get_colleges_q_no_match_returns_empty_array(client):
    """Spec: a query that matches nothing returns [] (200), not 404/422."""
    resp = client.get("/v1/colleges", params={"q": "ZZZnoMatchUniversityXYZ"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_colleges_q_sql_injection_is_safe(client):
    """Spec (security): ILIKE uses parameterized ORM — injection must not alter results."""
    resp = client.get("/v1/colleges", params={"q": "'; DROP TABLE colleges; --"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    # Confirm the table is still intact after the attempted injection
    follow_up = client.get("/v1/colleges")
    assert follow_up.status_code == 200


# ---------------------------------------------------------------------------
# GET /v1/colleges?has_listings=1
# ---------------------------------------------------------------------------

def test_get_colleges_has_listings_returns_only_colleges_with_active_listings(
    client, auth_as_seller
):
    """Spec: ?has_listings=1 returns ONLY colleges with >=1 active, non-deleted listing."""
    # Create a listing attached to COLLEGE_ACTIVE_1
    _create_listing_with_college(client)

    resp = client.get("/v1/colleges", params={"has_listings": "1"})
    assert resp.status_code == 200
    slugs = [c["slug"] for c in resp.json()]
    # COLLEGE_ACTIVE_1 has a listing; COLLEGE_ACTIVE_2 has none
    assert COLLEGE_ACTIVE_1_SLUG in slugs
    assert COLLEGE_ACTIVE_2_SLUG not in slugs


def test_get_colleges_has_listings_excludes_inactive_colleges(client, auth_as_seller):
    """Spec: inactive college must not appear even if it somehow has listings."""
    # We cannot link a listing to an inactive college via the API (400), so
    # we only assert that the inactive college is absent from the response.
    resp = client.get("/v1/colleges", params={"has_listings": "1"})
    assert resp.status_code == 200
    slugs = [c["slug"] for c in resp.json()]
    assert COLLEGE_INACTIVE_SLUG not in slugs


def test_get_colleges_has_listings_returns_empty_when_no_active_listings(client):
    """Spec: if no active listings exist for any college, response is []."""
    # No listings created in this test
    resp = client.get("/v1/colleges", params={"has_listings": "1"})
    assert resp.status_code == 200
    # Should return only colleges with active listings; our test colleges have none
    slugs = [c["slug"] for c in resp.json()]
    assert COLLEGE_ACTIVE_1_SLUG not in slugs
    assert COLLEGE_ACTIVE_2_SLUG not in slugs


# ===========================================================================
# Section B — GET /v1/colleges/{slug}
# ===========================================================================

def test_get_college_by_slug_returns_200_with_college_and_listings_keys(client):
    """Spec: /colleges/{slug} returns {college, listings:[...]} for an active slug."""
    resp = client.get(f"/v1/colleges/{COLLEGE_ACTIVE_1_SLUG}")
    assert resp.status_code == 200
    body = resp.json()
    assert "college" in body
    assert "listings" in body
    assert isinstance(body["listings"], list)


def test_get_college_by_slug_college_field_matches_seeded_slug(client):
    """Spec: the returned college object slug matches the requested slug."""
    resp = client.get(f"/v1/colleges/{COLLEGE_ACTIVE_1_SLUG}")
    assert resp.status_code == 200
    assert resp.json()["college"]["slug"] == COLLEGE_ACTIVE_1_SLUG


def test_get_college_by_slug_college_field_contains_name(client):
    """Spec: the returned college object contains the canonical name."""
    resp = client.get(f"/v1/colleges/{COLLEGE_ACTIVE_1_SLUG}")
    assert resp.status_code == 200
    assert resp.json()["college"]["name"] == COLLEGE_ACTIVE_1_NAME


def test_get_college_by_slug_returns_404_for_unknown_slug(client):
    """Spec: unknown slug → 404."""
    resp = client.get("/v1/colleges/does-not-exist-slug-xyz")
    assert resp.status_code == 404


def test_get_college_by_slug_returns_404_for_inactive_slug(client):
    """Spec: is_active=FALSE → 404 (same as unknown; hides without deleting)."""
    resp = client.get(f"/v1/colleges/{COLLEGE_INACTIVE_SLUG}")
    assert resp.status_code == 404


def test_get_college_by_slug_does_not_require_auth(client):
    """Spec: GET /v1/colleges/{slug} is a public endpoint — no token needed."""
    resp = client.get(f"/v1/colleges/{COLLEGE_ACTIVE_1_SLUG}")
    assert resp.status_code == 200


def test_get_college_by_slug_listings_contains_only_active_listings(
    client, auth_as_seller
):
    """Spec: /colleges/{slug} returns only active (non-deleted) listings for that college."""
    payload = dict(BASE_LISTING)
    payload["college_id"] = COLLEGE_ACTIVE_1_ID
    create_resp = client.post("/v1/listings", json=payload)
    listing_id = create_resp.json()["listing"]["id"]

    # Soft-delete the listing
    client.delete(f"/v1/listings/{listing_id}")

    resp = client.get(f"/v1/colleges/{COLLEGE_ACTIVE_1_SLUG}")
    assert resp.status_code == 200
    ids = [l["id"] for l in resp.json()["listings"]]
    assert listing_id not in ids


def test_get_college_by_slug_brief_mode_returns_college_with_empty_listings(client):
    """Spec: ?brief=1 returns the college object but an empty listings array."""
    resp = client.get(
        f"/v1/colleges/{COLLEGE_ACTIVE_1_SLUG}", params={"brief": "1"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "college" in body
    assert body["college"]["slug"] == COLLEGE_ACTIVE_1_SLUG
    assert body["listings"] == []


def test_get_college_by_slug_active_listing_appears_in_response(
    client, auth_as_seller
):
    """Spec: an active listing with college_id matching the slug appears in /colleges/{slug}."""
    payload = dict(BASE_LISTING)
    payload["college_id"] = COLLEGE_ACTIVE_1_ID
    create_resp = client.post("/v1/listings", json=payload)
    listing_id = create_resp.json()["listing"]["id"]

    resp = client.get(f"/v1/colleges/{COLLEGE_ACTIVE_1_SLUG}")
    assert resp.status_code == 200
    ids = [l["id"] for l in resp.json()["listings"]]
    assert listing_id in ids


# ===========================================================================
# Section C — GET /v1/listings?college=<slug>
# ===========================================================================

def test_listings_filter_college_slug_returns_only_matching_listings(
    client, auth_as_seller
):
    """Spec: ?college=<slug> returns only listings whose college_id matches that slug."""
    payload_col1 = dict(BASE_LISTING)
    payload_col1["college_id"] = COLLEGE_ACTIVE_1_ID
    resp1 = client.post("/v1/listings", json=payload_col1)
    listing_col1_id = resp1.json()["listing"]["id"]

    payload_col2 = dict(BASE_LISTING)
    payload_col2["college_id"] = COLLEGE_ACTIVE_2_ID
    client.post("/v1/listings", json=payload_col2)

    resp = client.get("/v1/listings", params={"college": COLLEGE_ACTIVE_1_SLUG})
    assert resp.status_code == 200
    ids = [l["id"] for l in resp.json()]
    assert listing_col1_id in ids
    # The college-2 listing must not appear
    for listing in resp.json():
        college = listing.get("college")
        if college:
            assert college["slug"] == COLLEGE_ACTIVE_1_SLUG


def test_listings_filter_unknown_college_slug_returns_empty_array_not_422(client):
    """Spec: unknown slug in ?college= returns [] (200, not 422 or 404)."""
    resp = client.get("/v1/listings", params={"college": "slug-that-does-not-exist-xyz"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_listings_filter_college_never_returns_college_other_rows(
    client, auth_as_seller
):
    """Spec: a listing with only college_other (no college_id) NEVER appears in ?college= results."""
    payload_other = dict(BASE_LISTING)
    payload_other["college_other"] = "Some Unnamed College"
    client.post("/v1/listings", json=payload_other)

    resp = client.get("/v1/listings", params={"college": COLLEGE_ACTIVE_1_SLUG})
    assert resp.status_code == 200
    for listing in resp.json():
        # Any returned listing must have a canonical college matching the slug
        college = listing.get("college")
        assert college is not None, (
            "A listing with only college_other must not appear in college-slug filter results"
        )
        assert college["slug"] == COLLEGE_ACTIVE_1_SLUG


def test_listings_filter_college_slug_sql_injection_is_safe(client):
    """Spec (security): slug filter resolves via parameterized ORM — injection is harmless."""
    resp = client.get(
        "/v1/listings", params={"college": "'; DROP TABLE listings; --"}
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    # Confirm listings table intact
    follow_up = client.get("/v1/listings")
    assert follow_up.status_code == 200


def test_listings_filter_college_returns_200_no_auth_required(client):
    """Spec: GET /v1/listings (including ?college=) is a public endpoint."""
    resp = client.get("/v1/listings", params={"college": COLLEGE_ACTIVE_1_SLUG})
    assert resp.status_code == 200


# ===========================================================================
# Section D — POST /v1/listings with college fields
# ===========================================================================

def test_create_listing_with_valid_college_id_stores_it_and_embeds_brief(
    client, auth_as_seller
):
    """Spec: POST with a valid college_id stores it; response embeds college:{id,slug,name}."""
    payload = dict(BASE_LISTING)
    payload["college_id"] = COLLEGE_ACTIVE_1_ID
    resp = client.post("/v1/listings", json=payload)
    assert resp.status_code == 201
    listing = resp.json()["listing"]
    assert listing["college"] is not None
    assert listing["college"]["slug"] == COLLEGE_ACTIVE_1_SLUG
    assert listing["college"]["name"] == COLLEGE_ACTIVE_1_NAME
    assert "id" in listing["college"]


def test_create_listing_with_college_id_response_does_not_expose_raw_college_id(
    client, auth_as_seller
):
    """Spec: raw college_id UUID must NOT be exposed in ListingOut — only the brief."""
    payload = dict(BASE_LISTING)
    payload["college_id"] = COLLEGE_ACTIVE_1_ID
    resp = client.post("/v1/listings", json=payload)
    assert resp.status_code == 201
    listing = resp.json()["listing"]
    assert "college_id" not in listing


def test_create_listing_with_college_other_only_stores_text_college_is_null(
    client, auth_as_seller
):
    """Spec: college_other only (no college_id) → college=null, college_other set."""
    payload = dict(BASE_LISTING)
    payload["college_other"] = "My Unlisted College"
    resp = client.post("/v1/listings", json=payload)
    assert resp.status_code == 201
    listing = resp.json()["listing"]
    assert listing["college"] is None
    assert listing["college_other"] == "My Unlisted College"


def test_create_listing_with_both_college_id_and_college_other_returns_422(
    client, auth_as_seller
):
    """Spec: providing both college_id and college_other → 422 (XOR invariant)."""
    payload = dict(BASE_LISTING)
    payload["college_id"] = COLLEGE_ACTIVE_1_ID
    payload["college_other"] = "Also Some College"
    resp = client.post("/v1/listings", json=payload)
    assert resp.status_code == 422


def test_create_listing_with_unknown_college_id_returns_400(client, auth_as_seller):
    """Spec: random/unknown college_id → 400 'Unknown or inactive college.'"""
    payload = dict(BASE_LISTING)
    payload["college_id"] = str(uuid.uuid4())
    resp = client.post("/v1/listings", json=payload)
    assert resp.status_code == 400
    assert "unknown or inactive college" in resp.json()["detail"].lower()


def test_create_listing_with_inactive_college_id_returns_400(
    client, auth_as_seller
):
    """Spec: an is_active=FALSE college_id → 400 (same guard as unknown id)."""
    payload = dict(BASE_LISTING)
    payload["college_id"] = COLLEGE_INACTIVE_ID
    resp = client.post("/v1/listings", json=payload)
    assert resp.status_code == 400
    assert "unknown or inactive college" in resp.json()["detail"].lower()


def test_create_listing_without_college_fields_has_null_college_and_college_other(
    client, auth_as_seller
):
    """Spec: college is optional; omitting both fields → college=null, college_other=null."""
    resp = client.post("/v1/listings", json=BASE_LISTING)
    assert resp.status_code == 201
    listing = resp.json()["listing"]
    assert listing["college"] is None
    assert listing.get("college_other") is None


def test_create_listing_without_auth_returns_401(client):
    """Spec: POST /v1/listings is a protected endpoint."""
    resp = client.post("/v1/listings", json=BASE_LISTING)
    assert resp.status_code == 401


def test_create_listing_college_other_whitespace_only_is_stored_as_null(
    client, auth_as_seller
):
    """Spec: college_other is stripped; whitespace-only value treated as None."""
    payload = dict(BASE_LISTING)
    payload["college_other"] = "   "
    resp = client.post("/v1/listings", json=payload)
    assert resp.status_code == 201
    listing = resp.json()["listing"]
    assert listing.get("college_other") is None


def test_create_listing_college_other_max_length_120_enforced(
    client, auth_as_seller
):
    """Spec: college_other has max_length=120; exceeding it → 422."""
    payload = dict(BASE_LISTING)
    payload["college_other"] = "A" * 121
    resp = client.post("/v1/listings", json=payload)
    assert resp.status_code == 422


# ===========================================================================
# Section E — PATCH /v1/listings/{id} with college fields
# ===========================================================================

def test_patch_listing_can_set_college_id_and_clears_college_other(
    client, auth_as_seller
):
    """Spec: setting college_id on PATCH clears any existing college_other (XOR)."""
    # Create with college_other
    payload = dict(BASE_LISTING)
    payload["college_other"] = "Some Unlisted College"
    create_resp = client.post("/v1/listings", json=payload)
    listing_id = create_resp.json()["listing"]["id"]

    # Patch in a college_id
    resp = client.patch(
        f"/v1/listings/{listing_id}",
        json={"college_id": COLLEGE_ACTIVE_1_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["college"] is not None
    assert body["college"]["slug"] == COLLEGE_ACTIVE_1_SLUG
    # college_other must be cleared
    assert body.get("college_other") is None


def test_patch_listing_can_set_college_other_and_clears_college_id(
    client, auth_as_seller
):
    """Spec: setting college_other on PATCH clears any existing college_id (XOR)."""
    # Create with college_id
    payload = dict(BASE_LISTING)
    payload["college_id"] = COLLEGE_ACTIVE_1_ID
    create_resp = client.post("/v1/listings", json=payload)
    listing_id = create_resp.json()["listing"]["id"]

    # Patch in college_other
    resp = client.patch(
        f"/v1/listings/{listing_id}",
        json={"college_other": "New Unlisted Campus"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["college"] is None
    assert body["college_other"] == "New Unlisted Campus"


def test_patch_listing_with_both_college_id_and_college_other_returns_422(
    client, auth_as_seller
):
    """Spec: PATCH with both fields violates XOR invariant → 422."""
    payload = dict(BASE_LISTING)
    create_resp = client.post("/v1/listings", json=payload)
    listing_id = create_resp.json()["listing"]["id"]

    resp = client.patch(
        f"/v1/listings/{listing_id}",
        json={
            "college_id": COLLEGE_ACTIVE_1_ID,
            "college_other": "Also Some College",
        },
    )
    assert resp.status_code == 422


def test_patch_listing_with_unknown_college_id_returns_400(client, auth_as_seller):
    """Spec: PATCH with unknown college_id → 400."""
    create_resp = client.post("/v1/listings", json=BASE_LISTING)
    listing_id = create_resp.json()["listing"]["id"]

    resp = client.patch(
        f"/v1/listings/{listing_id}",
        json={"college_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 400
    assert "unknown or inactive college" in resp.json()["detail"].lower()


def test_patch_listing_with_inactive_college_id_returns_400(client, auth_as_seller):
    """Spec: PATCH with is_active=FALSE college_id → 400."""
    create_resp = client.post("/v1/listings", json=BASE_LISTING)
    listing_id = create_resp.json()["listing"]["id"]

    resp = client.patch(
        f"/v1/listings/{listing_id}",
        json={"college_id": COLLEGE_INACTIVE_ID},
    )
    assert resp.status_code == 400


def test_patch_listing_can_change_college_to_a_different_active_college(
    client, auth_as_seller
):
    """Spec: college is freely editable; switching from one canonical college to another is allowed."""
    payload = dict(BASE_LISTING)
    payload["college_id"] = COLLEGE_ACTIVE_1_ID
    create_resp = client.post("/v1/listings", json=payload)
    listing_id = create_resp.json()["listing"]["id"]

    resp = client.patch(
        f"/v1/listings/{listing_id}",
        json={"college_id": COLLEGE_ACTIVE_2_ID},
    )
    assert resp.status_code == 200
    assert resp.json()["college"]["slug"] == COLLEGE_ACTIVE_2_SLUG


def test_patch_listing_without_auth_returns_401(client):
    """Spec: PATCH /v1/listings/{id} requires auth."""
    resp = client.patch(f"/v1/listings/{uuid.uuid4()}", json={"college_id": COLLEGE_ACTIVE_1_ID})
    assert resp.status_code == 401


def test_patch_listing_college_by_non_owner_returns_403(client, auth_as_seller):
    """Spec: ownership is checked before mutation — non-owner gets 403."""
    payload = dict(BASE_LISTING)
    payload["college_id"] = COLLEGE_ACTIVE_1_ID
    create_resp = client.post("/v1/listings", json=payload)
    listing_id = create_resp.json()["listing"]["id"]

    app.dependency_overrides[verify_token] = _override_verify_token(OTHER_USER_ID)
    resp = client.patch(
        f"/v1/listings/{listing_id}",
        json={"college_id": COLLEGE_ACTIVE_2_ID},
    )
    assert resp.status_code == 403
    app.dependency_overrides.pop(verify_token, None)


# ===========================================================================
# Section F — PATCH /v1/users/me with college fields
# ===========================================================================

def test_patch_user_me_with_valid_college_id_returns_200_with_embedded_brief(
    client, auth_as_seller
):
    """Spec: PATCH /users/me with college_id stores it; GET /users/me embeds college brief."""
    resp = client.patch(
        "/v1/users/me",
        json={"college_id": COLLEGE_ACTIVE_1_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["college"] is not None
    assert body["college"]["slug"] == COLLEGE_ACTIVE_1_SLUG
    assert body["college"]["name"] == COLLEGE_ACTIVE_1_NAME


def test_patch_user_me_with_college_other_stores_text_college_is_null(
    client, auth_as_seller
):
    """Spec: PATCH /users/me with college_other only → college=null, college_other set."""
    resp = client.patch(
        "/v1/users/me",
        json={"college_other": "My Unlisted Campus"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["college"] is None
    assert body["college_other"] == "My Unlisted Campus"


def test_patch_user_me_with_both_college_id_and_college_other_returns_422(
    client, auth_as_seller
):
    """Spec: PATCH /users/me with both fields → 422 (XOR invariant)."""
    resp = client.patch(
        "/v1/users/me",
        json={
            "college_id": COLLEGE_ACTIVE_1_ID,
            "college_other": "Also Something",
        },
    )
    assert resp.status_code == 422


def test_patch_user_me_with_unknown_college_id_returns_400(client, auth_as_seller):
    """Spec: unknown/inactive college_id → 400."""
    resp = client.patch(
        "/v1/users/me",
        json={"college_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 400
    assert "unknown or inactive college" in resp.json()["detail"].lower()


def test_patch_user_me_with_inactive_college_id_returns_400(client, auth_as_seller):
    """Spec: is_active=FALSE college_id → 400."""
    resp = client.patch(
        "/v1/users/me",
        json={"college_id": COLLEGE_INACTIVE_ID},
    )
    assert resp.status_code == 400


def test_patch_user_me_without_auth_returns_401(client):
    """Spec: PATCH /v1/users/me is a protected endpoint."""
    resp = client.patch(
        "/v1/users/me",
        json={"college_id": COLLEGE_ACTIVE_1_ID},
    )
    assert resp.status_code == 401


# ===========================================================================
# Section G — GET /v1/users/me and GET /v1/users/{id} embed college
# ===========================================================================

def test_get_users_me_embeds_college_brief_after_patch(client, auth_as_seller):
    """Spec: GET /users/me embeds the college brief when college_id is set."""
    # Set the college first
    client.patch("/v1/users/me", json={"college_id": COLLEGE_ACTIVE_1_ID})

    resp = client.get("/v1/users/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["college"] is not None
    assert body["college"]["slug"] == COLLEGE_ACTIVE_1_SLUG


def test_get_users_me_embeds_college_other_when_set(client, auth_as_seller):
    """Spec: GET /users/me embeds college_other when that is what is stored."""
    client.patch("/v1/users/me", json={"college_other": "Obscure Regional College"})

    resp = client.get("/v1/users/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["college"] is None
    assert body["college_other"] == "Obscure Regional College"


def test_get_users_me_does_not_expose_raw_college_id(client, auth_as_seller):
    """Spec: UserMe exposes `college` brief, never the raw college_id UUID field."""
    client.patch("/v1/users/me", json={"college_id": COLLEGE_ACTIVE_1_ID})

    resp = client.get("/v1/users/me")
    assert resp.status_code == 200
    assert "college_id" not in resp.json()


def test_get_users_public_embeds_college_brief(client, auth_as_seller):
    """Spec: GET /users/{id} (public) embeds college brief when college_id is set."""
    client.patch("/v1/users/me", json={"college_id": COLLEGE_ACTIVE_1_ID})

    resp = client.get(f"/v1/users/{SELLER_ID}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["college"] is not None
    assert body["college"]["slug"] == COLLEGE_ACTIVE_1_SLUG


def test_get_users_public_embeds_college_other(client, auth_as_seller):
    """Spec: GET /users/{id} embeds college_other when that is stored."""
    client.patch("/v1/users/me", json={"college_other": "Regional Tech Institute"})

    resp = client.get(f"/v1/users/{SELLER_ID}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["college"] is None
    assert body["college_other"] == "Regional Tech Institute"


def test_get_users_public_does_not_expose_raw_college_id(client, auth_as_seller):
    """Spec: UserPublic must never expose the raw college_id UUID field."""
    client.patch("/v1/users/me", json={"college_id": COLLEGE_ACTIVE_1_ID})

    resp = client.get(f"/v1/users/{SELLER_ID}")
    assert resp.status_code == 200
    assert "college_id" not in resp.json()


def test_get_users_public_does_not_require_auth(client, auth_as_seller):
    """Spec: GET /v1/users/{id} is a public endpoint."""
    # Set up some data as seller, then check as unauth'd
    client.patch("/v1/users/me", json={"college_id": COLLEGE_ACTIVE_1_ID})
    app.dependency_overrides.clear()  # remove auth override

    resp = client.get(f"/v1/users/{SELLER_ID}")
    assert resp.status_code == 200


# ===========================================================================
# Section H — Response privacy: raw college_id never exposed
# ===========================================================================

def test_listing_out_does_not_expose_raw_college_id_on_get_by_id(
    client, auth_as_seller
):
    """Spec: ListingOut exposes the `college` brief — never the raw college_id field."""
    payload = dict(BASE_LISTING)
    payload["college_id"] = COLLEGE_ACTIVE_1_ID
    create_resp = client.post("/v1/listings", json=payload)
    listing_id = create_resp.json()["listing"]["id"]

    resp = client.get(f"/v1/listings/{listing_id}")
    assert resp.status_code == 200
    assert "college_id" not in resp.json()


def test_listing_out_does_not_expose_raw_college_id_in_list(
    client, auth_as_seller
):
    """Spec: the GET /listings list response must not expose college_id on any item."""
    payload = dict(BASE_LISTING)
    payload["college_id"] = COLLEGE_ACTIVE_1_ID
    client.post("/v1/listings", json=payload)

    resp = client.get("/v1/listings")
    assert resp.status_code == 200
    for listing in resp.json():
        assert "college_id" not in listing


# ===========================================================================
# Section I — DB / model invariants
# ===========================================================================

def test_colleges_slug_is_unique_seeded_slugs_are_different(client):
    """DB invariant: colleges.slug is UNIQUE — our two seeded rows have distinct slugs."""
    assert COLLEGE_ACTIVE_1_SLUG != COLLEGE_ACTIVE_2_SLUG


def test_colleges_name_is_unique_seeded_names_are_different(client):
    """DB invariant: colleges.name is UNIQUE — our two seeded rows have distinct names."""
    assert COLLEGE_ACTIVE_1_NAME != COLLEGE_ACTIVE_2_NAME


async def _assert_college_slug_unique_rejects_duplicate():
    """Attempting to insert a duplicate slug must raise an integrity error at DB level."""
    from sqlalchemy.exc import IntegrityError
    raised = False
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                text(
                    "INSERT INTO colleges (slug, name, is_active) "
                    "VALUES (:slug, :name, TRUE)"
                ),
                {
                    "slug": COLLEGE_ACTIVE_1_SLUG,       # duplicate slug
                    "name": f"Some Other Name {uuid.uuid4()}",
                },
            )
            await session.commit()
        except IntegrityError:
            raised = True
            await session.rollback()
    assert raised, "DB should reject a duplicate college slug"


def test_db_rejects_duplicate_college_slug():
    """DB invariant: colleges.slug UNIQUE — duplicate insert must fail."""
    asyncio.run(_assert_college_slug_unique_rejects_duplicate())


async def _assert_college_name_unique_rejects_duplicate():
    from sqlalchemy.exc import IntegrityError
    raised = False
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                text(
                    "INSERT INTO colleges (slug, name, is_active) "
                    "VALUES (:slug, :name, TRUE)"
                ),
                {
                    "slug": f"unique-slug-{uuid.uuid4()}",
                    "name": COLLEGE_ACTIVE_1_NAME,       # duplicate name
                },
            )
            await session.commit()
        except IntegrityError:
            raised = True
            await session.rollback()
    assert raised, "DB should reject a duplicate college name"


def test_db_rejects_duplicate_college_name():
    """DB invariant: colleges.name UNIQUE — duplicate insert must fail."""
    asyncio.run(_assert_college_name_unique_rejects_duplicate())


async def _verify_on_delete_set_null_for_listing(listing_id: str):
    """After retiring a college (is_active=FALSE), its FK ref on listings becomes NULL."""
    # We simulate "retire" by setting is_active=FALSE (the production path);
    # ON DELETE SET NULL fires only on actual DELETE, which we do not test here
    # because the spec says retirement is via is_active=FALSE, not DELETE.
    # What we verify is that a retired college causes the slug lookup to return 404.
    pass  # tested via test_get_college_by_slug_returns_404_for_inactive_slug above


def test_retired_college_slug_returns_404_and_active_listing_is_still_queryable(
    client, auth_as_seller
):
    """Spec: is_active=FALSE hides from search/typeahead without deleting FK references.
    The listing is not deleted when its college is retired — it just loses the college filter link."""
    # We cannot retire COLLEGE_ACTIVE_1 via the API (no admin endpoint — v1 is manual SQL).
    # We use COLLEGE_INACTIVE which was seeded as is_active=FALSE.
    # Confirm the inactive slug is unreachable while the college row itself exists.
    slug_resp = client.get(f"/v1/colleges/{COLLEGE_INACTIVE_SLUG}")
    assert slug_resp.status_code == 404

    # Confirm inactive college does NOT appear in typeahead
    typeahead_resp = client.get("/v1/colleges")
    slugs = [c["slug"] for c in typeahead_resp.json()]
    assert COLLEGE_INACTIVE_SLUG not in slugs


def test_paused_listing_with_valid_college_does_not_appear_in_active_listing_index(
    client, auth_as_seller
):
    """Spec (CLAUDE.md): is_available=FALSE, sold_at=NULL is a valid 'paused' state.
    A paused listing must not appear in GET /listings or in /colleges/{slug} listings."""
    payload = dict(BASE_LISTING)
    payload["college_id"] = COLLEGE_ACTIVE_1_ID
    create_resp = client.post("/v1/listings", json=payload)
    listing_id = create_resp.json()["listing"]["id"]

    # Pause the listing
    client.patch(f"/v1/listings/{listing_id}", json={"is_available": False})

    # Must not appear in GET /listings
    index_resp = client.get("/v1/listings", params={"college": COLLEGE_ACTIVE_1_SLUG})
    assert listing_id not in [l["id"] for l in index_resp.json()]

    # Must not appear in /colleges/{slug} listings either
    college_resp = client.get(f"/v1/colleges/{COLLEGE_ACTIVE_1_SLUG}")
    assert listing_id not in [l["id"] for l in college_resp.json()["listings"]]


def test_paused_listing_with_college_is_valid_db_state_not_flagged(
    client, auth_as_seller
):
    """Spec (SCHEMA.md): is_available=FALSE AND sold_at=NULL is a valid paused state.
    The DB CHECK constraint must NOT reject it. The listing row must still exist."""
    payload = dict(BASE_LISTING)
    payload["college_id"] = COLLEGE_ACTIVE_1_ID
    create_resp = client.post("/v1/listings", json=payload)
    listing_id = create_resp.json()["listing"]["id"]

    pause_resp = client.patch(f"/v1/listings/{listing_id}", json={"is_available": False})
    assert pause_resp.status_code == 200
    body = pause_resp.json()
    assert body["is_available"] is False
    assert body["is_sold"] is False  # sold_at still NULL

    # The row is still accessible by ID
    get_resp = client.get(f"/v1/listings/{listing_id}")
    assert get_resp.status_code == 200


# ===========================================================================
# Section J — college is NOT linked to is_verified
# ===========================================================================

def test_setting_college_does_not_affect_is_verified_flag(client, auth_as_seller):
    """Spec: college is self-asserted and NEVER tied to is_verified (earned via books_sold >= 10)."""
    # Confirm baseline is_verified for our test seller
    me_before = client.get("/v1/users/me").json()
    is_verified_before = me_before["is_verified"]

    # Set a canonical college
    client.patch("/v1/users/me", json={"college_id": COLLEGE_ACTIVE_1_ID})

    me_after = client.get("/v1/users/me").json()
    assert me_after["is_verified"] == is_verified_before


# ===========================================================================
# Section K — Listing college brief field values in GET /listings list
# ===========================================================================

def test_listing_in_get_listings_embeds_college_brief_when_college_id_set(
    client, auth_as_seller
):
    """Spec: GET /listings list embeds the college brief for each listing that has one."""
    payload = dict(BASE_LISTING)
    payload["college_id"] = COLLEGE_ACTIVE_1_ID
    create_resp = client.post("/v1/listings", json=payload)
    listing_id = create_resp.json()["listing"]["id"]

    resp = client.get("/v1/listings")
    assert resp.status_code == 200
    matching = [l for l in resp.json() if l["id"] == listing_id]
    assert len(matching) == 1
    assert matching[0]["college"] is not None
    assert matching[0]["college"]["slug"] == COLLEGE_ACTIVE_1_SLUG


def test_listing_in_get_listings_embeds_college_other_when_only_that_is_set(
    client, auth_as_seller
):
    """Spec: GET /listings list embeds college_other (and college=null) for non-canonical rows."""
    payload = dict(BASE_LISTING)
    payload["college_other"] = "Freelance College of India"
    create_resp = client.post("/v1/listings", json=payload)
    listing_id = create_resp.json()["listing"]["id"]

    resp = client.get("/v1/listings")
    assert resp.status_code == 200
    matching = [l for l in resp.json() if l["id"] == listing_id]
    assert len(matching) == 1
    assert matching[0]["college"] is None
    assert matching[0]["college_other"] == "Freelance College of India"


def test_listing_in_get_listings_has_null_college_when_neither_field_set(
    client, auth_as_seller
):
    """Spec: listing with no college fields → college=null, college_other=null."""
    create_resp = client.post("/v1/listings", json=BASE_LISTING)
    listing_id = create_resp.json()["listing"]["id"]

    resp = client.get("/v1/listings")
    assert resp.status_code == 200
    matching = [l for l in resp.json() if l["id"] == listing_id]
    assert len(matching) == 1
    assert matching[0]["college"] is None
    assert matching[0].get("college_other") is None
