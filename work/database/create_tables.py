
from .database import Base, engine
from . import models


def main():
    print("Creating PostgreSQL tables...")

    Base.metadata.create_all(bind=engine)

    print("\nRegistered tables:")

    for table in Base.metadata.sorted_tables:
        print(f"Ready: {table.name}")

    print("\nDatabase schema initialized successfully!")


if __name__ == "__main__":
    main()
