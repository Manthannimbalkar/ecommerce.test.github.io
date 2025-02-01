from flask import Flask, render_template, jsonify,request
from flask_mysqldb import MySQL
import datetime
import json


app = Flask(__name__)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'ecommerce_web'
app.config['MYSQL_PASSWORD'] = 'web@123'
app.config['MYSQL_DB'] = 'ecommerce_web'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)


def format_currency(value):
    if value >= 1_00_00_000:  # 1 Crore
        return f'₹{value / 1_00_00_000:.2f} Cr'
    elif value >= 1_00_000:  # 1 Lakh
        return f'₹{value / 1_00_000:.2f} L'
    else:
        return f'₹{value:,.2f}'  # Adds comma separator

# Home Route
@app.route('/')
def home():
    return render_template('index.html')


# Route to fetch all customers
@app.route('/customers')
def get_customers():
   return render_template('customers.html')


# Route to fetch all products
@app.route('/products', methods=['GET'])
def get_products():
    try:
        # Pagination logic
        page = int(request.args.get('page', 1))  # Get current page from query parameter, default to 1
        per_page = 20  # Number of products per page
        offset = (page - 1) * per_page

        cur = mysql.connection.cursor()
        
        # Fetch unique categories and brands for filters
        cur.execute("SELECT DISTINCT category FROM products")
        categories = [row['category'] for row in cur.fetchall()]
        
        cur.execute("SELECT DISTINCT brand FROM products")
        brands = [row['brand'] for row in cur.fetchall()]
        
        # Fetch total product count
        cur.execute("SELECT COUNT(*) as total FROM products")
        total_products = cur.fetchone()['total']
        
        # Fetch products for the current page
        cur.execute(f"SELECT * FROM products LIMIT {per_page} OFFSET {offset}")
        products = cur.fetchall()
        cur.close()
        
        # Supported currencies for conversion
        currencies = ["USD", "EUR", "INR"]  # Add more as needed
        
        return render_template(
            'products.html',
            products=products,
            categories=categories,
            brands=brands,
            currencies=currencies,
            total_pages=(total_products // per_page) + (1 if total_products % per_page > 0 else 0),
            current_page=page
        )
    except Exception as e:
        return render_template('error.html', error=str(e))


# Route to fetch all order details
@app.route('/order-details')
def get_order_details():
    try:
        cur = mysql.connection.cursor()
        
        # Execute the query to fetch order details
        cur.execute("""
            SELECT 
                products.product_name, 
                order_details.order_date, 
                COUNT(order_details.item_id) AS total_orders, 
                SUM(products.price) AS total_amount
            FROM order_details
            JOIN products ON products.product_id = order_details.item_id
            GROUP BY products.product_name, order_details.order_date
        """)
        order_details = cur.fetchall()  # Fetch data as a list of dictionaries
        cur.close()
        
        # Pass data to the template
        return render_template('order_details.html', orders=order_details)
    except Exception as e:
        return jsonify({"error": str(e)})



# Route to fetch customer by ID
@app.route('/customer/<int:customer_id>')
def get_customer_by_id(customer_id):
    try:
        cur = mysql.connection.cursor()
        query = "SELECT * FROM customers WHERE customer_id = %s"
        cur.execute(query, (customer_id,))
        customer = cur.fetchone()
        cur.close()
        if customer:
            return jsonify(customer)
        else:
            return jsonify({"message": "Customer not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)})
    

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    cur = mysql.connection.cursor()
    
    # Query to get the minimum and maximum order dates
    cur.execute("SELECT MIN(order_date) AS min_date, MAX(order_date) AS max_date FROM order_details")
    date_range = cur.fetchone()
    min_date = date_range['min_date']
    max_date = date_range['max_date']
    
    # Query to get the available countries
    cur.execute("SELECT DISTINCT country FROM customers")
    countries = cur.fetchall()
    
    # Get date range and country filter from the request if provided
    start_date = request.args.get('start_date')  # Format 'YYYY-MM-DD'
    end_date = request.args.get('end_date')      # Format 'YYYY-MM-DD'
    country_filter = request.args.get('country')  # Example: 'USA'

    # Query to count total customers
    cur.execute("SELECT COUNT(*) AS total_customers FROM customers")
    total_customers = cur.fetchone()['total_customers']
    
    # Query to count total products
    cur.execute("SELECT COUNT(*) AS total_products FROM products")
    total_products = cur.fetchone()['total_products']
    
    # Query to count total orders
    cur.execute("SELECT COUNT(*) AS total_orders FROM order_details")
    total_orders = cur.fetchone()['total_orders']
    
    # Query to get total orders per product category
    cur.execute("""
        SELECT products.category, COUNT(order_details.item_id) AS total_orders, SUM(products.price) as total_amount
        FROM order_details
        JOIN products ON products.product_id = order_details.item_id
        GROUP BY products.category
    """)
    category_orders = cur.fetchall()

    # Query to get top 5 most sold products
    cur.execute("""  
    SELECT products.product_name, COUNT(order_details.item_id) AS total_orders, SUM(products.price) as total_amount, products.category
        FROM order_details
        JOIN products ON products.product_id = order_details.item_id
        GROUP BY products.product_name
        ORDER BY total_amount DESC
        LIMIT 5;
                 """)
    most_sold = cur.fetchall()

    # Query to get order details by country (with optional country filter)
    country_filter_sql = ""
    country_params = ()
    if country_filter:
        country_filter_sql = "WHERE customers.country = %s"
        country_params = (country_filter,)  # Tuple with one value

    cur.execute(f""" 
    SELECT customers.country, COUNT(order_details.item_id) AS total_orders, SUM(products.price) as total_amount
        FROM order_details
        JOIN products ON products.product_id = order_details.item_id
        JOIN customers ON customers.customer_id = order_details.order_id
        {country_filter_sql}
        GROUP BY customers.country;
    """, country_params)
    country_details = cur.fetchall()

    # Query to get total orders by payment method
    cur.execute(""" 
    SELECT payment_method, COUNT(order_id) AS total_orders
    FROM order_details
    GROUP BY payment_method;
               """)
    payment_data = cur.fetchall()

    # Query to get total orders by date range (if start_date and end_date are provided)
    date_filter_sql = ""
    date_params = ()
    if start_date and end_date:
        date_filter_sql = "WHERE order_details.order_date BETWEEN %s AND %s"
        date_params = (start_date, end_date)  # Tuple with both start_date and end_date
    
    cur.execute(f""" 
    SELECT order_details.order_date, COUNT(order_details.order_id) AS total_orders
    FROM order_details
    JOIN customers ON customers.customer_id = order_details.order_id
    {date_filter_sql}
    GROUP BY order_details.order_date;
               """, date_params)
    datewise_data = cur.fetchall()

# Fetch Data from SQL
    cur.execute("""
    SELECT DATE_FORMAT(order_details.order_time, '%h %p') AS order_hour, 
           COUNT(order_details.order_id) AS total_orders
    FROM order_details
    JOIN customers ON customers.customer_id = order_details.order_id
    GROUP BY order_hour
    ORDER BY STR_TO_DATE(order_hour, '%h %p');
    """)

    time_wise_data = cur.fetchall()

    cur.execute("""
    SELECT SUM(p.price) AS total_earned 
    FROM order_details od
    LEFT JOIN products p ON p.product_id = od.item_id;
""")

    total_earned = cur.fetchone()['total_earned']
    formatted_earned = format_currency(total_earned)


    # Ensure the cursor is closed
    cur.close()

    # Pass the counts and category orders to the dashboard template
    return render_template(
        'dashboard.html',
        total_customers=total_customers,
        total_products=total_products,
        total_orders=total_orders,
        category_orders=category_orders,
        most_sold=most_sold,
        country_details=country_details,
        payment_data=payment_data,
        datewise_data=datewise_data,
        min_date=min_date,
        max_date=max_date,
        countries=countries,
        start_date=start_date,
        end_date=end_date,
        country_filter=country_filter,
        time_wise_data = time_wise_data,
        formatted_earned = formatted_earned
    )



    
@app.route('/category/<category_name>')
def category_details(category_name):
    try:
        # Create database connection and cursor
        cur = mysql.connection.cursor()
    
        # Query database or get filtered data based on category_name
        query = """
            SELECT products.product_name, COUNT(order_details.item_id) AS total_orders, 
                   SUM(products.price) AS total_amount
            FROM order_details
            JOIN products ON products.product_id = order_details.item_id
            WHERE products.category = %s  # Add the filtering by category
            GROUP BY products.product_name;
        """
        
        # Execute the query with category_name as the filter
        cur.execute(query, (category_name,))
        
        # Fetch all results
        filtered_products = cur.fetchall()
        
        # Close the cursor
        cur.close()
        
        # Render the template and pass the category_name and filtered products
        return render_template('category_details.html', category_name=category_name, products=filtered_products)
    except Exception as e:
        # Handle any errors
        return str(e)



if __name__ == '__main__':
    app.run(debug=True)


