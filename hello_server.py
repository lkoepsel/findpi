from flask import Flask, request, render_template, abort
from datetime import datetime
import sqlite3
import os
import argparse
from datetime import datetime, timezone
import time

app = Flask(__name__)

# Configuration
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"
PORT = int(os.environ.get("PORT", 5001))
DATABASE = "messages.db"


def init_db():
    """Initialize the SQLite database and create the messages table if it doesn't exist."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS messages
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         text TEXT NOT NULL,
         ip TEXT NOT NULL,
         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
    """
    )
    conn.commit()
    conn.close()


def get_messages():
    """Retrieve all messages from the database."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT text, ip, timestamp FROM messages ORDER BY timestamp DESC")
    messages = []
    for row in c.fetchall():
        # Convert timestamp string to datetime for formatting
        timestamp = datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S")
        # Format as month/day/year hour:minute
        formatted_time = timestamp.strftime("%m/%d/%Y %H:%M")
        messages.append({"text": row[0], "ip": row[1], "timestamp": formatted_time})
    conn.close()
    return messages


def clean_test_entries():
    """Remove entries that were created during unit testing."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # Remove entries from common test IPs and those containing test markers
    c.execute(
        """DELETE FROM messages 
                WHERE ip IN ('127.0.0.1', 'testclient') 
                OR text LIKE '%test%' 
                OR text LIKE '%unittest%' """
    )
    deleted_count = c.rowcount
    conn.commit()
    conn.close()
    if deleted_count > 0:
        print(f"Cleaned {deleted_count} test entries from database")


def reset_database():
    """Reset the database by dropping and recreating the messages table."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS messages")
    conn.commit()
    print("Database has been reset")
    conn.close()
    init_db()  # Recreate the table


@app.route("/", methods=["POST"])
def receive_text():
    text = request.form.get("text", "").strip()
    if not text:
        abort(400, description="Text cannot be empty")

    if len(text) > 1000:  # Limit text length
        abort(400, description="Text too long (max 1000 characters)")

    try:
        ip = request.remote_addr

        # Store in database with local time
        local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute(
            "INSERT INTO messages (text, ip, timestamp) VALUES (?, ?, ?)",
            (text, ip, local_time),
        )
        conn.commit()
        conn.close()

        print(f"Received text: {text} from IP: {ip}")
        return "Data received successfully", 200

    except Exception as e:
        print(f"Error processing request: {str(e)}")
        abort(500, description="Internal server error")


@app.route("/", methods=["GET"])
def display_text():
    try:
        messages = get_messages()
        return render_template("index.html", received_data=messages)
    except Exception as e:
        print(f"Error retrieving messages: {str(e)}")
        abort(500, description="Internal server error")


@app.errorhandler(400)
def bad_request(e):
    return str(e), 400


@app.errorhandler(500)
def server_error(e):
    return str(e), 500


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run the hello server")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset the database before starting the server",
    )
    args = parser.parse_args()

    # Reset database if requested
    if args.reset:
        reset_database()
    else:
        init_db()  # Initialize database on startup
        clean_test_entries()  # Clean test entries before starting

    app.run(
        host="0.0.0.0",  # Accept connections from any network interface
        port=PORT,
        debug=DEBUG,
    )
