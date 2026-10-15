import os
import mysql.connector
import pandas as pd

#  MySQL connection
conn = mysql.connector.connect(
    host="localhost",       
    user="root",            
    password=os.getenv("MYSQL_PASSWORD", ""),
    database="agewell_db"
)

# 2. Verify connection
if conn.is_connected():
    print("✅ Connected to MySQL successfully!\n")

# 3. Fetch data from the table
query = "SELECT * FROM health_records;"
df = pd.read_sql(query, conn)

# 4. Display sample data
print("📊 Sample Records from Database:\n")
print(df.head())

# 5. Display summary statistics
print("\n🔎 Data Summary:\n")
print(df.describe())

# 6. Close the connection
conn.close()
print("\n🔒 MySQL connection closed.")
