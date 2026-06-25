"""Add state to listings & users; backfill state/city from legacy cities

Adds a nullable state/UT column to both tables. New listings require state +
city (a district within that state) at the app layer; existing rows are
best-effort backfilled by mapping each legacy free-text city to its igod
state + district. Cities that map cleanly keep their name; a few are
normalised to the containing district (e.g. Navi Mumbai -> Thane, Kochi ->
Ernakulam, Noida -> Gautam Buddha Nagar). Unmapped rows keep their city and
get a NULL state, to be fixed by the owner on next edit.

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

# (legacy_city, state, district) — validated against igod data at build time.
CITY_BACKFILL = [
    ("Agra", "Uttar Pradesh", "Agra"),
    ("Ahmedabad", "Gujarat", "Ahmedabad"),
    ("Ajmer", "Rajasthan", "Ajmer"),
    ("Amritsar", "Punjab", "Amritsar"),
    ("Bengaluru", "Karnataka", "Bengaluru Urban"),
    ("Bhopal", "Madhya Pradesh", "Bhopal"),
    ("Bhubaneswar", "Odisha", "Khordha"),
    ("Chandigarh", "Chandigarh", "Chandigarh"),
    ("Chennai", "Tamil Nadu", "Chennai"),
    ("Coimbatore", "Tamil Nadu", "Coimbatore"),
    ("Dehradun", "Uttarakhand", "Dehradun"),
    ("Delhi", "Delhi", "New Delhi"),
    ("Dhanbad", "Jharkhand", "Dhanbad"),
    ("Durgapur", "West Bengal", "Paschim Bardhaman"),
    ("Faridabad", "Haryana", "Faridabad"),
    ("Ghaziabad", "Uttar Pradesh", "Ghaziabad"),
    ("Gorakhpur", "Uttar Pradesh", "Gorakhpur"),
    ("Guntur", "Andhra Pradesh", "Guntur"),
    ("Gurugram", "Haryana", "Gurugram"),
    ("Guwahati", "Assam", "Kamrup Metro"),
    ("Gwalior", "Madhya Pradesh", "Gwalior"),
    ("Hyderabad", "Telangana", "Hyderabad"),
    ("Indore", "Madhya Pradesh", "Indore"),
    ("Jabalpur", "Madhya Pradesh", "Jabalpur"),
    ("Jaipur", "Rajasthan", "Jaipur"),
    ("Jalandhar", "Punjab", "Jalandhar"),
    ("Jammu", "Jammu and Kashmir", "Jammu"),
    ("Jamshedpur", "Jharkhand", "East Singhbum"),
    ("Jodhpur", "Rajasthan", "Jodhpur"),
    ("Kanpur", "Uttar Pradesh", "Kanpur Nagar"),
    ("Kochi", "Kerala", "Ernakulam"),
    ("Kolkata", "West Bengal", "Kolkata"),
    ("Kota", "Rajasthan", "Kota"),
    ("Kozhikode", "Kerala", "Kozhikode"),
    ("Lucknow", "Uttar Pradesh", "Lucknow"),
    ("Ludhiana", "Punjab", "Ludhiana"),
    ("Madurai", "Tamil Nadu", "Madurai"),
    ("Meerut", "Uttar Pradesh", "Meerut"),
    ("Mumbai", "Maharashtra", "Mumbai"),
    ("Mysuru", "Karnataka", "Mysuru"),
    ("Nagpur", "Maharashtra", "Nagpur"),
    ("Nashik", "Maharashtra", "Nashik"),
    ("Navi Mumbai", "Maharashtra", "Thane"),
    ("New Delhi", "Delhi", "New Delhi"),
    ("Noida", "Uttar Pradesh", "Gautam Buddha Nagar"),
    ("Patna", "Bihar", "Patna"),
    ("Prayagraj", "Uttar Pradesh", "Prayagraj"),
    ("Pune", "Maharashtra", "Pune"),
    ("Raipur", "Chhattisgarh", "Raipur"),
    ("Rajkot", "Gujarat", "Rajkot"),
    ("Ranchi", "Jharkhand", "Ranchi"),
    ("Shimla", "Himachal Pradesh", "Shimla"),
    ("Sikar", "Rajasthan", "Sikar"),
    ("Siliguri", "West Bengal", "Darjeeling"),
    ("Srinagar", "Jammu and Kashmir", "Srinagar"),
    ("Surat", "Gujarat", "Surat"),
    ("Thane", "Maharashtra", "Thane"),
    ("Thiruvananthapuram", "Kerala", "Thiruvananthapuram"),
    ("Thrissur", "Kerala", "Thrissur"),
    ("Tirupati", "Andhra Pradesh", "Tirupati"),
    ("Udaipur", "Rajasthan", "Udaipur"),
    ("Vadodara", "Gujarat", "Vadodara"),
    ("Varanasi", "Uttar Pradesh", "Varanasi"),
    ("Vijayawada", "Andhra Pradesh", "Ntr"),
    ("Visakhapatnam", "Andhra Pradesh", "Visakhapatnam"),
    ("Warangal", "Telangana", "Warangal"),
]


def upgrade() -> None:
    op.add_column("listings", sa.Column("state", sa.String(), nullable=True))
    op.add_column("users", sa.Column("state", sa.String(), nullable=True), schema="public")

    conn = op.get_bind()
    for table in ("listings", "public.users"):
        for old_city, state, district in CITY_BACKFILL:
            conn.execute(
                sa.text(
                    f"UPDATE {table} SET state = :state, city = :district "
                    "WHERE city = :old_city AND state IS NULL"
                ),
                {"state": state, "district": district, "old_city": old_city},
            )


def downgrade() -> None:
    # City normalisation is not reversed; only the new column is dropped.
    op.drop_column("users", "state", schema="public")
    op.drop_column("listings", "state")
