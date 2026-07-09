"""
Seed data untuk development.
Jalankan sekali setelah init_db().
"""
import asyncio
from uuid import UUID
from backend.db.database import AsyncSessionLocal
from backend.db.models import Hotel

DUMMY_HOTEL_ID = "00000000-0000-0000-0000-000000000001"

async def seed_dev_data():
    async with AsyncSessionLocal() as db:
        # Cek apakah sudah ada
        from sqlalchemy import select
        result = await db.execute(
            select(Hotel).where(
                Hotel.slug == "demo"
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print("Dummy hotel sudah ada, skip")
            return
        
        # Insert dummy hotel
        hotel = Hotel(
            id=UUID(DUMMY_HOTEL_ID),
            name="Hotel Demo Metland",
            slug="demo",
            waha_session="demo",
            is_active=True
        )
        db.add(hotel)
        await db.commit()
        print(f"Dummy hotel created: {hotel.name}")
        
        # Insert default policies untuk hotel dummy
        from backend.db.models import HotelPolicy
        import json

        policies = [
            {
                "hotel_id": DUMMY_HOTEL_ID,
                "policy_type": "complaint_routing",
                "rules": {
                    "fasilitas": "engineering",
                    "kebersihan": "housekeeping",
                    "makanan": "fnb",
                    "pelayanan": "front_office",
                    "kebisingan": "front_office",
                    "lainnya": "front_office"
                }
            },
            {
                "hotel_id": DUMMY_HOTEL_ID,
                "policy_type": "upsell",
                "rules": {
                    "breakfast": {
                        "name": "Paket Sarapan",
                        "price": 100000,
                        "unit": "per orang per malam"
                    },
                    "airport_transfer": {
                        "name": "Antar Jemput Bandara",
                        "price": 250000,
                        "unit": "per trip"
                    },
                    "room_decoration": {
                        "name": "Dekorasi Kamar",
                        "price": 350000,
                        "unit": "per kamar"
                    }
                }
            }
        ]

        for p in policies:
            existing_policy = await db.execute(
                select(HotelPolicy).where(
                    HotelPolicy.hotel_id == UUID(DUMMY_HOTEL_ID),
                    HotelPolicy.policy_type == p["policy_type"]
                )
            )
            if not existing_policy.scalar_one_or_none():
                policy = HotelPolicy(
                    hotel_id=UUID(p["hotel_id"]),
                    policy_type=p["policy_type"],
                    rules=p["rules"],
                    is_active=True
                )
                db.add(policy)

        await db.commit()
        print("Default policies created")

if __name__ == "__main__":
    asyncio.run(seed_dev_data())