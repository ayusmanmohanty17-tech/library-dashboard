const API_URL = 'https://library-dashboard-production.up.railway.app/api';

// Helper function for API requests
async function apiRequest(endpoint) {
    const response = await fetch(`${API_URL}${endpoint}`);
    if (!response.ok) {
        throw new Error(`HTTP Error: ${response.status}`);
    }
    return await response.json();
}

// Show error messages in the UI
function showError(message) {
    console.error(message);
    const errorBox = document.getElementById('errorMessage');
    if (errorBox) {
        errorBox.textContent = message;
        errorBox.style.display = 'block';
        setTimeout(() => {
            errorBox.style.display = 'none';
        }, 5000);
    }
}

// Navigation and section switching
function showSection(sectionName) {
    // Hide all sections
    document.querySelectorAll('.section').forEach(section => {
        section.classList.remove('active-section');
    });

    // Show selected section
    const section = document.getElementById(sectionName);
    if (section) {
        section.classList.add('active-section');
    }

    // Toggle active state on navigation buttons
    document.querySelectorAll('.nav-btn').forEach(button => {
        button.classList.remove('active');
        const onclickAttr = button.getAttribute('onclick');
        // Safely check if the onclick attribute targets this section
        if (onclickAttr && onclickAttr.includes(`'${sectionName}'`)) {
            button.classList.add('active');
        }
    });

    // Fetch data for the specific section being opened
    if (sectionName === 'dashboard') loadDashboard();
    if (sectionName === 'books') loadBooks();
    if (sectionName === 'students') loadStudents();
    if (sectionName === 'issued') loadIssuedBooks();
}

// Load Dashboard data
async function loadDashboard() {
    try {
        const data = await apiRequest('/dashboard');
        document.getElementById('totalBooks').textContent = data.totalBooks ?? 0;
        document.getElementById('availableBooks').textContent = data.availableBooks ?? 0;
        document.getElementById('issuedBooks').textContent = data.issuedBooks ?? 0;
        document.getElementById('totalStudents').textContent = data.totalStudents ?? 0;
    } catch (error) {
        console.error('Dashboard error:', error);
        showError('Unable to load dashboard data.');
    }
}

// Load Books data
async function loadBooks() {
    try {
        const books = await apiRequest('/books');
        const booksTable = document.getElementById('booksTable');
        const recentBooks = document.getElementById('recentBooks');

        if (booksTable) booksTable.innerHTML = '';
        if (recentBooks) recentBooks.innerHTML = '';

        if (!books || books.length === 0) {
            const message = `<tr><td colspan="7" style="text-align:center;">No books found.</td></tr>`;
            if (booksTable) booksTable.innerHTML = message;
            if (recentBooks) recentBooks.innerHTML = message;
            return;
        }

        books.forEach(book => {
            const status = book.available > 0
                ? `<span class="status available">Available</span>`
                : `<span class="status unavailable">Unavailable</span>`;

            const row = `<tr>
                <td>${book.id}</td>
                <td>${book.title}</td>
                <td>${book.author}</td>
                <td>${book.isbn}</td>
                <td>${book.quantity}</td>
                <td>${book.available}</td>
                <td>${status}</td>
            </tr>`;

            if (booksTable) booksTable.innerHTML += row;
            if (recentBooks) recentBooks.innerHTML += row; // Optional: Only slice recent items if needed
        });
    } catch (error) {
        console.error('Books error:', error);
        showError('Unable to load books.');
    }
}

// Load Students data
async function loadStudents() {
    try {
        const students = await apiRequest('/students');
        const table = document.getElementById('studentsTable');
        if (!table) return;

        table.innerHTML = '';

        if (!students || students.length === 0) {
            table.innerHTML = `<tr><td colspan="5" style="text-align:center;">No students found in the database.</td></tr>`;
            return;
        }

        students.forEach(student => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${student.id}</td>
                <td>${student.name}</td>
                <td>${student.email}</td>
                <td>${student.phone}</td>
                <td>${formatDate(student.created_at)}</td>
            `;
            table.appendChild(row);
        });
    } catch (error) {
        console.error('Students error:', error);
        const table = document.getElementById('studentsTable');
        if (table) {
            table.innerHTML = `<tr><td colspan="5" style="text-align:center;">Unable to load students.</td></tr>`;
        }
        showError('Unable to load students.');
    }
}

// Load Issued Books data
async function loadIssuedBooks() {
    try {
        const issuedBooks = await apiRequest('/issued-books');
        const table = document.getElementById('issuedTable');
        if (!table) return;

        table.innerHTML = '';

        if (!issuedBooks || issuedBooks.length === 0) {
            table.innerHTML = `<tr><td colspan="6" style="text-align:center;">No books have been issued.</td></tr>`;
            return;
        }

        issuedBooks.forEach(item => {
            // Normalize checking lowercase or capitalized string statuses
            const isIssued = item.status && item.status.toLowerCase() === 'issued';
            const statusClass = isIssued ? 'issued' : 'returned';

            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${item.id}</td>
                <td>${item.book_title}</td>
                <td>${item.student_name}</td>
                <td>${formatDate(item.issue_date)}</td>
                <td>${item.return_date ? formatDate(item.return_date) : '-'}</td>
                <td><span class="status ${statusClass}">${item.status}</span></td>
            `;
            table.appendChild(row);
        });
    } catch (error) {
        console.error('Issued books error:', error);
        const table = document.getElementById('issuedTable');
        if (table) {
            table.innerHTML = `<tr><td colspan="6" style="text-align:center;">Unable to load issued books.</td></tr>`;
        }
        showError('Unable to load issued books.');
    }
}

// Date Formatter
function formatDate(date) {
    if (!date) return '-';
    return new Date(date).toLocaleString();
}

// Initialize application on load
document.addEventListener('DOMContentLoaded', () => {
    showSection('dashboard'); // Default to showing the dashboard first
});
