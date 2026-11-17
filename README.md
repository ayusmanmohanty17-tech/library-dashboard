# Library Management System

A full-stack, responsive, and secure Library Management System built with **Python Flask**, **MySQL**, **HTML5**, **CSS3**, **JavaScript**, and **Bootstrap 5**.

This application directly connects to your existing MySQL database (`library`) without altering or dropping existing tables or records.

---

## 1. Features

- **Administrator Authentication**:
  - Secure session-based authentication with Werkzeug password hashing.
  - Protected administrative routes and CSRF protection on state-modifying requests.
- **Dynamic Admin Dashboard**:
  - Live statistics calculated directly from MySQL records: Total books, registered students, active loans, completed returns, and stock availability.
  - Interactive Chart.js charts and inventory status alerts.
- **Book Management (CRUD)**:
  - Add, browse, search (by Title, Author, ISBN), and filter books by stock availability.
  - Edit books with automatic quantity-to-availability consistency checks.
  - Safe deletion: blocks deletion if active loans or loan audit history exist.
- **Student Management (CRUD)**:
  - Register, edit, search (by name, email, phone), and view student records.
  - View dedicated borrowing history and active loan count per student.
  - Safe deletion preventing deletion of students with active loans.
- **Book Circulation (Issue & Return)**:
  - Select student and available book with real-time stock feedback.
  - Atomic database transactions: issuing decreases available stock by 1; returning marks `status = 'Returned'`, stamps `return_date`, and restores available stock by 1.
  - Prevention of duplicate return transactions.
- **Circulation & Borrowing History**:
  - Filter by Active Loans, Completed Returns, or All Records with full student and book metadata.
- **Analytical Reports**:
  - Top 10 most frequently borrowed books.
  - Top 10 students with the highest number of loans.
  - Visual distribution of available inventory vs. active circulation.
  - Schema extension proposal for overdue tracking and fine management.

---

## 2. Technology Stack

- **Backend**: Python 3.10+, Flask 3.x, Werkzeug, python-dotenv
- **Database**: MySQL Server 8.0, `mysql-connector-python`
- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5.3, Bootstrap Icons, Chart.js

---

## 3. Project Structure

```text
library_management/
│
├── app.py                  # Core Flask application and routes
├── config.py               # Configuration, DB connection, and credentials
├── requirements.txt        # Python dependency manifest
├── .env.example            # Template for environment variables
├── .env                    # Active local environment variables
├── README.md               # Complete documentation
│
├── static/
│   ├── css/
│   │   └── style.css       # Custom responsive stylesheet (Navy blue theme)
│   ├── js/
│   │   └── script.js       # Client-side dynamic interaction & modal handlers
│   └── images/             # Static image assets
│
└── templates/
    ├── base.html           # Master layout template (Sidebar, Topbar, Flash alerts)
    ├── login.html          # Admin sign-in screen
    ├── dashboard.html      # Live operational dashboard
    ├── books.html          # Books catalog, search and filters
    ├── add_book.html       # Add book form
    ├── edit_book.html      # Edit book form with quantity constraints
    ├── students.html       # Registered students directory
    ├── add_student.html    # Student registration form
    ├── edit_student.html   # Edit student details
    ├── student_history.html# Individual student borrowing profile
    ├── issue_book.html     # Transactional book issue interface
    ├── issued_books.html   # Circulation records & Return management
    └── reports.html        # Analytical reports & RFC schema extensions
```

---

## 4. Installation & Setup Instructions

### Step 1: Navigate to Project Directory
```powershell
cd library_management
```

### Step 2: Install Python Dependencies
```powershell
python -m pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env` (or verify the provided `.env`):
```powershell
Copy-Item .env.example .env
```

Configure your `.env` settings:
```ini
# Flask Secret Key
SECRET_KEY=9f82d1c3a7e4b506283749d01e2f3a4b5c6d7e8f90123456789abcdef0123456

# MySQL Database Connection
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=library

# Administrator Credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
```

---

## 5. Running the Application

Start the Flask development server:
```powershell
python app.py
```

The application will launch on:
```
http://127.0.0.1:5000/
```

### Default Administrator Credentials:
- **Username**: `admin`
- **Password**: `admin123`

---

## 6. Database Schema Reference

The system operates on the existing `library` database schema:

### `books`
- `id` INT PRIMARY KEY AUTO_INCREMENT
- `title` VARCHAR(150) NOT NULL
- `author` VARCHAR(100) NOT NULL
- `isbn` VARCHAR(50) UNIQUE
- `quantity` INT NOT NULL DEFAULT 1
- `available` INT NOT NULL DEFAULT 1
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

### `students`
- `id` INT PRIMARY KEY AUTO_INCREMENT
- `name` VARCHAR(100) NOT NULL
- `email` VARCHAR(100) UNIQUE
- `phone` VARCHAR(20)
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

### `issued_books`
- `id` INT PRIMARY KEY AUTO_INCREMENT
- `book_id` INT NOT NULL (Foreign Key -> `books.id`)
- `student_id` INT NOT NULL (Foreign Key -> `students.id`)
- `issue_date` DATETIME DEFAULT CURRENT_TIMESTAMP
- `return_date` DATETIME NULL
- `status` ENUM('Issued', 'Returned') DEFAULT 'Issued'

---

## 7. Common Troubleshooting

1. **Access denied for user 'root'@'localhost'**:
   - Verify that your MySQL server password in `.env` matches your MySQL root account password.
2. **Can't connect to MySQL server on 'localhost'**:
   - Ensure the MySQL Windows service (`MySQL80`) is running. Check with `Get-Service -Name *mysql*` in PowerShell.
3. **Cannot delete book/student**:
   - The application strictly enforces referential integrity. Books or students with active loans or existing history records cannot be deleted to avoid violating foreign key constraints.
