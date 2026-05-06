from flask import Flask, render_template, request, redirect, session, send_file
import mysql.connector
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = "secret123"

# ================= DATABASE =================
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="031206",
    database="foodflow"
)

cursor = db.cursor(dictionary=True, buffered=True)

# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form["phone"]

        cursor.execute("SELECT * FROM users WHERE phone=%s", (phone,))
        user = cursor.fetchone()

        if user:
            session["user"] = user["username"]
            return redirect("/dashboard")
        else:
            return "❌ Phone not registered"

    return render_template("login.html")

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    cursor.execute("SELECT * FROM restaurants")
    restaurants = cursor.fetchall()
    return render_template("dashboard.html", restaurants=restaurants)

# ================= MENU =================
@app.route("/menu/<path:res>")
def menu(res):
    search = request.args.get("search")

    if search:
        cursor.execute("""
            SELECT menu.* FROM menu
            JOIN restaurants ON menu.restaurant_id = restaurants.id
            WHERE restaurants.name=%s AND menu.name LIKE %s
        """, (res, f"%{search}%"))
    else:
        cursor.execute("""
            SELECT menu.* FROM menu
            JOIN restaurants ON menu.restaurant_id = restaurants.id
            WHERE restaurants.name=%s
        """, (res,))

    items = cursor.fetchall()
    return render_template("menu.html", items=items, res=res)

# ================= ADD TO CART =================
@app.route("/add/<int:id>")
def add(id):
    if "cart" not in session:
        session["cart"] = []

    cursor.execute("SELECT * FROM menu WHERE id=%s", (id,))
    item = cursor.fetchone()

    for c in session["cart"]:
        if c["id"] == id:
            c["qty"] += 1
            session.modified = True
            return redirect("/cart")

    item["qty"] = 1
    session["cart"].append(item)
    session.modified = True

    return redirect("/cart")

# ================= CART =================
@app.route("/cart")
def cart():
    cart = session.get("cart", [])
    total = sum(i["price"] * i["qty"] for i in cart)
    return render_template("cart.html", cart=cart, total=total)

# ================= PAYMENT =================
@app.route("/payment")
def payment():
    cart = session.get("cart", [])
    total = sum(i["price"] * i["qty"] for i in cart)
    return render_template("payment.html", total=total)

# ================= PLACE ORDER =================
@app.route("/place_order", methods=["POST"])
def place_order():
    if "user" not in session:
        return redirect("/")

    cart = session.get("cart", [])
    if not cart:
        return "Cart is empty!"

    total = sum(i["price"] * i["qty"] for i in cart)

    cursor.execute(
        "INSERT INTO orders (username, total, status) VALUES (%s,%s,%s)",
        (session["user"], total, "Preparing")
    )
    db.commit()

    order_id = cursor.lastrowid

    for item in cart:
        cursor.execute(
            "INSERT INTO order_items (order_id, item_name, price, quantity) VALUES (%s,%s,%s,%s)",
            (order_id, item["name"], item["price"], item["qty"])
        )
    db.commit()

    session["cart"] = []

    return redirect(f"/success/{order_id}")

# ================= SUCCESS =================
@app.route("/success/<int:order_id>")
def success(order_id):
    return render_template("success.html", order_id=order_id)

# ================= DELIVERY =================
@app.route("/delivery/<int:order_id>")
def delivery(order_id):
    return render_template("delivery.html", order_id=order_id)

# ================= BILL (PDF) =================
@app.route("/bill/<int:order_id>")
def bill(order_id):
    cursor.execute("SELECT * FROM order_items WHERE order_id=%s", (order_id,))
    items = cursor.fetchall()

    file = f"bill_{order_id}.pdf"
    doc = SimpleDocTemplate(file)
    styles = getSampleStyleSheet()

    content = []
    total = 0

    content.append(Paragraph(f"Order ID: {order_id}", styles['Title']))

    for i in items:
        line = f"{i['item_name']} x {i['quantity']} = Rs.{i['price'] * i['quantity']}"
        total += i['price'] * i['quantity']
        content.append(Paragraph(line, styles['Normal']))

    content.append(Paragraph(f"Total: Rs.{total}", styles['Heading2']))

    doc.build(content)

    return send_file(file, as_attachment=True)

# ================= HISTORY =================
@app.route("/history")
def history():
    if "user" not in session:
        return redirect("/")

    cursor.execute("SELECT * FROM orders WHERE username=%s", (session["user"],))
    data = cursor.fetchall()
    return render_template("history.html", data=data)

# ================= ADMIN =================
@app.route("/admin")
def admin():
    cursor.execute("SELECT * FROM orders")
    orders = cursor.fetchall()

    cursor.execute("SELECT SUM(total) AS profit FROM orders")
    profit = cursor.fetchone()

    return render_template("admin.html", orders=orders, profit=profit)

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)