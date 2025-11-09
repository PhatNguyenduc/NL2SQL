-- Sample database schema for testing
-- PostgreSQL version

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    full_name VARCHAR(100),
    age INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products table
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    stock_quantity INTEGER DEFAULT 0,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Order items table
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Insert sample data
INSERT INTO users (username, email, full_name, age) VALUES
    ('john_doe', 'john@example.com', 'John Doe', 30),
    ('jane_smith', 'jane@example.com', 'Jane Smith', 25),
    ('bob_johnson', 'bob@example.com', 'Bob Johnson', 35);

INSERT INTO products (name, description, price, stock_quantity, category) VALUES
    ('Laptop', 'High-performance laptop', 999.99, 10, 'Electronics'),
    ('Mouse', 'Wireless mouse', 29.99, 50, 'Electronics'),
    ('Keyboard', 'Mechanical keyboard', 79.99, 30, 'Electronics'),
    ('Monitor', '27-inch 4K monitor', 399.99, 15, 'Electronics');

INSERT INTO orders (user_id, total_amount, status) VALUES
    (1, 1029.98, 'completed'),
    (2, 29.99, 'completed'),
    (1, 479.98, 'pending');

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
    (1, 1, 1, 999.99),
    (1, 2, 1, 29.99),
    (2, 2, 1, 29.99),
    (3, 4, 1, 399.99),
    (3, 3, 1, 79.99);
