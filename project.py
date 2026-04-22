from collections import defaultdict
from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from datetime import datetime, timedelta
from datetime import date

app = Flask(__name__)
app.secret_key = 'secret_key'  

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Noor@2004',
    'database': 'resmanag'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# ----- LOGIN SYSTEM -----
@app.route('/', methods=['GET']) 
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['GET','POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    selected_role = request.form.get('role')

    if not username or not password or not selected_role:
        flash('Please fill in all fields.', 'danger')
        return redirect(url_for('login_page'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM Users WHERE Username = %s AND Password = %s', (username, password))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        if user['Role'].strip().lower() != selected_role.strip().lower():
            flash('Incorrect role selected. Please try again.', 'danger')
            return redirect(url_for('login_page'))

        session['username'] = user['Username']
        session['role'] = user['Role'].strip().lower()

        flash('Login successful!', 'success')
        
        # Redirect based on role
        if session['role'] == 'manager':
            return redirect(url_for('manager_dashboard'))
        elif session['role'] == 'employee':
            return redirect(url_for('employee_dashboard'))
        else:
            flash('Unknown role.', 'danger')
            return redirect(url_for('login_page'))
    else:
        flash('Invalid username or password.', 'danger')
        return redirect(url_for('login_page'))
    
@app.route('/manager_dashboard')
def manager_dashboard():
    if session.get('role') != 'manager':
        flash("Access denied.", "danger")
        return redirect(url_for('login_page'))
    return render_template('manager_dashboard.html')

@app.route('/employee_dashboard')
def employee_dashboard():
    if session.get('role') != 'employee':
        flash("Access denied.", "danger")
        return redirect(url_for('login_page'))
    return render_template('employee_dashboard.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login_page'))
    return render_template('dashboard.html', username=session['username'], role=session['role'])


@app.route('/products')
def products():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. All products + supplier name
    cursor.execute('''
        SELECT p.*, s.Name AS SupplierName
        FROM Products p
        LEFT JOIN Suppliers s ON p.SupplierID = s.SupplierID
        ORDER BY p.ProductID
    ''')
    products = cursor.fetchall()

    # 2. Most sold product (by quantity)
    cursor.execute('''
        SELECT 
            p.ProductID,
            p.Name,
            SUM(si.Quantity) AS TotalQuantity
        FROM SaleItems si
        JOIN Products p ON si.ProductID = p.ProductID
        GROUP BY p.ProductID, p.Name
        ORDER BY TotalQuantity DESC
        LIMIT 1
    ''')
    most_sold = cursor.fetchone()

    # 3. Top 5 products by quantity sold (for chart)
    cursor.execute('''
        SELECT 
            p.ProductID,
            p.Name,
            SUM(si.Quantity) AS TotalQuantity
        FROM SaleItems si
        JOIN Products p ON si.ProductID = p.ProductID
        GROUP BY p.ProductID, p.Name
        ORDER BY TotalQuantity DESC
        LIMIT 5
    ''')
    top_products = cursor.fetchall() or []

    # 4. Total products in stock
    cursor.execute('SELECT SUM(StockQuantity) AS TotalStock FROM Products')
    total_stock = cursor.fetchone()['TotalStock'] or 0

    # 5. Expired products count
    today_str = date.today().strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT COUNT(*) AS ExpiredCount
        FROM Products
        WHERE ExpiryDate < %s AND StockQuantity > 0
    ''', (today_str,))
    expired_count = cursor.fetchone()['ExpiredCount'] or 0

    # 6. Category with most expired products
    cursor.execute('''
        SELECT Category, SUM(StockQuantity) AS ExpiredStock
        FROM Products
        WHERE ExpiryDate < %s AND StockQuantity > 0
        GROUP BY Category
        ORDER BY ExpiredStock DESC
        LIMIT 1
    ''', (today_str,))
    expired_category = cursor.fetchone()

    # 7. Supplier with highest stock
    cursor.execute('''
        SELECT s.SupplierID, s.Name AS SupplierName, SUM(p.StockQuantity) AS TotalStock
        FROM Products p
        JOIN Suppliers s ON p.SupplierID = s.SupplierID
        GROUP BY s.SupplierID, s.Name
        ORDER BY TotalStock DESC
        LIMIT 1
    ''')
    top_supplier = cursor.fetchone()

    # 8. Total value of all stock
    cursor.execute('''
        SELECT SUM(Price * StockQuantity) AS TotalValue
        FROM Products
        WHERE Price IS NOT NULL AND StockQuantity IS NOT NULL
    ''')
    total_value = cursor.fetchone()['TotalValue'] or 0.0

    # 9. Total value of expired products
    cursor.execute('''
        SELECT SUM(Price) AS TotalExpiredValue
        FROM Products
        WHERE ExpiryDate < '2025-10-06'
    ''')
    total_price = cursor.fetchone()

    # 10. Product with highest revenue
    cursor.execute('''
        SELECT 
            p.ProductID,
            p.Name,
            SUM(si.Quantity * p.Price) AS TotalRevenue
        FROM SaleItems si
        JOIN Products p ON si.ProductID = p.ProductID
        GROUP BY p.ProductID, p.Name
        ORDER BY TotalRevenue DESC
        LIMIT 1
    ''')
    highest_revenue_product = cursor.fetchone()

    # 11. Total products sold per supplier
    cursor.execute('''
        SELECT 
            s.SupplierID,
            s.Name AS SupplierName,
            SUM(si.Quantity) AS TotalSold
        FROM SaleItems si
        JOIN Products p ON si.ProductID = p.ProductID
        JOIN Suppliers s ON p.SupplierID = s.SupplierID
        GROUP BY s.SupplierID, s.Name
        ORDER BY TotalSold DESC
    ''')
    products_sold_per_supplier = cursor.fetchall()

    # Done
    cursor.close()
    conn.close()

    return render_template(
        'products.html',
        products=products,
        most_sold=most_sold,
        top_products=top_products,
        total_stock=total_stock,
        expired_count=expired_count,
        expired_category=expired_category,
        top_supplier=top_supplier,
        total_value=total_value,
        total_price=total_price['TotalExpiredValue'] if total_price and total_price['TotalExpiredValue'] else 0,
        highest_revenue_product=highest_revenue_product,
        products_sold_per_supplier=products_sold_per_supplier
    )

@app.route('/products/add', methods=['GET', 'POST'])
def add_product():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        expiry_date = request.form['expiry']
        price = request.form['price'] or None
        stock = request.form['stock'] or None
        supplier_id = request.form['supplier'] or None

        try:
            expiry = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            price = float(price) if price else None
            stock = int(stock) if stock else None
            supplier_id = int(supplier_id) if supplier_id else None
        except ValueError:
            flash('Invalid input format.', 'danger')
            return redirect(url_for('add_product'))

        cursor.execute('''
            INSERT INTO products (Name, Category, ExpiryDate, Price, StockQuantity, SupplierID)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (name, category, expiry, price, stock, supplier_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Product added successfully!', 'success')
        return redirect(url_for('products'))

    # GET method: Fetch suppliers for the dropdown
    cursor.execute('SELECT SupplierID, Name FROM suppliers ORDER BY Name')
    suppliers = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('add_product.html', suppliers=suppliers)


@app.route('/products/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM products WHERE ProductID = %s', (id,))
    product = cursor.fetchone()

    if not product:
        flash('Product not found!', 'danger')
        return redirect(url_for('products'))

    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        expiry_date = request.form['expiry_date']
        price = request.form['price'] or None
        stock = request.form['stock'] or None

        try:
            expiry = datetime.strptime(expiry_date, '%Y-%m-%d').date()
            price = float(price) if price else None
            stock = int(stock) if stock else None
        except ValueError:
            flash('Invalid input format.', 'danger')
            return redirect(url_for('edit_product', id=id))

        cursor.execute('''
            UPDATE products
            SET Name=%s, Category=%s, ExpiryDate=%s, Price=%s, StockQuantity=%s
            WHERE ProductID=%s
        ''', (name, category, expiry, price, stock, id))
        conn.commit()
        flash('Product updated successfully!', 'success')

        cursor.execute('SELECT * FROM products WHERE ProductID = %s', (id,))
        product = cursor.fetchone()

    cursor.close()
    conn.close()
    return render_template('edit_product.html', product=product)

@app.route('/products/delete/<int:id>', methods=['POST'])
def delete_product(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM products WHERE ProductID = %s', (id,))
        conn.commit()
        flash('Product deleted successfully!', 'success')
    except mysql.connector.IntegrityError:
        flash('Cannot delete this product. It is referenced in existing sales records.', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('products'))

@app.route('/most_sold_product')
def most_sold_product():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT 
            p.ProductID,
            p.Name,
            SUM(si.Quantity) AS TotalSoldQuantity
        FROM SaleItems si
        JOIN Products p ON si.ProductID = p.ProductID
        GROUP BY p.ProductID, p.Name
        ORDER BY TotalSoldQuantity DESC
        LIMIT 1;
    """
    cursor.execute(query)
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template('most_sold_product.html', product=product)

@app.route('/customers')
def customers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all customers
    cursor.execute("SELECT * FROM Customers ORDER BY CustomerID")
    customers = cursor.fetchall()

    # Fetch top customer by sales (as before)
    cursor.execute('''
        SELECT 
            c.CustomerID,
            c.Name,
            c.ContactInfo,
            c.TotalDebts,
            IFNULL(SUM(s.TotalAmount), 0) AS total_sales
        FROM Customers c
        LEFT JOIN Sales s ON c.CustomerID = s.CustomerID
        GROUP BY c.CustomerID, c.Name, c.ContactInfo, c.TotalDebts
        ORDER BY total_sales DESC
        LIMIT 1;
    ''')
    top_customer = cursor.fetchone()

    cursor.close()
    conn.close()

    # Prepare top 5 customers by debt in Python
    top5_by_debt = sorted(customers, key=lambda c: c['TotalDebts'], reverse=True)[:5]

    return render_template("customers.html", customers=customers, top_customer=top_customer, top5_by_debt=top5_by_debt)

@app.route('/customers/add', methods=['GET', 'POST'])
def add_customer():
    if request.method == 'POST':
        name = request.form['name']
        contact_info = request.form['contact_info']
        total_debts = request.form['total_debts'] or 0
        
        try:
            total_debts = int(total_debts)
        except ValueError:
            flash('Total debts must be an integer.', 'danger')
            return redirect(url_for('add_customer'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO Customers (Name, ContactInfo, TotalDebts)
            VALUES (%s, %s, %s)
        ''', (name, contact_info, total_debts))
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Customer added successfully!', 'success')
        return redirect(url_for('customers'))
    
    return render_template('add_customer.html')
@app.route('/customers/edit/<int:id>', methods=['GET', 'POST'])
def edit_customer(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute('SELECT * FROM Customers WHERE CustomerID = %s', (id,))
    customer = cursor.fetchone()
    
    if not customer:
        flash('Customer not found!', 'danger')
        return redirect(url_for('customers'))
    
    if request.method == 'POST':
        name = request.form['name']
        contact_info = request.form['contact_info']
        total_debts = request.form['total_debts'] or 0
        
        try:
            total_debts = int(total_debts)
        except ValueError:
            flash('Total debts must be an integer.', 'danger')
            return redirect(url_for('edit_customer', id=id))
        
        cursor.execute('''
            UPDATE Customers
            SET Name=%s, ContactInfo=%s, TotalDebts=%s
            WHERE CustomerID=%s
        ''', (name, contact_info, total_debts, id))
        conn.commit()
        
        flash('Customer updated successfully!', 'success')
        
        # refresh the customer data after update
        cursor.execute('SELECT * FROM Customers WHERE CustomerID = %s', (id,))
        customer = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return render_template('edit_customer.html', customer=customer)
@app.route('/customers/delete/<int:id>', methods=['POST'])
def delete_customer(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM Customers WHERE CustomerID = %s', (id,))
        conn.commit()
        flash('Customer deleted successfully!', 'success')
    except mysql.connector.IntegrityError:
        flash('Cannot delete this customer due to existing dependencies.', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('customers'))

# List suppliers# List suppliers
@app.route('/suppliers')
def suppliers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get all suppliers
    cursor.execute("SELECT * FROM Suppliers")
    suppliers = cursor.fetchall()

    # Get products grouped by SupplierID
    cursor.execute("SELECT SupplierID, Name FROM Products")
    product_rows = cursor.fetchall()

    products_by_supplier = {}
    for row in product_rows:
        supplier_id = row['SupplierID']
        product_name = row['Name']
        products_by_supplier.setdefault(supplier_id, []).append(product_name)

    # Get top supplier
    cursor.execute("SELECT Name, PurchaseMoney FROM Suppliers ORDER BY PurchaseMoney DESC LIMIT 1")
    top_supplier = cursor.fetchone()

    conn.close()

    # Convert PurchaseMoney to float for JSON serialization if needed
    for supplier in suppliers:
        # If PurchaseMoney is decimal.Decimal, convert to float
        pm = supplier.get('PurchaseMoney')
        if pm is not None:
            supplier['PurchaseMoney'] = float(pm)

    return render_template(
        "suppliers.html",
        suppliers=suppliers,
        top_supplier=top_supplier,
        products_by_supplier=products_by_supplier
    )

# Add supplier

@app.route('/add_supplier', methods=['GET', 'POST'])
def add_supplier():
    if request.method == 'POST':
        name = request.form.get('name')  # corrected
        contact = request.form.get('contact_info')  # corrected
        purchase_money = request.form.get('purchase_money') or 0  # make sure it's optional or required in HTML

        try:
            purchase_money = float(purchase_money)
        except ValueError:
            flash('Purchase money must be a number.', 'danger')
            return redirect(url_for('add_supplier'))

        conn = get_db_connection()  # FIXED: you had `mysql.connector.connect(...)`
        cursor = conn.cursor()
        sql = "INSERT INTO Suppliers (Name, ContactInfo, PurchaseMoney) VALUES (%s, %s, %s)"
        cursor.execute(sql, (name, contact, purchase_money))
        conn.commit()
        cursor.close()
        conn.close()

        flash('Supplier added successfully!', 'success')
        return redirect(url_for('suppliers'))

    return render_template('add_supplier.html')
@app.route('/suppliers_top')
def suppliers_top():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM suppliers ORDER BY SupplierID')
    suppliers = cursor.fetchall()

    cursor.execute('SELECT * FROM suppliers ORDER BY PurchaseMoney DESC LIMIT 1')
    top_supplier = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template('suppliers.html', suppliers=suppliers, top_supplier=top_supplier)

# Edit supplier
@app.route('/suppliers/edit/<int:id>', methods=['GET', 'POST'])
def edit_supplier(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM suppliers WHERE SupplierID = %s', (id,))
    supplier = cursor.fetchone()

    if not supplier:
        flash('Supplier not found!', 'danger')
        return redirect(url_for('suppliers'))

    if request.method == 'POST':
        name = request.form['name']
        contact_info = request.form['contact_info']

        cursor.execute('UPDATE suppliers SET Name=%s, ContactInfo=%s WHERE SupplierID=%s', (name, contact_info, id))
        conn.commit()
        flash('Supplier updated successfully!', 'success')

        cursor.execute('SELECT * FROM suppliers WHERE SupplierID = %s', (id,))
        supplier = cursor.fetchone()

    cursor.close()
    conn.close()
    return render_template('edit_supplier.html', supplier=supplier)

# Delete supplier
@app.route('/suppliers/delete/<int:id>', methods=['POST'])
def delete_supplier(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM suppliers WHERE SupplierID = %s', (id,))
        conn.commit()
        flash('Supplier deleted successfully!', 'success')
    except mysql.connector.IntegrityError:
        flash('Cannot delete this supplier. It is referenced elsewhere.', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('suppliers'))

@app.route('/sales', methods=['GET', 'POST'])
def sales():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all sales with customer names
    cursor.execute('''
        SELECT Sales.SaleID, Customers.Name AS CustomerName, Sales.SaleDate, 
               Sales.TotalAmount, Sales.TaxAmount, Sales.PaymentMethod, Sales.CustomerID
        FROM Sales
        LEFT JOIN Customers ON Sales.CustomerID = Customers.CustomerID
        ORDER BY Sales.SaleDate DESC
    ''')
    sales = cursor.fetchall()

    # Summary statistics
    total_sales = len(sales)
    total_revenue = sum(sale['TotalAmount'] for sale in sales)
    total_taxes = sum(sale['TaxAmount'] for sale in sales if sale['TaxAmount'] is not None)
    average_sale = total_revenue / total_sales if total_sales else 0
    unique_customers = len(set(sale['CustomerName'] for sale in sales if sale['CustomerName']))

    # Customers for dropdown
    cursor.execute('SELECT CustomerID, Name FROM Customers ORDER BY Name')
    customers = cursor.fetchall()

    # Handle filtering
    selected_customer_id = request.args.get('customer_id', type=int)
    customer_purchase_count = None
    customer_name = None

    if selected_customer_id:
        cursor.execute('''
            SELECT COUNT(*) AS PurchaseCount
            FROM Sales
            WHERE CustomerID = %s
        ''', (selected_customer_id,))
        customer_purchase_count = cursor.fetchone()['PurchaseCount']

        cursor.execute('SELECT Name FROM Customers WHERE CustomerID = %s', (selected_customer_id,))
        result = cursor.fetchone()
        customer_name = result['Name'] if result else 'Unknown'

    # Most common payment method
    cursor.execute('''
        SELECT PaymentMethod, COUNT(*) AS MethodCount
        FROM Sales
        GROUP BY PaymentMethod
        ORDER BY MethodCount DESC
        LIMIT 1
    ''')
    result = cursor.fetchone()
    most_common_payment_method = result['PaymentMethod'] if result else 'N/A'

    cursor.close()
    conn.close()

    return render_template(
        'sales.html',
        sales=sales,
        total_sales=total_sales,
        total_revenue=total_revenue,
        total_taxes=total_taxes,  # added
        average_sale=average_sale,
        unique_customers=unique_customers,
        customers=customers,
        selected_customer_id=selected_customer_id,
        customer_purchase_count=customer_purchase_count,
        customer_name=customer_name,
        most_common_payment_method=most_common_payment_method
    )

@app.route('/add_sale', methods=['GET', 'POST'])
def add_sale():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        sale_date = request.form['sale_date']
        payment_method = request.form['payment_method']
        customer_id = request.form['customer_id']

        product_ids = request.form.getlist('product_id')
        quantities = request.form.getlist('quantity')

        try:
            if not product_ids or not any(quantities):
                flash('At least one product must be selected with a quantity.', 'danger')
                return redirect(url_for('add_sale'))

            total_amount = 0.0
            tax_amount = 0.0
            item_data = []

            for pid, qty in zip(product_ids, quantities):
                if not qty.strip() or int(qty) <= 0:
                    continue

                cursor.execute("SELECT Price, CostPrice FROM Products WHERE ProductID = %s", (pid,))
                product = cursor.fetchone()
                if not product:
                    continue

                price = float(product['Price'])
                cost = float(product['CostPrice'])
                qty = int(qty)

                item_total = price * qty
                total_amount += item_total
                profit = (price - cost) * qty

                item_data.append({
                    'product_id': pid,
                    'quantity': qty,
                    'unit_price': price,
                    'profit': profit
                })

            tax_amount = round(total_amount * 0.1, 2)  # Example: 10% tax

            cursor.execute("""
                INSERT INTO Sales (SaleDate, TotalAmount, TaxAmount, PaymentMethod, CustomerID)
                VALUES (%s, %s, %s, %s, %s)
            """, (sale_date, total_amount, tax_amount, payment_method, customer_id))
            sale_id = cursor.lastrowid

            for item in item_data:
                cursor.execute("""
                    INSERT INTO SaleItems (SaleID, ProductID, Quantity, UnitPrice)
                    VALUES (%s, %s, %s, %s)
                """, (sale_id, item['product_id'], item['quantity'], item['unit_price']))

                cursor.execute("""
                    INSERT INTO Profits (SaleID,ProfitAmount)
                    VALUES (%s, %s)
                """, (sale_id, item['profit']))

            conn.commit()
            flash('Sale and sale items added successfully!', 'success')
            return redirect(url_for('sales'))

        except Exception as e:
            conn.rollback()
            flash(f'Error adding sale: {str(e)}', 'danger')
            return redirect(url_for('add_sale'))

        finally:
            cursor.close()
            conn.close()

    else:
        cursor.execute("SELECT * FROM Products")
        products = cursor.fetchall()
        cursor.execute("SELECT * FROM Customers")
        customers = cursor.fetchall()
        cursor.execute("SELECT * FROM Employees")
        employees = cursor.fetchall()
        cursor.close()
        conn.close()

        return render_template('add_sale.html', products=products, customers=customers, employees=employees)
@app.route("/edit_sale/<int:id>", methods=["GET", "POST"])

def edit_sale(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        sale_date = request.form["sale_date"]
        total_amount = request.form["total_amount"]
        tax_amount = request.form["tax_amount"]
        payment_method = request.form["payment_method"]

        try:
            cursor.execute(
                """
                UPDATE Sales 
                SET SaleDate = %s, TotalAmount = %s, 
                    TaxAmount = %s, PaymentMethod = %s 
                WHERE SaleID = %s
                """,
                (sale_date, total_amount, tax_amount, payment_method, id)
            )
            conn.commit()
            flash("Sale updated successfully!", "success")
            return redirect(url_for("sales"))
        except Exception as e:
            conn.rollback()
            flash(f"Error updating sale: {e}", "danger")
            return redirect(url_for("edit_sale", id=id))
        finally:
            cursor.close()
            conn.close()

    else:
        cursor.execute("SELECT * FROM Sales WHERE SaleID = %s", (id,))
        sale = cursor.fetchone()

        cursor.execute("SELECT * FROM Customers")
        customers = cursor.fetchall()

        cursor.close()
        conn.close()

        if sale is None:
            flash("Sale not found.", "danger")
            return redirect(url_for("sales"))

        return render_template("edit_sale.html", sale=sale, customers=customers)



@app.route('/sales/delete/<int:id>', methods=['POST'])
def delete_sale(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM Sales WHERE SaleID = %s', (id,))
        conn.commit()
        flash('Sale deleted successfully!', 'success')
    except mysql.connector.IntegrityError:
        flash('Cannot delete this sale. It is referenced elsewhere.', 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('sales'))
@app.route('/employees')
def employees():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # All employees and extra info
    cursor.execute('''
        SELECT w.WorkerID, w.FirstName, w.LastName, w.PhoneNumber, w.HireDate, w.Salary,
               e.Department, e.Shift
        FROM Workers w
        LEFT JOIN Employees e ON w.WorkerID = e.EmployeeID
        ORDER BY w.WorkerID
    ''')
    employees = cursor.fetchall()

    # Highest paid employee
    cursor.execute('''
        SELECT w.WorkerID, w.FirstName, w.LastName, w.Salary
        FROM Workers w
        ORDER BY w.Salary DESC
        LIMIT 1
    ''')
    top_employee = cursor.fetchone()

    # Top performer (sales)
    cursor.execute('''
        SELECT 
            w.WorkerID,
            w.FirstName,
            w.LastName,
            SUM(si.Quantity * p.Price) AS TotalSales
        FROM Sales s
        JOIN SaleItems si ON s.SaleID = si.SaleID
        JOIN Products p ON si.ProductID = p.ProductID
        JOIN Workers w ON s.EmployeeID = w.WorkerID
        GROUP BY w.WorkerID, w.FirstName, w.LastName
        ORDER BY TotalSales DESC
        LIMIT 1;
    ''')
    top_sales_employee = cursor.fetchone()

    cursor.close()
    conn.close()

    # Prepare chart data
    names = [f"{emp['FirstName']} {emp['LastName']}" for emp in employees]
    salaries = [emp['Salary'] for emp in employees]

    return render_template(
        'employees.html',
        employees=employees,
        top_employee=top_employee,
        top_sales_employee=top_sales_employee,
        names=names,
        salaries=salaries
    )


# ----- ADD EMPLOYEE -----
@app.route('/employees/add', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        fname = request.form['first_name']
        lname = request.form['last_name']
        phone = request.form['phone']
        hire_date = request.form['hire_date']
        salary = request.form['salary']
        department = request.form['department']
        shift = request.form['shift']

        try:
            hire_date_obj = datetime.strptime(hire_date, '%Y-%m-%d').date()
            salary_val = float(salary)
        except ValueError:
            flash('Invalid date or salary format.', 'danger')
            return redirect(url_for('add_employee'))

        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert into Workers
        cursor.execute('''
            INSERT INTO Workers (FirstName, LastName, PhoneNumber, HireDate, Salary)
            VALUES (%s, %s, %s, %s, %s)
        ''', (fname, lname, phone, hire_date_obj, salary_val))
        worker_id = cursor.lastrowid

        # Insert into Employees
        cursor.execute('''
            INSERT INTO Employees (EmployeeID, Department, Shift)
            VALUES (%s, %s, %s)
        ''', (worker_id, department, shift))

        conn.commit()
        cursor.close()
        conn.close()

        flash('Employee added successfully!', 'success')
        return redirect(url_for('employees'))

    return render_template('add_employee.html')


# ----- EDIT EMPLOYEE -----
@app.route('/employees/edit/<int:id>', methods=['GET', 'POST'])
def edit_employee(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        fname = request.form['first_name']
        lname = request.form['last_name']
        phone = request.form['phone']
        hire_date = request.form['hire_date']
        salary = request.form['salary']
        department = request.form['department']
        shift = request.form['shift']

        try:
            hire_date_obj = datetime.strptime(hire_date, '%Y-%m-%d').date()
            salary_val = float(salary)
        except ValueError:
            flash('Invalid date or salary format.', 'danger')
            return redirect(url_for('edit_employee', id=id))

        # Update Workers and Employees tables
        cursor.execute('''
            UPDATE Workers
            SET FirstName=%s, LastName=%s, PhoneNumber=%s, HireDate=%s, Salary=%s
            WHERE WorkerID=%s
        ''', (fname, lname, phone, hire_date_obj, salary_val, id))

        cursor.execute('''
            UPDATE Employees
            SET Department=%s, Shift=%s
            WHERE EmployeeID=%s
        ''', (department, shift, id))

        conn.commit()
        cursor.close()
        conn.close()

        flash('Employee updated successfully!', 'success')
        return redirect(url_for('employees'))

    # GET: Fetch employee data to fill the form
    cursor.execute('''
        SELECT w.WorkerID, w.FirstName, w.LastName, w.PhoneNumber, w.HireDate, w.Salary,
               e.Department, e.Shift
        FROM Workers w
        LEFT JOIN Employees e ON w.WorkerID = e.EmployeeID
        WHERE w.WorkerID = %s
    ''', (id,))
    employee = cursor.fetchone()
    cursor.close()
    conn.close()

    if employee is None:
        flash('Employee not found.', 'warning')
        return redirect(url_for('employees'))

    return render_template('edit_employee.html', employee=employee)


# ----- DELETE EMPLOYEE -----
@app.route('/employees/delete/<int:id>', methods=['POST'])
def delete_employee(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Because of ON DELETE CASCADE in Employees table FK, deleting from Workers will remove Employees row automatically
    cursor.execute('DELETE FROM Workers WHERE WorkerID = %s', (id,))

    conn.commit()
    cursor.close()
    conn.close()

    flash('Employee deleted successfully.', 'info')
    return redirect(url_for('employees'))

@app.route('/logout',methods=['POST'])
def logout():

    flash('logout successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/profits')
def profits():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT SUM(TotalAmount) AS total_revenue FROM Sales")
    total_revenue = cursor.fetchone()['total_revenue'] or 0.0

    cursor.execute("SELECT SUM(PurchaseMoney) AS total_purchases FROM Suppliers")
    total_purchases = cursor.fetchone()['total_purchases'] or 0.0

    net_profit = total_revenue - total_purchases

    cursor.close()
    conn.close()

    return render_template('profits.html',
                           total_revenue=total_revenue,
                           total_purchases=total_purchases,
                           net_profit=net_profit)

if __name__ == '__main__':
    app.run(debug=True)
