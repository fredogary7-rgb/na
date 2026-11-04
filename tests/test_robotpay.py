import psycopg2

DATABASE_URL = "postgresql://neondb_owner:npg_vORLNxDEU0k6@ep-snowy-snow-b587omnv-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
    SELECT id, name, status
    FROM public.investment_products
    ORDER BY id;
""")

print("\n📋 LISTE DES PRODUITS\n")

for product in cur.fetchall():
    print(f"ID : {product[0]} | Nom : {product[1]} | Statut : {product[2]}")

cur.close()
conn.close()