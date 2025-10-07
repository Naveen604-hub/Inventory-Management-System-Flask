from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import func
import os
from datetime import datetime


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///inventory.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
db = SQLAlchemy(app)


class Product(db.Model):
    __tablename__ = "product"
    product_id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Product {self.product_id} - {self.name}>"


class Location(db.Model):
    __tablename__ = "location"
    location_id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Location {self.location_id} - {self.name}>"


class ProductMovement(db.Model):
    __tablename__ = "product_movement"
    movement_id = db.Column(db.String(64), primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    from_location = db.Column(db.String(64), db.ForeignKey("location.location_id"), nullable=True)
    to_location = db.Column(db.String(64), db.ForeignKey("location.location_id"), nullable=True)
    product_id = db.Column(db.String(64), db.ForeignKey("product.product_id"), nullable=False)
    qty = db.Column(db.Integer, nullable=False)

    product = relationship("Product")
    from_loc = relationship("Location", foreign_keys=[from_location])
    to_loc = relationship("Location", foreign_keys=[to_location])

    def __repr__(self) -> str:
        return f"<Movement {self.movement_id} {self.product_id} {self.qty}>"


def compute_balances():
    """Return dict keyed by (product_id, location_id) -> qty balance."""
    balances = {}
    movements = ProductMovement.query.order_by(ProductMovement.timestamp.asc()).all()
    for mv in movements:
        if mv.to_location:
            key = (mv.product_id, mv.to_location)
            balances[key] = balances.get(key, 0) + mv.qty
        if mv.from_location:
            key = (mv.product_id, mv.from_location)
            balances[key] = balances.get(key, 0) - mv.qty
    return balances


def get_available_qty(product_id: str, location_id: str) -> int:
    balances = compute_balances()
    return balances.get((product_id, location_id), 0)


@app.route("/")
def index():
    # Stats
    product_count = Product.query.count()
    location_count = Location.query.count()
    movement_count = ProductMovement.query.count()

    # Recent movements
    recent_movements = ProductMovement.query.order_by(ProductMovement.timestamp.desc()).limit(10).all()
    products = {p.product_id: p for p in Product.query.all()}
    locations = {l.location_id: l for l in Location.query.all()}

    # Balances preview (top 10 non-zero by absolute qty desc)
    balances = compute_balances()
    balance_rows = []
    for (product_id, location_id), qty in balances.items():
        if qty == 0:
            continue
        balance_rows.append({
            "product_id": product_id,
            "product_name": products.get(product_id).name if product_id in products else product_id,
            "location_id": location_id,
            "location_name": locations.get(location_id).name if location_id in locations else location_id,
            "qty": qty,
        })
    balance_rows.sort(key=lambda r: abs(r["qty"]), reverse=True)
    balance_rows = balance_rows[:10]

    return render_template(
        "home.html",
        product_count=product_count,
        location_count=location_count,
        movement_count=movement_count,
        recent_movements=recent_movements,
        products=products,
        locations=locations,
        balance_rows=balance_rows,
    )


# Product CRUD
@app.route("/products")
def products_list():
    products = Product.query.order_by(Product.product_id.asc()).all()
    # Aggregate balances for quick glance on product page
    balances = compute_balances()
    locations = {l.location_id: l for l in Location.query.all()}
    product_totals = {}
    product_breakdown = {}
    for (product_id, location_id), qty in balances.items():
        if qty == 0:
            continue
        product_totals[product_id] = product_totals.get(product_id, 0) + qty
        lst = product_breakdown.setdefault(product_id, [])
        location_name = locations.get(location_id).name if location_id in locations else location_id
        lst.append({"location_id": location_id, "location_name": location_name, "qty": qty})
    # Sort breakdown entries by location name
    for pid in product_breakdown:
        product_breakdown[pid].sort(key=lambda r: r["location_name"])
    return render_template("products/list.html", products=products, product_totals=product_totals, product_breakdown=product_breakdown)


@app.route("/products/new", methods=["GET", "POST"])
def products_new():
    if request.method == "POST":
        product_id = request.form.get("product_id", "").strip()
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None
        if not product_id or not name:
            flash("Product ID and Name are required.", "danger")
        elif Product.query.get(product_id):
            flash("Product ID already exists.", "danger")
        else:
            db.session.add(Product(product_id=product_id, name=name, description=description))
            db.session.commit()
            flash("Successfully created.", "success")
            return redirect(url_for("products_list"))
    return render_template("products/new.html")


@app.route("/products/<product_id>/edit", methods=["GET", "POST"])
def products_edit(product_id):
    product = Product.query.get_or_404(product_id)
    all_locations = Location.query.order_by(Location.location_id.asc()).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None
        add_qty_raw = request.form.get("add_qty", "").strip()
        add_to_location = request.form.get("add_to_location", "").strip() or None

        if not name:
            flash("Name is required.", "danger")
        else:
            product.name = name
            product.description = description

            # If user specified a quantity to add, create an inbound movement into selected location
            if add_qty_raw:
                try:
                    add_qty = int(add_qty_raw)
                except ValueError:
                    add_qty = None
                if add_qty is None or add_qty <= 0:
                    flash("Quantity to add must be a positive integer.", "danger")
                    return render_template("products/edit.html", product=product, locations=all_locations)
                if not add_to_location or not Location.query.get(add_to_location):
                    flash("Please choose a valid location to receive the quantity.", "danger")
                    return render_template("products/edit.html", product=product, locations=all_locations)
                # Auto-generate a unique movement id
                mid = f"AUTO-{int(datetime.utcnow().timestamp()*1000)}"
                db.session.add(ProductMovement(
                    movement_id=mid,
                    product_id=product.product_id,
                    from_location=None,
                    to_location=add_to_location,
                    qty=add_qty,
                ))

            db.session.commit()
            flash("Successfully updated.", "success")
            return redirect(url_for("products_list"))
    return render_template("products/edit.html", product=product, locations=all_locations)


@app.route("/products/<product_id>/delete", methods=["POST"])
def products_delete(product_id):
    product = Product.query.get_or_404(product_id)
    # Prevent delete if movements exist for this product
    if ProductMovement.query.filter_by(product_id=product_id).first():
        flash("Cannot delete product with existing movements.", "danger")
        return redirect(url_for("products_list"))
    db.session.delete(product)
    db.session.commit()
    flash("Successfully deleted.", "success")
    return redirect(url_for("products_list"))


# Location CRUD
@app.route("/locations")
def locations_list():
    locations = Location.query.order_by(Location.location_id.asc()).all()
    return render_template("locations/list.html", locations=locations)


@app.route("/locations/new", methods=["GET", "POST"])
def locations_new():
    if request.method == "POST":
        location_id = request.form.get("location_id", "").strip()
        name = request.form.get("name", "").strip()
        address = request.form.get("address", "").strip() or None
        if not location_id or not name:
            flash("Location ID and Name are required.", "danger")
        elif Location.query.get(location_id):
            flash("Location ID already exists.", "danger")
        else:
            db.session.add(Location(location_id=location_id, name=name, address=address))
            db.session.commit()
            flash("Successfully created.", "success")
            return redirect(url_for("locations_list"))
    return render_template("locations/new.html")


@app.route("/locations/<location_id>/edit", methods=["GET", "POST"])
def locations_edit(location_id):
    location = Location.query.get_or_404(location_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        address = request.form.get("address", "").strip() or None
        if not name:
            flash("Name is required.", "danger")
        else:
            location.name = name
            location.address = address
            db.session.commit()
            flash("Successfully updated.", "success")
            return redirect(url_for("locations_list"))
    return render_template("locations/edit.html", location=location)


@app.route("/locations/<location_id>/delete", methods=["POST"])
def locations_delete(location_id):
    location = Location.query.get_or_404(location_id)
    # Prevent delete if movements reference this location
    if ProductMovement.query.filter((ProductMovement.from_location == location_id) | (ProductMovement.to_location == location_id)).first():
        flash("Cannot delete location referenced by movements.", "danger")
        return redirect(url_for("locations_list"))
    db.session.delete(location)
    db.session.commit()
    flash("Successfully deleted.", "success")
    return redirect(url_for("locations_list"))


# ProductMovement CRUD
def validate_movement_form(form, existing_id: str | None = None):
    movement_id = form.get("movement_id", "").strip()
    product_id = form.get("product_id", "").strip()
    from_location = form.get("from_location", "").strip() or None
    to_location = form.get("to_location", "").strip() or None
    qty_raw = form.get("qty", "").strip()

    # Basic checks
    if not movement_id:
        return None, "Movement ID is required."
    if existing_id is None and ProductMovement.query.get(movement_id):
        return None, "Movement ID already exists."
    if not product_id or not Product.query.get(product_id):
        return None, "Valid Product is required."
    if not from_location and not to_location:
        return None, "Either From or To location must be provided."
    if from_location and not Location.query.get(from_location):
        return None, "From Location does not exist."
    if to_location and not Location.query.get(to_location):
        return None, "To Location does not exist."
    if from_location and to_location and from_location == to_location:
        return None, "From and To locations cannot be the same."
    try:
        qty = int(qty_raw)
    except ValueError:
        return None, "Qty must be an integer."
    if qty <= 0:
        return None, "Qty must be positive."

    # Stock check for outbound or transfer
    if from_location:
        available = get_available_qty(product_id, from_location)
        # If editing, adjust availability by adding back original qty if from_location unchanged
        if existing_id is not None:
            original = ProductMovement.query.get(existing_id)
            if original and original.from_location == from_location and original.product_id == product_id:
                available += original.qty
        if qty > available:
            return None, f"Insufficient stock at From Location. Available: {available}."

    data = {
        "movement_id": movement_id,
        "product_id": product_id,
        "from_location": from_location,
        "to_location": to_location,
        "qty": qty,
    }
    return data, None


@app.route("/movements")
def movements_list():
    movements = ProductMovement.query.order_by(ProductMovement.timestamp.desc()).all()
    products = {p.product_id: p for p in Product.query.all()}
    locations = {l.location_id: l for l in Location.query.all()}
    return render_template("movements/list.html", movements=movements, products=products, locations=locations)


@app.route("/movements/new", methods=["GET", "POST"])
def movements_new():
    products = Product.query.order_by(Product.product_id.asc()).all()
    locations = Location.query.order_by(Location.location_id.asc()).all()
    if request.method == "POST":
        data, error = validate_movement_form(request.form)
        if error:
            flash(error, "danger")
        else:
            movement = ProductMovement(**data)
            db.session.add(movement)
            db.session.commit()
            flash("Successfully created.", "success")
            return redirect(url_for("movements_list"))
    return render_template("movements/new.html", products=products, locations=locations)


@app.route("/movements/<movement_id>/edit", methods=["GET", "POST"])
def movements_edit(movement_id):
    movement = ProductMovement.query.get_or_404(movement_id)
    products = Product.query.order_by(Product.product_id.asc()).all()
    locations = Location.query.order_by(Location.location_id.asc()).all()
    if request.method == "POST":
        data, error = validate_movement_form(request.form, existing_id=movement_id)
        if error:
            flash(error, "danger")
        else:
            movement.product_id = data["product_id"]
            movement.from_location = data["from_location"]
            movement.to_location = data["to_location"]
            movement.qty = data["qty"]
            # Keep the original timestamp unless user explicitly provided one (not in form now)
            db.session.commit()
            flash("Successfully updated.", "success")
            return redirect(url_for("movements_list"))
    return render_template("movements/edit.html", movement=movement, products=products, locations=locations)


@app.route("/movements/<movement_id>/delete", methods=["POST"])
def movements_delete(movement_id):
    movement = ProductMovement.query.get_or_404(movement_id)
    # Ensure deletion won't violate stock (i.e., after deletion, balances remain non-negative)
    # This check is conservative: simulate removal and verify from_location would have enough stock
    if movement.from_location:
        available = get_available_qty(movement.product_id, movement.from_location)
        if available < movement.qty:
            flash("Cannot delete movement; it would make stock negative at From Location.", "danger")
            return redirect(url_for("movements_list"))
    db.session.delete(movement)
    db.session.commit()
    flash("Successfully deleted.", "success")
    return redirect(url_for("movements_list"))


@app.route("/report")
def report():
    balances = compute_balances()
    # Build rows with names
    products = {p.product_id: p for p in Product.query.all()}
    locations = {l.location_id: l for l in Location.query.all()}
    rows = []
    for (product_id, location_id), qty in sorted(balances.items()):
        if qty == 0:
            continue
        product_name = products.get(product_id).name if product_id in products else product_id
        location_name = locations.get(location_id).name if location_id in locations else location_id
        rows.append({
            "product_id": product_id,
            "product_name": product_name,
            "location_id": location_id,
            "location_name": location_name,
            "qty": qty,
        })
    return render_template("report.html", rows=rows)


@app.route("/seed")
def seed():
    # Create tables
    db.create_all()

    # Seed products
    sample_products = [
        ("A", "Product A"),
        ("B", "Product B"),
        ("C", "Product C"),
        ("D", "Product D"),
    ]
    for pid, name in sample_products:
        if not Product.query.get(pid):
            db.session.add(Product(product_id=pid, name=name))

    # Seed locations
    sample_locations = [
        ("X", "Warehouse X"),
        ("Y", "Warehouse Y"),
        ("Z", "Warehouse Z"),
        ("W", "Warehouse W"),
    ]
    for lid, name in sample_locations:
        if not Location.query.get(lid):
            db.session.add(Location(location_id=lid, name=name))

    db.session.commit()

    # Seed movements (idempotent by checking IDs)
    def add_mv(mid, pid, fr, to, qty):
        if not ProductMovement.query.get(mid):
            db.session.add(ProductMovement(
                movement_id=mid,
                product_id=pid,
                from_location=fr,
                to_location=to,
                qty=qty,
            ))

    # Initial stock in
    add_mv("M1", "A", None, "X", 50)
    add_mv("M2", "B", None, "X", 30)
    add_mv("M3", "A", "X", "Y", 10)
    add_mv("M4", "B", None, "Y", 20)
    add_mv("M5", "C", None, "Z", 40)
    add_mv("M6", "A", "Y", "Z", 5)
    add_mv("M7", "A", None, "X", 15)
    add_mv("M8", "B", "X", None, 5)  # outbound sale
    add_mv("M9", "C", "Z", "X", 12)
    add_mv("M10", "D", None, "W", 25)
    add_mv("M11", "D", "W", "X", 5)
    add_mv("M12", "A", "X", None, 8)
    add_mv("M13", "B", "Y", "Z", 7)
    add_mv("M14", "C", None, "Y", 9)
    add_mv("M15", "A", "Z", None, 3)
    add_mv("M16", "B", None, "Z", 11)
    add_mv("M17", "A", "X", "Y", 6)
    add_mv("M18", "D", "X", None, 2)
    add_mv("M19", "C", "Y", "X", 4)
    add_mv("M20", "B", "Z", None, 3)

    db.session.commit()
    flash("Database seeded with sample data.", "success")
    return redirect(url_for("report"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)


