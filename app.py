import os
import secrets
from functools import wraps
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, abort
)
from werkzeug.security import check_password_hash
import mysql.connector
from mysql.connector import Error

from config import Config, get_db_connection

app = Flask(__name__)
app.config.from_object(Config)


# =====================================================================
# Security Helpers & Decorators
# =====================================================================

def login_required(f):
    """Decorator to enforce administrator authentication on routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash("Please sign in to access the administrator panel.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def get_csrf_token():
    """Generate or retrieve a CSRF token stored in the session."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(24)
    return session['_csrf_token']


@app.context_processor
def inject_globals():
    """Inject global variables into all Jinja2 templates."""
    return {
        'csrf_token': get_csrf_token(),
        'current_admin': session.get('admin_username', 'Administrator'),
        'current_year': datetime.now().year,
        'now': datetime.now()
    }


@app.template_filter('datetimeformat')
def datetimeformat_filter(value, format='%b %d, %Y %I:%M %p'):
    """Format datetime objects for presentation."""
    if value is None:
        return '—'
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime(format)


@app.before_request
def csrf_protect():
    """Verify CSRF token on all state-mutating POST requests."""
    if request.method == "POST":
        # Allow login form to generate and validate CSRF token seamlessly
        token = session.get('_csrf_token')
        form_token = request.form.get('csrf_token')
        if not token or token != form_token:
            flash("Security check failed (invalid or expired CSRF token). Please try again.", "danger")
            return redirect(request.referrer or url_for('dashboard'))


# =====================================================================
# Authentication Routes
# =====================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Administrator login handler."""
    if session.get('admin_logged_in'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Validate against configured administrator credentials
        if username == Config.ADMIN_USERNAME and check_password_hash(Config.ADMIN_PASSWORD_HASH, password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session['_csrf_token'] = secrets.token_hex(24)  # Cycle CSRF token on login
            flash(f"Welcome back, {username}! You have successfully logged in.", "success")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash("Invalid administrator username or password. Please verify credentials.", "danger")

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Administrator logout handler."""
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('login'))


# =====================================================================
# Dashboard Route
# =====================================================================

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    """Admin dashboard presenting live database statistics and activity."""
    conn = None
    stats = {
        'total_books_titles': 0,
        'total_books_copies': 0,
        'total_available_copies': 0,
        'total_issued_copies': 0,
        'total_students': 0,
        'currently_issued': 0,
        'returned_books': 0
    }
    recent_activity = []
    low_inventory_books = []

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Book statistics (aggregate from existing books table)
        cursor.execute("""
            SELECT 
                COUNT(*) AS total_titles,
                COALESCE(SUM(quantity), 0) AS total_copies,
                COALESCE(SUM(available), 0) AS total_available
            FROM books;
        """)
        book_res = cursor.fetchone()
        if book_res:
            stats['total_books_titles'] = book_res['total_titles']
            stats['total_books_copies'] = book_res['total_copies']
            stats['total_available_copies'] = book_res['total_available']
            stats['total_issued_copies'] = max(0, book_res['total_copies'] - book_res['total_available'])

        # 2. Student statistics
        cursor.execute("SELECT COUNT(*) AS total_students FROM students;")
        student_res = cursor.fetchone()
        if student_res:
            stats['total_students'] = student_res['total_students']

        # 3. Issued books status counts
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN status = 'Issued' THEN 1 ELSE 0 END), 0) AS currently_issued,
                COALESCE(SUM(CASE WHEN status = 'Returned' THEN 1 ELSE 0 END), 0) AS returned_books
            FROM issued_books;
        """)
        issue_res = cursor.fetchone()
        if issue_res:
            stats['currently_issued'] = issue_res['currently_issued']
            stats['returned_books'] = issue_res['returned_books']

        # 4. Recent borrowing activity (JOIN issued_books with books and students)
        cursor.execute("""
            SELECT 
                ib.id,
                ib.book_id,
                ib.student_id,
                ib.issue_date,
                ib.return_date,
                ib.status,
                b.title AS book_title,
                b.author AS book_author,
                s.name AS student_name,
                s.email AS student_email
            FROM issued_books ib
            JOIN books b ON ib.book_id = b.id
            JOIN students s ON ib.student_id = s.id
            ORDER BY ib.issue_date DESC
            LIMIT 5;
        """)
        recent_activity = cursor.fetchall()

        # 5. Low inventory books (available == 0 or low)
        cursor.execute("""
            SELECT id, title, author, isbn, quantity, available 
            FROM books 
            WHERE available = 0
            LIMIT 5;
        """)
        low_inventory_books = cursor.fetchall()

        cursor.close()
    except Error as e:
        flash(f"Database error loading dashboard metrics: {e}", "danger")
    finally:
        if conn and conn.is_connected():
            conn.close()

    return render_template(
        'dashboard.html',
        stats=stats,
        recent_activity=recent_activity,
        low_inventory_books=low_inventory_books
    )


# =====================================================================
# Book Management Routes
# =====================================================================

@app.route('/books')
@login_required
def books():
    """List, search and filter books."""
    search_query = request.args.get('search', '').strip()
    availability_filter = request.args.get('availability', 'all').strip()

    books_list = []
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        sql = "SELECT id, title, author, isbn, quantity, available, created_at FROM books WHERE 1=1"
        params = []

        if search_query:
            sql += " AND (title LIKE %s OR author LIKE %s OR isbn LIKE %s)"
            search_pattern = f"%{search_query}%"
            params.extend([search_pattern, search_pattern, search_pattern])

        if availability_filter == 'available':
            sql += " AND available > 0"
        elif availability_filter == 'unavailable':
            sql += " AND available = 0"

        sql += " ORDER BY id DESC"

        cursor.execute(sql, params)
        books_list = cursor.fetchall()

        # For each book, calculate active issued count
        for b in books_list:
            b['active_issued'] = max(0, b['quantity'] - b['available'])

        cursor.close()
    except Error as e:
        flash(f"Error retrieving books catalog: {e}", "danger")
    finally:
        if conn and conn.is_connected():
            conn.close()

    return render_template(
        'books.html',
        books=books_list,
        search_query=search_query,
        availability_filter=availability_filter
    )


@app.route('/books/add', methods=['GET', 'POST'])
@login_required
def add_book():
    """Register a new book in the catalog."""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        isbn = request.form.get('isbn', '').strip()
        quantity_str = request.form.get('quantity', '1').strip()

        # Validation
        errors = []
        if not title:
            errors.append("Book title is required.")
        elif len(title) > 150:
            errors.append("Book title cannot exceed 150 characters.")

        if not author:
            errors.append("Author name is required.")
        elif len(author) > 100:
            errors.append("Author name cannot exceed 100 characters.")

        if not isbn:
            errors.append("ISBN is required.")
        elif len(isbn) > 50:
            errors.append("ISBN cannot exceed 50 characters.")

        try:
            quantity = int(quantity_str)
            if quantity < 1:
                errors.append("Quantity must be at least 1.")
        except ValueError:
            errors.append("Quantity must be a valid whole number.")
            quantity = 1

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template('add_book.html', form_data=request.form)

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # Check ISBN uniqueness
            cursor.execute("SELECT id FROM books WHERE isbn = %s;", (isbn,))
            if cursor.fetchone():
                flash(f"A book with ISBN '{isbn}' already exists in the catalog.", "warning")
                cursor.close()
                return render_template('add_book.html', form_data=request.form)

            # Insert new book: available initially equals quantity
            insert_sql = """
                INSERT INTO books (title, author, isbn, quantity, available)
                VALUES (%s, %s, %s, %s, %s);
            """
            cursor.execute(insert_sql, (title, author, isbn, quantity, quantity))
            conn.commit()
            cursor.close()

            flash(f"Book '{title}' successfully added with {quantity} copies available.", "success")
            return redirect(url_for('books'))
        except Error as e:
            if conn:
                conn.rollback()
            flash(f"Database error while saving book: {e}", "danger")
        finally:
            if conn and conn.is_connected():
                conn.close()

    return render_template('add_book.html', form_data={})


@app.route('/books/edit/<int:book_id>', methods=['GET', 'POST'])
@login_required
def edit_book(book_id):
    """Edit existing book information while maintaining quantity and availability consistency."""
    conn = None
    book = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM books WHERE id = %s;", (book_id,))
        book = cursor.fetchone()
        cursor.close()
    except Error as e:
        flash(f"Database error: {e}", "danger")
        return redirect(url_for('books'))
    finally:
        if conn and conn.is_connected():
            conn.close()

    if not book:
        flash("The requested book was not found.", "warning")
        return redirect(url_for('books'))

    # Calculate currently issued copies
    issued_count = max(0, book['quantity'] - book['available'])

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        isbn = request.form.get('isbn', '').strip()
        quantity_str = request.form.get('quantity', str(book['quantity'])).strip()

        errors = []
        if not title:
            errors.append("Book title is required.")
        if not author:
            errors.append("Author name is required.")
        if not isbn:
            errors.append("ISBN is required.")

        try:
            new_quantity = int(quantity_str)
            if new_quantity < 1:
                errors.append("Quantity must be at least 1.")
            elif new_quantity < issued_count:
                errors.append(
                    f"Total quantity cannot be reduced below {issued_count}, "
                    f"because {issued_count} copies are currently issued to students."
                )
        except ValueError:
            errors.append("Quantity must be a valid whole number.")
            new_quantity = book['quantity']

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template('edit_book.html', book=book, issued_count=issued_count)

        # Calculate new available copies consistently
        new_available = new_quantity - issued_count

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # Check ISBN uniqueness if changed
            cursor.execute("SELECT id FROM books WHERE isbn = %s AND id != %s;", (isbn, book_id))
            if cursor.fetchone():
                flash(f"Another book is already registered with ISBN '{isbn}'.", "warning")
                cursor.close()
                return render_template('edit_book.html', book=book, issued_count=issued_count)

            update_sql = """
                UPDATE books 
                SET title = %s, author = %s, isbn = %s, quantity = %s, available = %s
                WHERE id = %s;
            """
            cursor.execute(update_sql, (title, author, isbn, new_quantity, new_available, book_id))
            conn.commit()
            cursor.close()

            flash(f"Book '{title}' updated successfully.", "success")
            return redirect(url_for('books'))
        except Error as e:
            if conn:
                conn.rollback()
            flash(f"Database error updating book: {e}", "danger")
        finally:
            if conn and conn.is_connected():
                conn.close()

    return render_template('edit_book.html', book=book, issued_count=issued_count)


@app.route('/books/delete/<int:book_id>', methods=['POST'])
@login_required
def delete_book(book_id):
    """Delete book record only if there are no active issued copies or foreign key constraint violations."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Check if book exists
        cursor.execute("SELECT title FROM books WHERE id = %s;", (book_id,))
        book = cursor.fetchone()
        if not book:
            flash("Book not found.", "warning")
            return redirect(url_for('books'))

        # 2. Check for active issued copies
        cursor.execute("""
            SELECT COUNT(*) AS active_cnt 
            FROM issued_books 
            WHERE book_id = %s AND status = 'Issued';
        """, (book_id,))
        active_check = cursor.fetchone()
        if active_check and active_check['active_cnt'] > 0:
            flash(
                f"Cannot delete '{book['title']}': there are currently {active_check['active_cnt']} active unreturned copy/copies.",
                "danger"
            )
            return redirect(url_for('books'))

        # 3. Check for historical borrowing records
        cursor.execute("""
            SELECT COUNT(*) AS history_cnt 
            FROM issued_books 
            WHERE book_id = %s;
        """, (book_id,))
        history_check = cursor.fetchone()
        if history_check and history_check['history_cnt'] > 0:
            flash(
                f"Cannot delete '{book['title']}': {history_check['history_cnt']} historical borrowing record(s) reference this book. "
                "Deleting it is prevented to preserve library audit integrity.",
                "warning"
            )
            return redirect(url_for('books'))

        # Safe to delete
        cursor.execute("DELETE FROM books WHERE id = %s;", (book_id,))
        conn.commit()
        cursor.close()
        flash(f"Book '{book['title']}' was deleted successfully.", "success")
    except Error as e:
        if conn:
            conn.rollback()
        flash(f"Database error deleting book: {e}", "danger")
    finally:
        if conn and conn.is_connected():
            conn.close()

    return redirect(url_for('books'))


# =====================================================================
# Student Management Routes
# =====================================================================

@app.route('/students')
@login_required
def students():
    """List and search registered students."""
    search_query = request.args.get('search', '').strip()
    students_list = []
    conn = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        sql = """
            SELECT 
                s.id, 
                s.name, 
                s.email, 
                s.phone, 
                s.created_at,
                COALESCE(SUM(CASE WHEN ib.status = 'Issued' THEN 1 ELSE 0 END), 0) AS active_borrowed,
                COUNT(ib.id) AS total_borrowed
            FROM students s
            LEFT JOIN issued_books ib ON s.id = ib.student_id
            WHERE 1=1
        """
        params = []
        if search_query:
            sql += " AND (s.name LIKE %s OR s.email LIKE %s OR s.phone LIKE %s)"
            search_pattern = f"%{search_query}%"
            params.extend([search_pattern, search_pattern, search_pattern])

        sql += " GROUP BY s.id, s.name, s.email, s.phone, s.created_at ORDER BY s.id DESC"

        cursor.execute(sql, params)
        students_list = cursor.fetchall()
        cursor.close()
    except Error as e:
        flash(f"Error retrieving students: {e}", "danger")
    finally:
        if conn and conn.is_connected():
            conn.close()

    return render_template(
        'students.html',
        students=students_list,
        search_query=search_query
    )


@app.route('/students/add', methods=['GET', 'POST'])
@login_required
def add_student():
    """Register a new student."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()

        errors = []
        if not name:
            errors.append("Student name is required.")
        elif len(name) > 100:
            errors.append("Name cannot exceed 100 characters.")

        if not email:
            errors.append("Email address is required.")
        elif len(email) > 100:
            errors.append("Email cannot exceed 100 characters.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template('add_student.html', form_data=request.form)

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # Check email uniqueness
            cursor.execute("SELECT id FROM students WHERE email = %s;", (email,))
            if cursor.fetchone():
                flash(f"A student with email '{email}' is already registered.", "warning")
                cursor.close()
                return render_template('add_student.html', form_data=request.form)

            insert_sql = "INSERT INTO students (name, email, phone) VALUES (%s, %s, %s);"
            cursor.execute(insert_sql, (name, email, phone))
            conn.commit()
            cursor.close()

            flash(f"Student '{name}' registered successfully.", "success")
            return redirect(url_for('students'))
        except Error as e:
            if conn:
                conn.rollback()
            flash(f"Database error registering student: {e}", "danger")
        finally:
            if conn and conn.is_connected():
                conn.close()

    return render_template('add_student.html', form_data={})


@app.route('/students/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    """Edit student details."""
    conn = None
    student = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE id = %s;", (student_id,))
        student = cursor.fetchone()
        cursor.close()
    except Error as e:
        flash(f"Database error: {e}", "danger")
        return redirect(url_for('students'))
    finally:
        if conn and conn.is_connected():
            conn.close()

    if not student:
        flash("Student record not found.", "warning")
        return redirect(url_for('students'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()

        errors = []
        if not name:
            errors.append("Student name is required.")
        if not email:
            errors.append("Email is required.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template('edit_student.html', student=student)

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # Check email uniqueness excluding current student
            cursor.execute("SELECT id FROM students WHERE email = %s AND id != %s;", (email, student_id))
            if cursor.fetchone():
                flash(f"The email '{email}' is already registered to another student.", "warning")
                cursor.close()
                return render_template('edit_student.html', student=student)

            update_sql = "UPDATE students SET name = %s, email = %s, phone = %s WHERE id = %s;"
            cursor.execute(update_sql, (name, email, phone, student_id))
            conn.commit()
            cursor.close()

            flash(f"Student '{name}' details updated successfully.", "success")
            return redirect(url_for('students'))
        except Error as e:
            if conn:
                conn.rollback()
            flash(f"Database error updating student: {e}", "danger")
        finally:
            if conn and conn.is_connected():
                conn.close()

    return render_template('edit_student.html', student=student)


@app.route('/students/<int:student_id>/history')
@login_required
def student_history(student_id):
    """View individual student borrowing history."""
    conn = None
    student = None
    borrowing_history = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM students WHERE id = %s;", (student_id,))
        student = cursor.fetchone()

        if not student:
            flash("Student not found.", "warning")
            return redirect(url_for('students'))

        cursor.execute("""
            SELECT 
                ib.id,
                ib.book_id,
                ib.issue_date,
                ib.return_date,
                ib.status,
                b.title AS book_title,
                b.author AS book_author,
                b.isbn AS book_isbn
            FROM issued_books ib
            JOIN books b ON ib.book_id = b.id
            WHERE ib.student_id = %s
            ORDER BY ib.issue_date DESC;
        """, (student_id,))
        borrowing_history = cursor.fetchall()
        cursor.close()
    except Error as e:
        flash(f"Database error loading borrowing history: {e}", "danger")
        return redirect(url_for('students'))
    finally:
        if conn and conn.is_connected():
            conn.close()

    return render_template('student_history.html', student=student, history=borrowing_history)


@app.route('/students/delete/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    """Delete student only if no active or historical loans exist."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT name FROM students WHERE id = %s;", (student_id,))
        student = cursor.fetchone()
        if not student:
            flash("Student not found.", "warning")
            return redirect(url_for('students'))

        # Check for active issued books
        cursor.execute("""
            SELECT COUNT(*) AS active_cnt 
            FROM issued_books 
            WHERE student_id = %s AND status = 'Issued';
        """, (student_id,))
        active_check = cursor.fetchone()
        if active_check and active_check['active_cnt'] > 0:
            flash(
                f"Cannot delete '{student['name']}': student currently has {active_check['active_cnt']} unreturned book(s).",
                "danger"
            )
            return redirect(url_for('students'))

        # Check for historical borrowings
        cursor.execute("""
            SELECT COUNT(*) AS history_cnt 
            FROM issued_books 
            WHERE student_id = %s;
        """, (student_id,))
        history_check = cursor.fetchone()
        if history_check and history_check['history_cnt'] > 0:
            flash(
                f"Cannot delete '{student['name']}': student has {history_check['history_cnt']} borrowing record(s) in history. "
                "Preserved to protect library audit logs.",
                "warning"
            )
            return redirect(url_for('students'))

        cursor.execute("DELETE FROM students WHERE id = %s;", (student_id,))
        conn.commit()
        cursor.close()
        flash(f"Student '{student['name']}' deleted successfully.", "success")
    except Error as e:
        if conn:
            conn.rollback()
        flash(f"Database error deleting student: {e}", "danger")
    finally:
        if conn and conn.is_connected():
            conn.close()

    return redirect(url_for('students'))


# =====================================================================
# Book Issue Management Routes
# =====================================================================

@app.route('/issue', methods=['GET', 'POST'])
@login_required
def issue_book():
    """Issue a book to a student with atomic transaction control."""
    selected_book_id = request.args.get('book_id', type=int)
    selected_student_id = request.args.get('student_id', type=int)

    conn = None
    if request.method == 'POST':
        student_id = request.form.get('student_id', type=int)
        book_id = request.form.get('book_id', type=int)

        if not student_id or not book_id:
            flash("Please select both a student and a book to issue.", "danger")
            return redirect(url_for('issue_book'))

        try:
            conn = get_db_connection()
            # Start explicit transaction
            cursor = conn.cursor(dictionary=True)

            # 1. Verify student exists
            cursor.execute("SELECT id, name FROM students WHERE id = %s;", (student_id,))
            student = cursor.fetchone()
            if not student:
                flash("Selected student does not exist.", "danger")
                return redirect(url_for('issue_book'))

            # 2. Lock and verify book availability with FOR UPDATE
            cursor.execute("SELECT id, title, available, quantity FROM books WHERE id = %s FOR UPDATE;", (book_id,))
            book = cursor.fetchone()
            if not book:
                flash("Selected book does not exist in inventory.", "danger")
                return redirect(url_for('issue_book'))

            if book['available'] <= 0:
                flash(f"Book '{book['title']}' is currently out of stock (available: 0).", "warning")
                conn.rollback()
                return redirect(url_for('issue_book'))

            # Optional check: warn if student already holds an unreturned copy of the same book
            cursor.execute("""
                SELECT id FROM issued_books 
                WHERE book_id = %s AND student_id = %s AND status = 'Issued';
            """, (book_id, student_id))
            if cursor.fetchone():
                flash(
                    f"Notice: Student '{student['name']}' already has an active copy of '{book['title']}'. "
                    "Another copy has been issued as requested.",
                    "info"
                )

            # 3. Insert record into issued_books
            insert_sql = """
                INSERT INTO issued_books (book_id, student_id, issue_date, return_date, status)
                VALUES (%s, %s, NOW(), NULL, 'Issued');
            """
            cursor.execute(insert_sql, (book_id, student_id))

            # 4. Decrease available copies in books table
            update_sql = """
                UPDATE books 
                SET available = available - 1 
                WHERE id = %s AND available > 0;
            """
            cursor.execute(update_sql, (book_id,))

            # Commit the atomic transaction
            conn.commit()
            cursor.close()

            flash(f"Successfully issued '{book['title']}' to student '{student['name']}'.", "success")
            return redirect(url_for('issued_books'))
        except Error as e:
            if conn:
                conn.rollback()
            flash(f"Transaction failed while issuing book: {e}", "danger")
            return redirect(url_for('issue_book'))
        finally:
            if conn and conn.is_connected():
                conn.close()

    # GET request: load available books and registered students
    available_books = []
    all_students = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id, title, author, isbn, available, quantity FROM books WHERE available > 0 ORDER BY title ASC;")
        available_books = cursor.fetchall()

        cursor.execute("SELECT id, name, email, phone FROM students ORDER BY name ASC;")
        all_students = cursor.fetchall()

        cursor.close()
    except Error as e:
        flash(f"Error loading issue book form: {e}", "danger")
    finally:
        if conn and conn.is_connected():
            conn.close()

    return render_template(
        'issue_book.html',
        available_books=available_books,
        students=all_students,
        selected_book_id=selected_book_id,
        selected_student_id=selected_student_id
    )


# =====================================================================
# Book Return Management & Borrowing History Routes
# =====================================================================

@app.route('/issued-books')
@login_required
def issued_books():
    """Display borrowing history, manage returns, and filter records."""
    status_filter = request.args.get('status', 'Issued').strip()
    search_query = request.args.get('search', '').strip()

    borrowed_records = []
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        sql = """
            SELECT 
                ib.id,
                ib.book_id,
                ib.student_id,
                ib.issue_date,
                ib.return_date,
                ib.status,
                b.title AS book_title,
                b.author AS book_author,
                b.isbn AS book_isbn,
                s.name AS student_name,
                s.email AS student_email,
                s.phone AS student_phone
            FROM issued_books ib
            JOIN books b ON ib.book_id = b.id
            JOIN students s ON ib.student_id = s.id
            WHERE 1=1
        """
        params = []

        if status_filter in ('Issued', 'Returned'):
            sql += " AND ib.status = %s"
            params.append(status_filter)

        if search_query:
            sql += " AND (b.title LIKE %s OR b.author LIKE %s OR b.isbn LIKE %s OR s.name LIKE %s OR s.email LIKE %s)"
            pattern = f"%{search_query}%"
            params.extend([pattern, pattern, pattern, pattern, pattern])

        sql += " ORDER BY ib.issue_date DESC"

        cursor.execute(sql, params)
        borrowed_records = cursor.fetchall()
        cursor.close()
    except Error as e:
        flash(f"Error retrieving borrowing records: {e}", "danger")
    finally:
        if conn and conn.is_connected():
            conn.close()

    return render_template(
        'issued_books.html',
        records=borrowed_records,
        status_filter=status_filter,
        search_query=search_query
    )


@app.route('/return/<int:issue_id>', methods=['POST'])
@login_required
def return_book(issue_id):
    """Process book return atomically, updating loan record and incrementing inventory availability."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Fetch loan record and lock row
        cursor.execute("""
            SELECT ib.id, ib.book_id, ib.status, b.title AS book_title, s.name AS student_name
            FROM issued_books ib
            JOIN books b ON ib.book_id = b.id
            JOIN students s ON ib.student_id = s.id
            WHERE ib.id = %s FOR UPDATE;
        """, (issue_id,))
        loan = cursor.fetchone()

        if not loan:
            flash("Borrowing record not found.", "warning")
            return redirect(url_for('issued_books'))

        if loan['status'] == 'Returned':
            flash(f"This record for '{loan['book_title']}' has already been marked as Returned.", "warning")
            return redirect(url_for('issued_books'))

        # 2. Update issued_books: set return_date = NOW(), status = 'Returned'
        cursor.execute("""
            UPDATE issued_books 
            SET return_date = NOW(), status = 'Returned'
            WHERE id = %s AND status = 'Issued';
        """, (issue_id,))

        # 3. Increase available copies in books table
        cursor.execute("""
            UPDATE books 
            SET available = available + 1 
            WHERE id = %s;
        """, (loan['book_id'],))

        conn.commit()
        cursor.close()

        flash(f"Successfully processed return of '{loan['book_title']}' from '{loan['student_name']}'.", "success")
    except Error as e:
        if conn:
            conn.rollback()
        flash(f"Database error during return transaction: {e}", "danger")
    finally:
        if conn and conn.is_connected():
            conn.close()

    return redirect(url_for('issued_books'))


# =====================================================================
# Reports & Analytics Route
# =====================================================================

@app.route('/reports')
@login_required
def reports():
    """Generate dynamic reports using SQL aggregate functions and present proposed extensions."""
    conn = None
    top_books = []
    top_students = []
    inventory_summary = {}
    issue_status_summary = {}

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Most frequently issued books
        cursor.execute("""
            SELECT 
                b.id,
                b.title,
                b.author,
                b.isbn,
                b.quantity,
                b.available,
                COUNT(ib.id) AS borrow_count
            FROM books b
            LEFT JOIN issued_books ib ON b.id = ib.book_id
            GROUP BY b.id, b.title, b.author, b.isbn, b.quantity, b.available
            HAVING borrow_count > 0
            ORDER BY borrow_count DESC
            LIMIT 10;
        """)
        top_books = cursor.fetchall()

        # 2. Students with highest number of borrowings
        cursor.execute("""
            SELECT 
                s.id,
                s.name,
                s.email,
                s.phone,
                COUNT(ib.id) AS total_borrowed,
                COALESCE(SUM(CASE WHEN ib.status = 'Issued' THEN 1 ELSE 0 END), 0) AS active_borrowed,
                COALESCE(SUM(CASE WHEN ib.status = 'Returned' THEN 1 ELSE 0 END), 0) AS returned_count
            FROM students s
            LEFT JOIN issued_books ib ON s.id = ib.student_id
            GROUP BY s.id, s.name, s.email, s.phone
            HAVING total_borrowed > 0
            ORDER BY total_borrowed DESC
            LIMIT 10;
        """)
        top_students = cursor.fetchall()

        # 3. Overall Inventory Summary
        cursor.execute("""
            SELECT 
                COUNT(*) AS total_titles,
                COALESCE(SUM(quantity), 0) AS total_copies,
                COALESCE(SUM(available), 0) AS total_available,
                COALESCE(SUM(CASE WHEN available = 0 THEN 1 ELSE 0 END), 0) AS out_of_stock_titles,
                COALESCE(SUM(CASE WHEN available > 0 THEN 1 ELSE 0 END), 0) AS available_titles
            FROM books;
        """)
        inventory_summary = cursor.fetchone() or {}

        # 4. Loan status summary
        cursor.execute("""
            SELECT 
                COUNT(*) AS total_transactions,
                COALESCE(SUM(CASE WHEN status = 'Issued' THEN 1 ELSE 0 END), 0) AS active_issues,
                COALESCE(SUM(CASE WHEN status = 'Returned' THEN 1 ELSE 0 END), 0) AS returned_loans
            FROM issued_books;
        """)
        issue_status_summary = cursor.fetchone() or {}

        cursor.close()
    except Error as e:
        flash(f"Error generating reports: {e}", "danger")
    finally:
        if conn and conn.is_connected():
            conn.close()

    return render_template(
        'reports.html',
        top_books=top_books,
        top_students=top_students,
        inventory_summary=inventory_summary,
        issue_status_summary=issue_status_summary
    )


# =====================================================================
# Application Entry Point
# =====================================================================

if __name__ == '__main__':
    # Run development server
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
