import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    load_dotenv()

class Config:
    """Application configuration parameters loaded from environment variables."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-dev-secret-key-change-in-production')
    
    # MySQL Database Configuration
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'library')
    
    # Administrator Credentials
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    # Generate a hashed representation of the admin password
    ADMIN_PLAIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    ADMIN_PASSWORD_HASH = generate_password_hash(ADMIN_PLAIN_PASSWORD)


def get_db_connection():
    """
    Establish and return a connection to the existing MySQL database.
    Raises mysql.connector.Error if connection fails.
    """
    try:
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci',
            autocommit=False  # Explicit transaction control
        )
        return connection
    except Error as e:
        print(f"[ERROR] Database connection failed: {e}")
        raise e


def test_db_connection():
    """Utility to test connection status during startup."""
    try:
        conn = get_db_connection()
        if conn.is_connected():
            cursor = conn.cursor()
            cursor.execute("SELECT DATABASE();")
            current_db = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            return True, f"Successfully connected to database '{current_db}'."
        return False, "Database connection could not be established."
    except Exception as ex:
        return False, str(ex)
