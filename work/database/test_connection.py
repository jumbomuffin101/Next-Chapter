
from sqlalchemy import text
from .database import engine


def main():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("Database connection successful:", result.scalar())

    except Exception as error:
        print("Database connection failed.")
        print("Error type:", type(error).__name__)
        print(
            "Check the database password, connection host, "
            "port, and network access."
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
