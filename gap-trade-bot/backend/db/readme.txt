# Querying SQLite .db Files

You can query the .db (SQLite) files in this directory using either the command line or Python.

---

## 1. Using the Command Line (`sqlite3` CLI)

1. Open Terminal
2. Navigate to this directory:
   ```sh
   cd /Users/avinashchennamadhav/Documents/Projects/trading-advisor/trading_advisor/db
   ```
3. Open the database:
   ```sh
   sqlite3 your_database.db
   ```
   Replace `your_database.db` with the actual file name (e.g., `trades_db.db` or `ticker_details.db`).
4. Run SQL queries:
   - List tables:
     ```sql
     .tables
     ```
   - Show schema for a table:
     ```sql
     .schema table_name
     ```
   - Select data:
     ```sql
     SELECT * FROM table_name LIMIT 10;
     ```
   - Exit:
     ```sql
     .exit
     ```

---

## 2. Using Python

You can also query the database from a Python script or interactive shell:

```python
import sqlite3

# Connect to the database
conn = sqlite3.connect('db/your_database.db')  # adjust path as needed
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print(cursor.fetchall())

# Query data
cursor.execute("SELECT * FROM your_table LIMIT 10;")
for row in cursor.fetchall():
    print(row)

conn.close()
```

---

**Summary Table**

| Method      | How to Start                                      | Example Query                      |
|-------------|---------------------------------------------------|------------------------------------|
| CLI         | `sqlite3 your_database.db`                        | `SELECT * FROM table_name;`        |
| Python      | `import sqlite3` + connect + cursor               | `cursor.execute("SELECT ...")`     |

---

For more details, see the [SQLite documentation](https://sqlite.org/docs.html).
