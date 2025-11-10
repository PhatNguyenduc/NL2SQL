create database if not exists ecommerce;
use ecommerce;

CREATE TABLE users
(
    user_id       BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name    VARCHAR(100) NOT NULL,
    last_name     VARCHAR(100) NOT NULL,
    phone         VARCHAR(20),
    date_of_birth DATE,
    is_active     BOOLEAN   DEFAULT TRUE,
    is_verified   BOOLEAN   DEFAULT FALSE,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP    NULL,
    INDEX idx_email (email),
    INDEX idx_created_at (created_at)
);

CREATE TABLE user_addresses
(
    address_id     BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id        BIGINT UNSIGNED NOT NULL,
    address_type   ENUM ('billing', 'shipping', 'both') DEFAULT 'shipping',
    is_default     BOOLEAN                              DEFAULT FALSE,
    full_name      VARCHAR(200)    NOT NULL,
    phone          VARCHAR(20),
    address_line1  VARCHAR(255)    NOT NULL,
    address_line2  VARCHAR(255),
    city           VARCHAR(100)    NOT NULL,
    state_province VARCHAR(100)    NOT NULL,
    postal_code    VARCHAR(20)     NOT NULL,
    country        VARCHAR(100)    NOT NULL,
    created_at     TIMESTAMP                            DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP                            DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_default (user_id, is_default)
);

CREATE TABLE categories
(
    category_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    parent_category_id BIGINT UNSIGNED NULL,
    category_name      VARCHAR(200)    NOT NULL,
    slug               VARCHAR(200)    NOT NULL UNIQUE,
    description        TEXT,
    image_url          VARCHAR(500),
    is_active          BOOLEAN   DEFAULT TRUE,
    sort_order         INT       DEFAULT 0,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_category_id) REFERENCES categories (category_id) ON DELETE SET NULL,
    INDEX idx_parent (parent_category_id),
    INDEX idx_slug (slug),
    INDEX idx_active (is_active)
);

CREATE TABLE brands
(
    brand_id    BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    brand_name  VARCHAR(200) NOT NULL UNIQUE,
    slug        VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    logo_url    VARCHAR(500),
    website_url VARCHAR(500),
    is_active   BOOLEAN   DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_slug (slug)
);

CREATE TABLE products
(
    product_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    brand_id          BIGINT UNSIGNED,
    product_name      VARCHAR(500)   NOT NULL,
    slug              VARCHAR(500)   NOT NULL UNIQUE,
    sku               VARCHAR(100)   NOT NULL UNIQUE,
    description       TEXT,
    short_description VARCHAR(500),
    base_price        DECIMAL(10, 2) NOT NULL,
    compare_at_price  DECIMAL(10, 2),
    cost_price        DECIMAL(10, 2),
    weight            DECIMAL(8, 2),
    weight_unit       ENUM ('kg', 'g', 'lb', 'oz') DEFAULT 'kg',
    is_active         BOOLEAN                      DEFAULT TRUE,
    is_featured       BOOLEAN                      DEFAULT FALSE,
    view_count        INT UNSIGNED                 DEFAULT 0,
    created_at        TIMESTAMP                    DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP                    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (brand_id) REFERENCES brands (brand_id) ON DELETE SET NULL,
    INDEX idx_sku (sku),
    INDEX idx_slug (slug),
    INDEX idx_brand (brand_id),
    INDEX idx_active (is_active),
    INDEX idx_featured (is_featured),
    INDEX idx_price (base_price),
    FULLTEXT idx_search (product_name, description)
);

CREATE TABLE product_categories
(
    product_id  BIGINT UNSIGNED NOT NULL,
    category_id BIGINT UNSIGNED NOT NULL,
    is_primary  BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (product_id, category_id),
    FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories (category_id) ON DELETE CASCADE,
    INDEX idx_category (category_id)
);

CREATE TABLE product_images
(
    image_id   BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    product_id BIGINT UNSIGNED NOT NULL,
    image_url  VARCHAR(500)    NOT NULL,
    alt_text   VARCHAR(255),
    is_primary BOOLEAN   DEFAULT FALSE,
    sort_order INT       DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE CASCADE,
    INDEX idx_product (product_id),
    INDEX idx_primary (product_id, is_primary)
);

CREATE TABLE product_variants
(
    variant_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    product_id        BIGINT UNSIGNED NOT NULL,
    variant_name      VARCHAR(200)    NOT NULL,
    sku               VARCHAR(100)    NOT NULL UNIQUE,
    price_adjustment  DECIMAL(10, 2) DEFAULT 0.00,
    weight_adjustment DECIMAL(8, 2)  DEFAULT 0.00,
    is_active         BOOLEAN        DEFAULT TRUE,
    created_at        TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE CASCADE,
    INDEX idx_product (product_id),
    INDEX idx_sku (sku)
);

CREATE TABLE product_attributes
(
    attribute_id   BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    attribute_name VARCHAR(100) NOT NULL UNIQUE,
    display_name   VARCHAR(100) NOT NULL,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE variant_attributes
(
    variant_id      BIGINT UNSIGNED NOT NULL,
    attribute_id    BIGINT UNSIGNED NOT NULL,
    attribute_value VARCHAR(200)    NOT NULL,
    PRIMARY KEY (variant_id, attribute_id),
    FOREIGN KEY (variant_id) REFERENCES product_variants (variant_id) ON DELETE CASCADE,
    FOREIGN KEY (attribute_id) REFERENCES product_attributes (attribute_id) ON DELETE CASCADE,
    INDEX idx_attribute (attribute_id)
);

CREATE TABLE inventory
(
    inventory_id       BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    product_id         BIGINT UNSIGNED,
    variant_id         BIGINT UNSIGNED,
    quantity_available INT UNSIGNED DEFAULT 0,
    quantity_reserved  INT UNSIGNED DEFAULT 0,
    reorder_level      INT UNSIGNED DEFAULT 10,
    warehouse_location VARCHAR(100),
    last_stock_check   TIMESTAMP NULL,
    updated_at         TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES product_variants (variant_id) ON DELETE CASCADE,
    UNIQUE KEY unique_product_variant (product_id, variant_id),
    INDEX idx_product (product_id),
    INDEX idx_variant (variant_id),
    INDEX idx_quantity (quantity_available)
);

CREATE TABLE cart_items
(
    cart_item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id      BIGINT UNSIGNED NOT NULL,
    product_id   BIGINT UNSIGNED NOT NULL,
    variant_id   BIGINT UNSIGNED,
    quantity     INT UNSIGNED    NOT NULL DEFAULT 1,
    price        DECIMAL(10, 2)  NOT NULL,
    created_at   TIMESTAMP                DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP                DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES product_variants (variant_id) ON DELETE CASCADE,
    INDEX idx_user (user_id),
    INDEX idx_product (product_id)
);

CREATE TABLE orders
(
    order_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT UNSIGNED NOT NULL,
    order_number    VARCHAR(50)     NOT NULL UNIQUE,
    order_status    ENUM ('pending', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded') DEFAULT 'pending',
    payment_status  ENUM ('pending', 'paid', 'failed', 'refunded')                                  DEFAULT 'pending',
    subtotal        DECIMAL(10, 2)  NOT NULL,
    tax_amount      DECIMAL(10, 2)                                                                  DEFAULT 0.00,
    shipping_amount DECIMAL(10, 2)                                                                  DEFAULT 0.00,
    discount_amount DECIMAL(10, 2)                                                                  DEFAULT 0.00,
    total_amount    DECIMAL(10, 2)  NOT NULL,
    currency        VARCHAR(3)                                                                      DEFAULT 'USD',
    notes           TEXT,
    created_at      TIMESTAMP                                                                       DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP                                                                       DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id),
    INDEX idx_user (user_id),
    INDEX idx_order_number (order_number),
    INDEX idx_status (order_status),
    INDEX idx_created (created_at)
);

CREATE TABLE order_items
(
    order_item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id      BIGINT UNSIGNED NOT NULL,
    product_id    BIGINT UNSIGNED NOT NULL,
    variant_id    BIGINT UNSIGNED,
    product_name  VARCHAR(500)    NOT NULL,
    variant_name  VARCHAR(200),
    sku           VARCHAR(100)    NOT NULL,
    quantity      INT UNSIGNED    NOT NULL,
    unit_price    DECIMAL(10, 2)  NOT NULL,
    total_price   DECIMAL(10, 2)  NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products (product_id),
    FOREIGN KEY (variant_id) REFERENCES product_variants (variant_id),
    INDEX idx_order (order_id),
    INDEX idx_product (product_id)
);

CREATE TABLE order_addresses
(
    order_address_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id         BIGINT UNSIGNED              NOT NULL,
    address_type     ENUM ('billing', 'shipping') NOT NULL,
    full_name        VARCHAR(200)                 NOT NULL,
    phone            VARCHAR(20),
    address_line1    VARCHAR(255)                 NOT NULL,
    address_line2    VARCHAR(255),
    city             VARCHAR(100)                 NOT NULL,
    state_province   VARCHAR(100)                 NOT NULL,
    postal_code      VARCHAR(20)                  NOT NULL,
    country          VARCHAR(100)                 NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE CASCADE,
    INDEX idx_order (order_id)
);

CREATE TABLE order_status_history
(
    history_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id   BIGINT UNSIGNED                                                                 NOT NULL,
    status     ENUM ('pending', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded') NOT NULL,
    notes      TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE CASCADE,
    INDEX idx_order (order_id)
);

CREATE TABLE payment_methods
(
    payment_method_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    method_name       VARCHAR(100) NOT NULL UNIQUE,
    is_active         BOOLEAN   DEFAULT TRUE,
    display_order     INT       DEFAULT 0,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE transactions
(
    transaction_id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id               BIGINT UNSIGNED NOT NULL,
    payment_method_id      BIGINT UNSIGNED,
    transaction_type       ENUM ('payment', 'refund')                           DEFAULT 'payment',
    transaction_status     ENUM ('pending', 'completed', 'failed', 'cancelled') DEFAULT 'pending',
    amount                 DECIMAL(10, 2)  NOT NULL,
    currency               VARCHAR(3)                                           DEFAULT 'USD',
    gateway_transaction_id VARCHAR(255),
    gateway_response       TEXT,
    processed_at           TIMESTAMP       NULL,
    created_at             TIMESTAMP                                            DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders (order_id),
    FOREIGN KEY (payment_method_id) REFERENCES payment_methods (payment_method_id),
    INDEX idx_order (order_id),
    INDEX idx_transaction_id (gateway_transaction_id)
);

CREATE TABLE shipping_methods
(
    shipping_method_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    method_name        VARCHAR(100)   NOT NULL,
    description        TEXT,
    base_cost          DECIMAL(10, 2) NOT NULL,
    cost_per_kg        DECIMAL(10, 2) DEFAULT 0.00,
    estimated_days_min INT,
    estimated_days_max INT,
    is_active          BOOLEAN        DEFAULT TRUE,
    created_at         TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE shipments
(
    shipment_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id           BIGINT UNSIGNED NOT NULL,
    shipping_method_id BIGINT UNSIGNED,
    tracking_number    VARCHAR(255),
    carrier            VARCHAR(100),
    shipped_at         TIMESTAMP       NULL,
    estimated_delivery TIMESTAMP       NULL,
    delivered_at       TIMESTAMP       NULL,
    shipment_status    ENUM ('pending', 'shipped', 'in_transit', 'delivered', 'returned') DEFAULT 'pending',
    notes              TEXT,
    created_at         TIMESTAMP                                                          DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP                                                          DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders (order_id),
    FOREIGN KEY (shipping_method_id) REFERENCES shipping_methods (shipping_method_id),
    INDEX idx_order (order_id),
    INDEX idx_tracking (tracking_number)
);

CREATE TABLE product_reviews
(
    review_id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    product_id           BIGINT UNSIGNED  NOT NULL,
    user_id              BIGINT UNSIGNED  NOT NULL,
    order_id             BIGINT UNSIGNED,
    rating               TINYINT UNSIGNED NOT NULL CHECK (rating BETWEEN 1 AND 5),
    title                VARCHAR(255),
    review_text          TEXT,
    is_verified_purchase BOOLEAN      DEFAULT FALSE,
    is_approved          BOOLEAN      DEFAULT FALSE,
    helpful_count        INT UNSIGNED DEFAULT 0,
    created_at           TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE SET NULL,
    INDEX idx_product (product_id),
    INDEX idx_user (user_id),
    INDEX idx_rating (rating),
    INDEX idx_approved (is_approved)
);

CREATE TABLE coupons
(
    coupon_id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    coupon_code         VARCHAR(50)                         NOT NULL UNIQUE,
    description         TEXT,
    discount_type       ENUM ('percentage', 'fixed_amount') NOT NULL,
    discount_value      DECIMAL(10, 2)                      NOT NULL,
    min_order_amount    DECIMAL(10, 2),
    max_discount_amount DECIMAL(10, 2),
    usage_limit         INT UNSIGNED,
    usage_count         INT UNSIGNED DEFAULT 0,
    usage_per_user      INT UNSIGNED DEFAULT 1,
    is_active           BOOLEAN      DEFAULT TRUE,
    valid_from          TIMESTAMP                           NOT NULL,
    valid_until         TIMESTAMP                           NOT NULL,
    created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_code (coupon_code),
    INDEX idx_active (is_active),
    INDEX idx_dates (valid_from, valid_until)
);

CREATE TABLE coupon_usage
(
    usage_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    coupon_id       BIGINT UNSIGNED NOT NULL,
    user_id         BIGINT UNSIGNED NOT NULL,
    order_id        BIGINT UNSIGNED NOT NULL,
    discount_amount DECIMAL(10, 2)  NOT NULL,
    used_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (coupon_id) REFERENCES coupons (coupon_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE CASCADE,
    INDEX idx_coupon (coupon_id),
    INDEX idx_user (user_id)
);

CREATE TABLE wishlists
(
    wishlist_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT UNSIGNED NOT NULL,
    product_id  BIGINT UNSIGNED NOT NULL,
    variant_id  BIGINT UNSIGNED,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES product_variants (variant_id) ON DELETE CASCADE,
    UNIQUE KEY unique_wishlist_item (user_id, product_id, variant_id),
    INDEX idx_user (user_id),
    INDEX idx_product (product_id)
);
