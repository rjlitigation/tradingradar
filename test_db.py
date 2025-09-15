from utils.storage import fetch_all

rows = fetch_all()
for r in rows:
    print(r)
