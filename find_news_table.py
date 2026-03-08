from config.db_connector import DBConnector

db = DBConnector()
db.conectar()

query = """
SELECT table_name, column_name 
FROM information_schema.columns 
WHERE column_name ILIKE '%titular%' 
   OR column_name ILIKE '%noticia%' 
   OR column_name ILIKE '%news%'
   OR column_name ILIKE '%titulo%';
"""
db.cursor.execute(query)
results = db.cursor.fetchall()
print("Found columns:")
for r in results:
    print(f"Table: {r[0]} | Column: {r[1]}")

db.desconectar()
