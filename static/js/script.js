/**
 * Library Management System - Client-side Scripts
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Mobile Sidebar Toggle & Backdrop
    const sidebar = document.getElementById('appSidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const backdrop = document.getElementById('sidebarBackdrop');

    if (sidebarToggle && sidebar && backdrop) {
        sidebarToggle.addEventListener('click', function () {
            sidebar.classList.toggle('show');
            backdrop.classList.toggle('show');
        });

        backdrop.addEventListener('click', function () {
            sidebar.classList.remove('show');
            backdrop.classList.remove('show');
        });
    }

    // 2. Initialize Bootstrap Tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // 3. Return Book Modal Handler
    const returnModal = document.getElementById('returnConfirmModal');
    if (returnModal) {
        returnModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const issueId = button.getAttribute('data-issue-id');
            const bookTitle = button.getAttribute('data-book-title');
            const studentName = button.getAttribute('data-student-name');

            const modalTitleEl = returnModal.querySelector('#returnModalBookTitle');
            const modalStudentEl = returnModal.querySelector('#returnModalStudentName');
            const returnForm = returnModal.querySelector('#returnModalForm');

            if (modalTitleEl) modalTitleEl.textContent = bookTitle;
            if (modalStudentEl) modalStudentEl.textContent = studentName;
            if (returnForm) returnForm.action = '/return/' + issueId;
        });
    }

    // 4. Delete Book Modal Handler
    const deleteBookModal = document.getElementById('deleteBookModal');
    if (deleteBookModal) {
        deleteBookModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const bookId = button.getAttribute('data-book-id');
            const bookTitle = button.getAttribute('data-book-title');

            const titleEl = deleteBookModal.querySelector('#deleteBookTitle');
            const form = deleteBookModal.querySelector('#deleteBookForm');

            if (titleEl) titleEl.textContent = bookTitle;
            if (form) form.action = '/books/delete/' + bookId;
        });
    }

    // 5. Delete Student Modal Handler
    const deleteStudentModal = document.getElementById('deleteStudentModal');
    if (deleteStudentModal) {
        deleteStudentModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const studentId = button.getAttribute('data-student-id');
            const studentName = button.getAttribute('data-student-name');

            const nameEl = deleteStudentModal.querySelector('#deleteStudentName');
            const form = deleteStudentModal.querySelector('#deleteStudentForm');

            if (nameEl) nameEl.textContent = studentName;
            if (form) form.action = '/students/delete/' + studentId;
        });
    }

    // 6. Dynamic Book Selector in Issue Form
    const bookSelect = document.getElementById('book_select');
    const bookInfoPreview = document.getElementById('book_info_preview');
    if (bookSelect && bookInfoPreview) {
        function updateBookPreview() {
            const selectedOpt = bookSelect.options[bookSelect.selectedIndex];
            if (selectedOpt && selectedOpt.value) {
                const available = selectedOpt.getAttribute('data-available');
                const author = selectedOpt.getAttribute('data-author');
                const isbn = selectedOpt.getAttribute('data-isbn');
                
                bookInfoPreview.innerHTML = `
                    <div class="alert alert-info py-2 px-3 mb-0">
                        <small>
                            <strong>Author:</strong> ${author} | 
                            <strong>ISBN:</strong> ${isbn} | 
                            <span class="badge ${available > 0 ? 'bg-success' : 'bg-danger'}">${available} Available</span>
                        </small>
                    </div>
                `;
            } else {
                bookInfoPreview.innerHTML = '';
            }
        }
        bookSelect.addEventListener('change', updateBookPreview);
        updateBookPreview();
    }

    // 7. Auto fade-out alerts after 5 seconds (except danger alerts)
    setTimeout(function () {
        const alerts = document.querySelectorAll('.alert-dismissible:not(.alert-danger)');
        alerts.forEach(function (alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 6000);
});
