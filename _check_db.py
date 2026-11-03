import psycopg2
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

try:
    cur.execute("""
        UPDATE "user"
        SET is_admin = TRUE
        WHERE username = %s
        RETURNING id, username, is_admin;
    """, ("91369977",))

    user = cur.fetchone()

    if user:
        conn.commit()
        print("✅ Utilisateur promu administrateur !")
        print(f"ID : {user[0]}")
        print(f"Username : {user[1]}")
        print(f"Admin : {user[2]}")
    else:
        conn.rollback()
        print("❌ Utilisateur introuvable.")

except Exception as e:
    conn.rollback()
    print(f"Erreur : {e}")

finally:
    cur.close()
    conn.close()