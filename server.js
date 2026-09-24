const express = require("express");
const mysql = require("mysql2");
const cors = require("cors");

const app = express();
const PORT = process.env.PORT || 3000;

// ============================================
// MIDDLEWARE
// ============================================

app.use(cors());
app.use(express.json());

// ============================================
// MYSQL DATABASE CONNECTION
// ============================================

const fs = require('fs');
const path = require('path');

// Connect to Aiven MySQL Database
const db = mysql.createPool({
    host: process.env.MYSQLHOST || "mysql-2a88a4dc-ayusmanmohanty17-e802.d.aivencloud.com",
    port: process.env.MYSQLPORT || 15336,
    user: process.env.MYSQLUSER || "avnadmin",
    password: process.env.MYSQLPASSWORD || "AVNS_c-EJHWVXmbomT4Dkm_s",
    database: process.env.MYSQLDATABASE || "defaultdb",
    ssl: fs.existsSync(path.join(__dirname, 'ca.pem')) 
         ? { ca: fs.readFileSync(path.join(__dirname, 'ca.pem')) } 
         : { rejectUnauthorized: false },
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
});

// ============================================
// TEST MYSQL CONNECTION
// ============================================

db.getConnection((err, connection) => {

    if (err) {
        console.error("");
        console.error("❌ MySQL connection failed:");
        console.error(err.message);
        console.error("");

        return;
    }

    console.log("");
    console.log("======================================");
    console.log("✅ CONNECTED TO MYSQL");
    console.log("======================================");
    console.log("📚 Database: library");
    console.log("🖥️ Host: localhost");
    console.log("🔌 Port: 3306");
    console.log("======================================");
    console.log("");

    connection.release();
});

// ============================================
// DASHBOARD API
// ============================================

app.get("/api/dashboard", (req, res) => {

    const sql = `
    SELECT
        (SELECT COALESCE(SUM(quantity), 0)
         FROM books) AS totalBooks,

        (SELECT COALESCE(SUM(available), 0)
         FROM books) AS availableBooks,

        (SELECT COUNT(*)
         FROM issued_books
         WHERE status = 'Issued') AS issuedBooks,

        (SELECT COUNT(*)
         FROM students) AS totalStudents
`;

    db.query(sql, (err, results) => {

        if (err) {
            console.error("Dashboard error:", err.message);

            return res.status(500).json({
                error: "Failed to load dashboard data"
            });
        }

        res.json(results[0]);
    });
});

// ============================================
// GET ALL BOOKS
// ============================================

app.get("/api/books", (req, res) => {

    const sql = `
    SELECT
        id,
        title,
        author,
        isbn,
        quantity,
        available,
        created_at
    FROM books
    ORDER BY id DESC
`;

    db.query(sql, (err, results) => {

        if (err) {
            console.error("Books error:", err.message);

            return res.status(500).json({
                error: "Failed to fetch books"
            });
        }

        res.json(results);
    });
});

// ============================================
// GET ALL STUDENTS
// ============================================

app.get("/api/students", (req, res) => {

    const sql = `
    SELECT
        id,
        name,
        email,
        phone,
        created_at
    FROM students
    ORDER BY id DESC
`;

    db.query(sql, (err, results) => {

        if (err) {
            console.error("Students error:", err.message);

            return res.status(500).json({
                error: "Failed to fetch students"
            });
        }

        res.json(results);
    });
});

// ============================================
// GET ISSUED BOOKS
// ============================================

app.get("/api/issued-books", (req, res) => {

    const sql = `
    SELECT
        ib.id,
        b.title AS book_title,
        s.name AS student_name,
        ib.issue_date,
        ib.return_date,
        ib.status

    FROM issued_books ib

    INNER JOIN books b
        ON ib.book_id = b.id

    INNER JOIN students s
        ON ib.student_id = s.id

    ORDER BY ib.id DESC
`;

    db.query(sql, (err, results) => {

        if (err) {
            console.error("Issued books error:", err.message);

            return res.status(500).json({
                error: "Failed to fetch issued books"
            });
        }

        res.json(results);
    });
});

// ============================================
// TEST API
// ============================================

app.get("/", (req, res) => {

    res.json({
        message: "Library Management System API is running",
        database: "library",
        status: "OK"
    });
});

// ============================================
// START SERVER
// ============================================

app.listen(PORT, () => {

    console.log("");
    console.log("======================================");
    console.log("📚 LIBRARY MANAGEMENT SYSTEM");
    console.log("======================================");
    console.log(`🚀 Server running at http://localhost:${PORT}`);
    console.log("======================================");
    console.log("");
});
