import psycopg2

DATABASE_URL = "postgresql://neondb_owner:npg_vORLNxDEU0k6@ep-snowy-snow-b587omnv-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, full_name, phone_number, role
        FROM public.users
        WHERE phone_number = %s;
    """, ("+22891369977",))

    user = cur.fetchone()

    if user:
        print("\n📋 VÉRIFICATION DU COMPTE")
        print("ID :", user[0])
        print("Nom :", user[1])
        print("Téléphone :", user[2])
        print("Rôle actuel :", user[3])

        if user[3] == "admin":
            print("\n✅ CE COMPTE EST ADMINISTRATEUR !")
        else:
            cur.execute("""
                UPDATE public.users
                SET role = 'admin'
                WHERE phone_number = %s
                RETURNING id, full_name, phone_number, role;
            """, ("+22891369977",))

            updated_user = cur.fetchone()
            conn.commit()

            print("\n✅ PROMOTION RÉUSSIE :", updated_user)

    else:
        print("❌ Utilisateur introuvable.")

    cur.close()
    conn.close()

except Exception as e:
    print("❌ Erreur :", e)