import mysql.connector
from faker import Faker
import random
from datetime import timedelta
import string

NUM_USERS = 500
NUM_USER_ADDRESSES = 800
NUM_CATEGORIES = 30
NUM_BRANDS = 50
NUM_PRODUCTS = 1000
NUM_PRODUCT_VARIANTS = 2000
NUM_PRODUCT_IMAGES = 3000
NUM_PRODUCT_ATTRIBUTES = 10
NUM_PAYMENT_METHODS = 6
NUM_SHIPPING_METHODS = 5
NUM_INVENTORY_RECORDS = 1500
NUM_CART_ITEMS = 300
NUM_ORDERS = 2000
NUM_ORDER_ITEMS_PER_ORDER_AVG = 3
NUM_ORDER_ADDRESSES_PER_ORDER = 2
NUM_ORDER_STATUS_HISTORY_PER_ORDER_AVG = 2
NUM_TRANSACTIONS_PER_ORDER_AVG = 1
NUM_SHIPMENTS = 1200
NUM_REVIEWS = 1500
NUM_COUPONS = 50
NUM_COUPON_USAGE = 300
NUM_WISHLISTS = 400
NUM_VARIANT_ATTRIBUTES_PER_VARIANT_AVG = 2
NUM_PRODUCT_CATEGORIES_PER_PRODUCT_AVG = 2

fake = Faker()


def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='admin',
        database='ecommerce'
    )


def clear_existing_data(conn):
    cursor = conn.cursor()
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

    tables = [
        'coupon_usage', 'wishlists', 'product_reviews', 'shipments',
        'transactions', 'order_status_history', 'order_addresses', 'order_items',
        'orders', 'cart_items', 'inventory', 'variant_attributes',
        'product_variants', 'product_images', 'product_categories', 'products',
        'brands', 'categories', 'user_addresses', 'users', 'coupons',
        'shipping_methods', 'payment_methods', 'product_attributes'
    ]

    for table in tables:
        cursor.execute(f"TRUNCATE TABLE {table}")

    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    cursor.close()
    print("Cleared existing data from all tables")


def generate_product_attributes(conn, num_attributes):
    cursor = conn.cursor()
    attributes = []

    predefined_attrs = [
        ('color', 'Color'),
        ('size', 'Size'),
        ('material', 'Material'),
        ('storage', 'Storage Capacity'),
        ('memory', 'Memory'),
        ('screen_size', 'Screen Size'),
        ('weight', 'Weight'),
        ('battery', 'Battery Capacity'),
        ('processor', 'Processor'),
        ('style', 'Style')
    ]

    for i in range(min(num_attributes, len(predefined_attrs))):
        attr_name, display_name = predefined_attrs[i]
        cursor.execute("""
                       INSERT INTO product_attributes (attribute_name, display_name)
                       VALUES (%s, %s)
                       """, (attr_name, display_name))
        attributes.append(cursor.lastrowid)

    conn.commit()
    cursor.close()
    print(f"Inserted {len(attributes)} product attributes")
    return attributes


def generate_payment_methods(conn, num_methods):
    cursor = conn.cursor()
    methods = []

    predefined_methods = [
        ('Credit Card', True, 1),
        ('Debit Card', True, 2),
        ('PayPal', True, 3),
        ('Apple Pay', True, 4),
        ('Google Pay', True, 5),
        ('Bank Transfer', True, 6),
        ('Cash on Delivery', True, 7),
        ('Cryptocurrency', False, 8)
    ]

    for i in range(min(num_methods, len(predefined_methods))):
        method_name, is_active, display_order = predefined_methods[i]
        cursor.execute("""
                       INSERT INTO payment_methods (method_name, is_active, display_order)
                       VALUES (%s, %s, %s)
                       """, (method_name, is_active, display_order))
        methods.append(cursor.lastrowid)

    conn.commit()
    cursor.close()
    print(f"Inserted {len(methods)} payment methods")
    return methods


def generate_shipping_methods(conn, num_methods):
    cursor = conn.cursor()
    methods = []

    predefined_methods = [
        ('Standard Shipping', 'Standard delivery', 5.99, 0.50, 5, 7, True),
        ('Express Shipping', 'Fast delivery', 15.99, 1.00, 2, 3, True),
        ('Next Day Delivery', 'Delivered next business day', 25.99, 1.50, 1, 1, True),
        ('Free Shipping', 'Free standard shipping on orders over $50', 0.00, 0.00, 7, 10, True),
        ('Economy Shipping', 'Budget friendly option', 3.99, 0.30, 10, 14, True),
        ('International Express', 'Fast international delivery', 49.99, 2.00, 3, 7, True),
        ('Same Day Delivery', 'Delivered same day', 35.99, 2.00, 0, 0, False)
    ]

    for i in range(min(num_methods, len(predefined_methods))):
        method_data = predefined_methods[i]
        cursor.execute("""
                       INSERT INTO shipping_methods (method_name, description, base_cost, cost_per_kg,
                                                     estimated_days_min, estimated_days_max, is_active)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       """, method_data)
        methods.append(cursor.lastrowid)

    conn.commit()
    cursor.close()
    print(f"Inserted {len(methods)} shipping methods")
    return methods


def generate_users(conn, num_users):
    cursor = conn.cursor()
    users = []

    for i in range(num_users):
        email = fake.unique.email()
        password_hash = fake.sha256()
        first_name = fake.first_name()
        last_name = fake.last_name()
        phone = fake.phone_number()[:20]
        date_of_birth = fake.date_of_birth(minimum_age=18, maximum_age=80)
        is_active = random.choice([True, True, True, False])
        is_verified = random.choice([True, True, False])
        created_at = fake.date_time_between(start_date='-2y', end_date='now')
        last_login_at = fake.date_time_between(start_date=created_at, end_date='now') if random.random() > 0.3 else None

        cursor.execute("""
                       INSERT INTO users (email, password_hash, first_name, last_name, phone, date_of_birth,
                                          is_active, is_verified, created_at, last_login_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       """, (email, password_hash, first_name, last_name, phone, date_of_birth,
                             is_active, is_verified, created_at, last_login_at))

        users.append(cursor.lastrowid)

    conn.commit()
    cursor.close()
    print(f"Inserted {num_users} users")
    return users


def generate_user_addresses(conn, user_ids, num_addresses):
    cursor = conn.cursor()

    for i in range(num_addresses):
        user_id = random.choice(user_ids)
        address_type = random.choice(['billing', 'shipping', 'both'])
        is_default = random.choice([True, False, False, False])
        full_name = fake.name()
        phone = fake.phone_number()[:20]
        address_line1 = fake.street_address()
        address_line2 = fake.secondary_address() if random.random() > 0.5 else None
        city = fake.city()
        state_province = fake.state()
        postal_code = fake.postcode()
        country = fake.country()

        cursor.execute("""
                       INSERT INTO user_addresses (user_id, address_type, is_default, full_name, phone,
                                                   address_line1, address_line2, city, state_province,
                                                   postal_code, country)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       """, (user_id, address_type, is_default, full_name, phone, address_line1,
                             address_line2, city, state_province, postal_code, country))

    conn.commit()
    cursor.close()
    print(f"Inserted {num_addresses} user addresses")


def generate_categories(conn, num_categories):
    cursor = conn.cursor()
    categories = []

    parent_categories = []
    num_parents = num_categories // 3

    for i in range(num_parents):
        category_name = fake.unique.word().capitalize() + " " + random.choice(
            ['Products', 'Items', 'Goods', 'Collection'])
        slug = category_name.lower().replace(' ', '-')
        description = fake.text(max_nb_chars=200)
        image_url = fake.image_url()
        is_active = random.choice([True, True, True, False])
        sort_order = i

        cursor.execute("""
                       INSERT INTO categories (parent_category_id, category_name, slug, description,
                                               image_url, is_active, sort_order)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       """, (None, category_name, slug, description, image_url, is_active, sort_order))

        parent_categories.append(cursor.lastrowid)
        categories.append(cursor.lastrowid)

    for i in range(num_categories - num_parents):
        parent_id = random.choice(parent_categories) if random.random() > 0.3 else None
        category_name = fake.unique.word().capitalize() + " " + random.choice(['Category', 'Section', 'Department'])
        slug = category_name.lower().replace(' ', '-')
        description = fake.text(max_nb_chars=200)
        image_url = fake.image_url()
        is_active = random.choice([True, True, True, False])
        sort_order = i

        cursor.execute("""
                       INSERT INTO categories (parent_category_id, category_name, slug, description,
                                               image_url, is_active, sort_order)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       """, (parent_id, category_name, slug, description, image_url, is_active, sort_order))

        categories.append(cursor.lastrowid)

    conn.commit()
    cursor.close()
    print(f"Inserted {num_categories} categories")
    return categories


def generate_brands(conn, num_brands):
    cursor = conn.cursor()
    brands = []

    for i in range(num_brands):
        brand_name = fake.unique.company()
        slug = brand_name.lower().replace(' ', '-').replace(',', '').replace('.', '')
        description = fake.catch_phrase()
        logo_url = fake.image_url()
        website_url = fake.url()
        is_active = random.choice([True, True, True, False])

        cursor.execute("""
                       INSERT INTO brands (brand_name, slug, description, logo_url, website_url, is_active)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       """, (brand_name, slug, description, logo_url, website_url, is_active))

        brands.append(cursor.lastrowid)

    conn.commit()
    cursor.close()
    print(f"Inserted {num_brands} brands")
    return brands


def generate_products(conn, brand_ids, num_products):
    cursor = conn.cursor()
    products = []

    for i in range(num_products):
        brand_id = random.choice(brand_ids) if random.random() > 0.2 else None
        product_name = fake.catch_phrase() + " " + random.choice(
            ['Pro', 'Plus', 'Premium', 'Deluxe', 'Standard', 'Basic'])
        slug = product_name.lower().replace(' ', '-')[:500]
        sku = 'SKU-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        description = fake.text(max_nb_chars=500)
        short_description = fake.text(max_nb_chars=150)
        base_price = round(random.uniform(10, 1000), 2)
        compare_at_price = round(base_price * random.uniform(1.1, 1.5), 2) if random.random() > 0.5 else None
        cost_price = round(base_price * random.uniform(0.4, 0.7), 2)
        weight = round(random.uniform(0.1, 50), 2)
        weight_unit = random.choice(['kg', 'g', 'lb', 'oz'])
        is_active = random.choice([True, True, True, False])
        is_featured = random.choice([True, False, False, False, False])
        view_count = random.randint(0, 10000)

        cursor.execute("""
                       INSERT INTO products (brand_id, product_name, slug, sku, description, short_description,
                                             base_price, compare_at_price, cost_price, weight, weight_unit,
                                             is_active, is_featured, view_count)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       """, (brand_id, product_name, slug, sku, description, short_description, base_price,
                             compare_at_price, cost_price, weight, weight_unit, is_active, is_featured, view_count))

        products.append(cursor.lastrowid)

    conn.commit()
    cursor.close()
    print(f"Inserted {num_products} products")
    return products


def generate_product_categories(conn, product_ids, category_ids):
    cursor = conn.cursor()

    for product_id in product_ids:
        num_categories = random.randint(1, 3)
        selected_categories = random.sample(category_ids, min(num_categories, len(category_ids)))

        for idx, category_id in enumerate(selected_categories):
            is_primary = idx == 0
            cursor.execute("""
                           INSERT INTO product_categories (product_id, category_id, is_primary)
                           VALUES (%s, %s, %s)
                           """, (product_id, category_id, is_primary))

    conn.commit()
    cursor.close()
    print(f"Inserted product-category relationships")


def generate_product_images(conn, product_ids, num_images):
    cursor = conn.cursor()

    for i in range(num_images):
        product_id = random.choice(product_ids)
        image_url = fake.image_url()
        alt_text = fake.sentence(nb_words=4)
        is_primary = random.choice([True, False, False, False])
        sort_order = random.randint(0, 10)

        cursor.execute("""
                       INSERT INTO product_images (product_id, image_url, alt_text, is_primary, sort_order)
                       VALUES (%s, %s, %s, %s, %s)
                       """, (product_id, image_url, alt_text, is_primary, sort_order))

    conn.commit()
    cursor.close()
    print(f"Inserted {num_images} product images")


def generate_product_variants(conn, product_ids, num_variants):
    cursor = conn.cursor()
    variants = []

    colors = ['Red', 'Blue', 'Green', 'Black', 'White', 'Yellow', 'Purple', 'Orange', 'Gray', 'Pink']
    sizes = ['XS', 'S', 'M', 'L', 'XL', 'XXL', '32GB', '64GB', '128GB', '256GB']

    for i in range(num_variants):
        product_id = random.choice(product_ids)
        variant_name = random.choice(colors) + " / " + random.choice(sizes)
        sku = 'VAR-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        price_adjustment = round(random.uniform(-50, 100), 2)
        weight_adjustment = round(random.uniform(-5, 10), 2)
        is_active = random.choice([True, True, True, False])

        cursor.execute("""
                       INSERT INTO product_variants (product_id, variant_name, sku, price_adjustment,
                                                     weight_adjustment, is_active)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       """, (product_id, variant_name, sku, price_adjustment, weight_adjustment, is_active))

        variants.append(cursor.lastrowid)

    conn.commit()
    cursor.close()
    print(f"Inserted {num_variants} product variants")
    return variants


def generate_variant_attributes(conn, variant_ids):
    cursor = conn.cursor()

    cursor.execute("SELECT attribute_id, attribute_name FROM product_attributes")
    attributes = cursor.fetchall()

    color_values = ['Red', 'Blue', 'Green', 'Black', 'White', 'Yellow', 'Purple', 'Orange', 'Gray', 'Pink']
    size_values = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
    material_values = ['Cotton', 'Polyester', 'Leather', 'Metal', 'Plastic', 'Wood', 'Glass']
    storage_values = ['32GB', '64GB', '128GB', '256GB', '512GB', '1TB']

    value_map = {
        'color': color_values,
        'size': size_values,
        'material': material_values,
        'storage': storage_values
    }

    for variant_id in variant_ids:
        num_attrs = random.randint(1, 3)
        selected_attrs = random.sample(attributes, min(num_attrs, len(attributes)))

        for attr_id, attr_name in selected_attrs:
            if attr_name in value_map:
                attr_value = random.choice(value_map[attr_name])
            else:
                attr_value = fake.word()

            cursor.execute("""
                           INSERT INTO variant_attributes (variant_id, attribute_id, attribute_value)
                           VALUES (%s, %s, %s)
                           """, (variant_id, attr_id, attr_value))

    conn.commit()
    cursor.close()
    print(f"Inserted variant attributes")


def generate_inventory(conn, product_ids, variant_ids):
    cursor = conn.cursor()

    for product_id in product_ids:
        if random.random() > 0.3:
            quantity_available = random.randint(0, 1000)
            quantity_reserved = random.randint(0, min(50, quantity_available))
            reorder_level = random.randint(5, 50)
            warehouse_location = f"WH-{random.choice(['A', 'B', 'C'])}-{random.randint(1, 100)}"
            last_stock_check = fake.date_time_between(start_date='-30d', end_date='now')

            cursor.execute("""
                           INSERT INTO inventory (product_id, variant_id, quantity_available, quantity_reserved,
                                                  reorder_level, warehouse_location, last_stock_check)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)
                           """, (product_id, None, quantity_available, quantity_reserved, reorder_level,
                                 warehouse_location, last_stock_check))

    for variant_id in variant_ids:
        if random.random() > 0.5:
            cursor.execute("SELECT product_id FROM product_variants WHERE variant_id = %s", (variant_id,))
            result = cursor.fetchone()
            if result:
                product_id = result[0]
                quantity_available = random.randint(0, 500)
                quantity_reserved = random.randint(0, min(30, quantity_available))
                reorder_level = random.randint(5, 30)
                warehouse_location = f"WH-{random.choice(['A', 'B', 'C'])}-{random.randint(1, 100)}"
                last_stock_check = fake.date_time_between(start_date='-30d', end_date='now')

                cursor.execute("""
                               INSERT INTO inventory (product_id, variant_id, quantity_available, quantity_reserved,
                                                      reorder_level, warehouse_location, last_stock_check)
                               VALUES (%s, %s, %s, %s, %s, %s, %s)
                               """, (product_id, variant_id, quantity_available, quantity_reserved, reorder_level,
                                     warehouse_location, last_stock_check))

    conn.commit()
    cursor.close()
    print(f"Inserted inventory records")


def generate_cart_items(conn, user_ids, product_ids, variant_ids, num_items):
    cursor = conn.cursor()

    for i in range(num_items):
        user_id = random.choice(user_ids)
        product_id = random.choice(product_ids)
        variant_id = random.choice(variant_ids) if random.random() > 0.5 else None
        quantity = random.randint(1, 5)

        cursor.execute("SELECT base_price FROM products WHERE product_id = %s", (product_id,))
        result = cursor.fetchone()
        if result:
            base_price = result[0]
            price_adj = 0
            if variant_id:
                cursor.execute("SELECT price_adjustment FROM product_variants WHERE variant_id = %s", (variant_id,))
                var_result = cursor.fetchone()
                if var_result:
                    price_adj = var_result[0]

            price = float(base_price) + float(price_adj)

            cursor.execute("""
                           INSERT INTO cart_items (user_id, product_id, variant_id, quantity, price)
                           VALUES (%s, %s, %s, %s, %s)
                           """, (user_id, product_id, variant_id, quantity, price))

    conn.commit()
    cursor.close()
    print(f"Inserted {num_items} cart items")


def generate_orders(conn, user_ids, product_ids, variant_ids, num_orders):
    cursor = conn.cursor()
    orders = []

    for i in range(num_orders):
        user_id = random.choice(user_ids)
        order_number = 'ORD-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        order_status = random.choice(
            ['pending', 'processing', 'processing', 'shipped', 'shipped', 'delivered', 'delivered', 'cancelled'])
        payment_status = random.choice(['pending', 'paid', 'paid', 'paid', 'failed', 'refunded'])

        num_items = random.randint(1, 8)
        subtotal = 0
        order_items = []

        for j in range(num_items):
            product_id = random.choice(product_ids)
            variant_id = random.choice(variant_ids) if random.random() > 0.6 else None

            cursor.execute("SELECT product_name, sku, base_price FROM products WHERE product_id = %s", (product_id,))
            prod_result = cursor.fetchone()

            if prod_result:
                product_name, sku, base_price = prod_result
                price_adj = 0
                variant_name = None

                if variant_id:
                    cursor.execute(
                        "SELECT variant_name, sku, price_adjustment FROM product_variants WHERE variant_id = %s",
                        (variant_id,))
                    var_result = cursor.fetchone()
                    if var_result:
                        variant_name, sku, price_adj = var_result

                unit_price = float(base_price) + float(price_adj)
                quantity = random.randint(1, 5)
                total_price = unit_price * quantity
                subtotal += total_price

                order_items.append({
                    'product_id': product_id,
                    'variant_id': variant_id,
                    'product_name': product_name,
                    'variant_name': variant_name,
                    'sku': sku,
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'total_price': total_price
                })

        tax_rate = 0.08
        tax_amount = round(subtotal * tax_rate, 2)
        shipping_amount = round(random.uniform(0, 25), 2)
        discount_amount = round(random.uniform(0, subtotal * 0.2), 2) if random.random() > 0.7 else 0
        total_amount = subtotal + tax_amount + shipping_amount - discount_amount

        created_at = fake.date_time_between(start_date='-1y', end_date='now')

        cursor.execute("""
                       INSERT INTO orders (user_id, order_number, order_status, payment_status, subtotal,
                                           tax_amount, shipping_amount, discount_amount, total_amount, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       """, (user_id, order_number, order_status, payment_status, subtotal, tax_amount,
                             shipping_amount, discount_amount, total_amount, created_at))

        order_id = cursor.lastrowid
        orders.append(order_id)

        for item in order_items:
            cursor.execute("""
                           INSERT INTO order_items (order_id, product_id, variant_id, product_name, variant_name,
                                                    sku, quantity, unit_price, total_price)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                           """, (order_id, item['product_id'], item['variant_id'], item['product_name'],
                                 item['variant_name'], item['sku'], item['quantity'], item['unit_price'],
                                 item['total_price']))

        for addr_type in ['billing', 'shipping']:
            cursor.execute("""
                           INSERT INTO order_addresses (order_id, address_type, full_name, phone, address_line1,
                                                        address_line2, city, state_province, postal_code, country)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           """, (order_id, addr_type, fake.name(), fake.phone_number()[:20], fake.street_address(),
                                 None, fake.city(), fake.state(), fake.postcode(), fake.country()))

        cursor.execute("""
                       INSERT INTO order_status_history (order_id, status, notes, created_by, created_at)
                       VALUES (%s, %s, %s, %s, %s)
                       """, (order_id, order_status, f"Order {order_status}", 'system', created_at))

    conn.commit()
    cursor.close()
    print(f"Inserted {num_orders} orders with items and addresses")
    return orders


def generate_transactions(conn, order_ids):
    cursor = conn.cursor()

    cursor.execute("SELECT payment_method_id FROM payment_methods")
    payment_methods = [row[0] for row in cursor.fetchall()]

    for order_id in order_ids:
        cursor.execute("SELECT total_amount, payment_status FROM orders WHERE order_id = %s", (order_id,))
        result = cursor.fetchone()

        if result:
            total_amount, payment_status = result
            payment_method_id = random.choice(payment_methods)

            if payment_status == 'paid':
                transaction_status = 'completed'
            elif payment_status == 'failed':
                transaction_status = 'failed'
            elif payment_status == 'refunded':
                transaction_status = 'completed'
            else:
                transaction_status = random.choice(['pending', 'completed'])

            gateway_transaction_id = 'TXN-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
            processed_at = fake.date_time_between(start_date='-1y',
                                                  end_date='now') if transaction_status == 'completed' else None

            cursor.execute("""
                           INSERT INTO transactions (order_id, payment_method_id, transaction_type, transaction_status,
                                                     amount, gateway_transaction_id, processed_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)
                           """, (order_id, payment_method_id, 'payment', transaction_status, total_amount,
                                 gateway_transaction_id, processed_at))

            if payment_status == 'refunded':
                refund_amount = float(total_amount) * random.uniform(0.5, 1.0)
                refund_txn_id = 'RFD-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
                refund_processed = fake.date_time_between(start_date=processed_at, end_date='now')

                cursor.execute("""
                               INSERT INTO transactions (order_id, payment_method_id, transaction_type,
                                                         transaction_status,
                                                         amount, gateway_transaction_id, processed_at)
                               VALUES (%s, %s, %s, %s, %s, %s, %s)
                               """, (order_id, payment_method_id, 'refund', 'completed', refund_amount,
                                     refund_txn_id, refund_processed))

    conn.commit()
    cursor.close()
    print(f"Inserted transactions for orders")


def generate_shipments(conn, order_ids):
    cursor = conn.cursor()

    cursor.execute("SELECT shipping_method_id FROM shipping_methods")
    shipping_methods = [row[0] for row in cursor.fetchall()]

    for order_id in order_ids:
        cursor.execute("SELECT order_status FROM orders WHERE order_id = %s", (order_id,))
        result = cursor.fetchone()

        if result and result[0] in ['shipped', 'delivered']:
            shipping_method_id = random.choice(shipping_methods)
            tracking_number = 'TRK-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
            carrier = random.choice(['FedEx', 'UPS', 'DHL', 'USPS', 'Canada Post'])

            shipped_at = fake.date_time_between(start_date='-6m', end_date='now')
            estimated_delivery = shipped_at + timedelta(days=random.randint(2, 10))

            if result[0] == 'delivered':
                shipment_status = 'delivered'
                delivered_at = fake.date_time_between(start_date=shipped_at, end_date='now')
            else:
                shipment_status = random.choice(['shipped', 'in_transit'])
                delivered_at = None

            cursor.execute("""
                           INSERT INTO shipments (order_id, shipping_method_id, tracking_number, carrier,
                                                  shipped_at, estimated_delivery, delivered_at, shipment_status)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                           """, (order_id, shipping_method_id, tracking_number, carrier, shipped_at,
                                 estimated_delivery, delivered_at, shipment_status))

    conn.commit()
    cursor.close()
    print(f"Inserted shipments for delivered/shipped orders")


def generate_reviews(conn, user_ids, product_ids, order_ids, num_reviews):
    cursor = conn.cursor()

    for i in range(num_reviews):
        product_id = random.choice(product_ids)
        user_id = random.choice(user_ids)
        order_id = random.choice(order_ids) if random.random() > 0.3 else None
        rating = random.choices([1, 2, 3, 4, 5], weights=[5, 10, 15, 30, 40])[0]
        title = fake.sentence(nb_words=6)
        review_text = fake.text(max_nb_chars=500)
        is_verified_purchase = order_id is not None
        is_approved = random.choice([True, True, True, False])
        helpful_count = random.randint(0, 100)
        created_at = fake.date_time_between(start_date='-1y', end_date='now')

        cursor.execute("""
                       INSERT INTO product_reviews (product_id, user_id, order_id, rating, title, review_text,
                                                    is_verified_purchase, is_approved, helpful_count, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       """, (product_id, user_id, order_id, rating, title, review_text, is_verified_purchase,
                             is_approved, helpful_count, created_at))

    conn.commit()
    cursor.close()
    print(f"Inserted {num_reviews} product reviews")


def generate_coupons(conn, num_coupons):
    cursor = conn.cursor()
    coupons = []

    for i in range(num_coupons):
        coupon_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        description = fake.sentence(nb_words=8)
        discount_type = random.choice(['percentage', 'fixed_amount'])

        if discount_type == 'percentage':
            discount_value = random.choice([5, 10, 15, 20, 25, 30])
            max_discount_amount = random.choice([50, 100, 200]) if random.random() > 0.5 else None
        else:
            discount_value = random.choice([5, 10, 15, 20, 25, 50])
            max_discount_amount = None

        min_order_amount = random.choice([25, 50, 75, 100]) if random.random() > 0.3 else None
        usage_limit = random.choice([100, 500, 1000, None])
        usage_count = random.randint(0, usage_limit if usage_limit else 500)
        usage_per_user = random.choice([1, 2, 3])
        is_active = random.choice([True, True, False])

        valid_from = fake.date_time_between(start_date='-3m', end_date='now')
        valid_until = valid_from + timedelta(days=random.randint(30, 180))

        cursor.execute("""
                       INSERT INTO coupons (coupon_code, description, discount_type, discount_value,
                                            min_order_amount, max_discount_amount, usage_limit, usage_count,
                                            usage_per_user, is_active, valid_from, valid_until)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       """, (coupon_code, description, discount_type, discount_value, min_order_amount,
                             max_discount_amount, usage_limit, usage_count, usage_per_user, is_active,
                             valid_from, valid_until))

        coupons.append(cursor.lastrowid)

    conn.commit()
    cursor.close()
    print(f"Inserted {num_coupons} coupons")
    return coupons


def generate_coupon_usage(conn, coupon_ids, order_ids):
    cursor = conn.cursor()

    used_orders = set()

    for coupon_id in coupon_ids:
        cursor.execute("""
                       SELECT discount_type, discount_value, max_discount_amount, usage_count, usage_limit
                       FROM coupons
                       WHERE coupon_id = %s
                       """, (coupon_id,))
        result = cursor.fetchone()

        if result:
            discount_type, discount_value, max_discount_amount, usage_count, usage_limit = result

            num_uses = min(usage_count, random.randint(0, 20))

            for i in range(num_uses):
                available_orders = [oid for oid in order_ids if oid not in used_orders]
                if not available_orders:
                    break

                order_id = random.choice(available_orders)
                used_orders.add(order_id)

                cursor.execute("SELECT subtotal, user_id FROM orders WHERE order_id = %s", (order_id,))
                order_result = cursor.fetchone()

                if order_result:
                    subtotal, user_id = order_result

                    if discount_type == 'percentage':
                        discount_amount = float(subtotal) * (float(discount_value) / 100)
                        if max_discount_amount:
                            discount_amount = min(discount_amount, float(max_discount_amount))
                    else:
                        discount_amount = float(discount_value)

                    discount_amount = round(discount_amount, 2)

                    cursor.execute("""
                                   INSERT INTO coupon_usage (coupon_id, user_id, order_id, discount_amount)
                                   VALUES (%s, %s, %s, %s)
                                   """, (coupon_id, user_id, order_id, discount_amount))

    conn.commit()
    cursor.close()
    print(f"Inserted coupon usage records")


def generate_wishlists(conn, user_ids, product_ids, variant_ids, num_wishlists):
    cursor = conn.cursor()

    for i in range(num_wishlists):
        user_id = random.choice(user_ids)
        product_id = random.choice(product_ids)
        variant_id = random.choice(variant_ids) if random.random() > 0.6 else None

        try:
            cursor.execute("""
                           INSERT INTO wishlists (user_id, product_id, variant_id)
                           VALUES (%s, %s, %s)
                           """, (user_id, product_id, variant_id))
        except mysql.connector.IntegrityError:
            pass

    conn.commit()
    cursor.close()
    print(f"Inserted wishlist items")


def main():
    print("Connecting to database...")
    conn = get_db_connection()

    print("\n=== Clearing Existing Data ===")
    clear_existing_data(conn)

    print("\n=== Generating Base Configuration ===")
    generate_product_attributes(conn, NUM_PRODUCT_ATTRIBUTES)
    generate_payment_methods(conn, NUM_PAYMENT_METHODS)
    generate_shipping_methods(conn, NUM_SHIPPING_METHODS)

    print("\n=== Generating Users ===")
    user_ids = generate_users(conn, NUM_USERS)
    generate_user_addresses(conn, user_ids, NUM_USER_ADDRESSES)

    print("\n=== Generating Product Catalog ===")
    category_ids = generate_categories(conn, NUM_CATEGORIES)
    brand_ids = generate_brands(conn, NUM_BRANDS)
    product_ids = generate_products(conn, brand_ids, NUM_PRODUCTS)
    generate_product_categories(conn, product_ids, category_ids)
    generate_product_images(conn, product_ids, NUM_PRODUCT_IMAGES)

    print("\n=== Generating Product Variants ===")
    variant_ids = generate_product_variants(conn, product_ids, NUM_PRODUCT_VARIANTS)
    generate_variant_attributes(conn, variant_ids)

    print("\n=== Generating Inventory ===")
    generate_inventory(conn, product_ids, variant_ids)

    print("\n=== Generating Shopping Cart ===")
    generate_cart_items(conn, user_ids, product_ids, variant_ids, NUM_CART_ITEMS)

    print("\n=== Generating Orders ===")
    order_ids = generate_orders(conn, user_ids, product_ids, variant_ids, NUM_ORDERS)
    generate_transactions(conn, order_ids)
    generate_shipments(conn, order_ids)

    print("\n=== Generating Reviews ===")
    generate_reviews(conn, user_ids, product_ids, order_ids, NUM_REVIEWS)

    print("\n=== Generating Coupons ===")
    coupon_ids = generate_coupons(conn, NUM_COUPONS)
    generate_coupon_usage(conn, coupon_ids, user_ids)

    print("\n=== Generating Wishlists ===")
    generate_wishlists(conn, user_ids, product_ids, variant_ids, NUM_WISHLISTS)

    conn.close()
    print("\n✓ Data generation complete!")
    print(f"\nSummary:")
    print(f"  Users: {NUM_USERS}")
    print(f"  Products: {NUM_PRODUCTS}")
    print(f"  Product Variants: {NUM_PRODUCT_VARIANTS}")
    print(f"  Orders: {NUM_ORDERS}")
    print(f"  Reviews: {NUM_REVIEWS}")
    print(f"  Coupons: {NUM_COUPONS}")


if __name__ == "__main__":
    main()
