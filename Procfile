web: sh -c "flask db upgrade && flask seed-products && gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 --access-logfile -"
scheduler: python scheduler.py
