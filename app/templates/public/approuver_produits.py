import psycopg2

DATABASE_URL = "postgresql://neondb_owner:npg_vORLNxDEU0k6@ep-snowy-snow-b587omnv-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("""
        UPDATE public.investment_products
        SET status = 'approved'
        WHERE status != 'approved'
        RETURNING id, name, status;
    """)

    products = cur.fetchall()
    conn.commit()

    print("\n✅ PRODUITS APPROUVÉS AVEC SUCCÈS !\n")

    for p in products:
        print(f"ID : {p[0]} | Nom : {p[1]} | Statut : {p[2]}")

    print(f"\nTotal de produits modifiés : {len(products)}")

    cur.close()
    conn.close()

except Exception as e:
    print("❌ Erreur :", e)