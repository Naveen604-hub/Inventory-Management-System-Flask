
# Inventory Management System

A modern Flask web application for managing products, locations, and stock movements with real-time balance tracking.

## 🚀 Features

- **Product Management**: Add, edit, and track products with descriptions
- **Location Management**: Manage warehouses and shop locations
- **Stock Movements**: Record inbound, outbound, and transfer movements
- **Real-time Balances**: Live inventory tracking across all locations
- **Modern UI**: Responsive design with animations and Bootstrap styling
- **Data Validation**: Prevents negative stock and validates all operations

## 📋 Database Schema

- **Product**: `product_id` (PK), `name`, `description`
- **Location**: `location_id` (PK), `name`, `address`
- **ProductMovement**: `movement_id` (PK), `timestamp`, `from_location`, `to_location`, `product_id`, `qty`

## 🛠️ Tech Stack

- **Backend**: Flask, SQLAlchemy
- **Frontend**: Bootstrap 5, Bootstrap Icons
- **Database**: SQLite (configurable to MySQL/PostgreSQL)
- **Styling**: Custom CSS with animations

## 📦 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Naveen604-hub/Inventory-Management-System-Flask.git
   cd Inventory-Management-System-Flask
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   ```

3. **Activate virtual environment**
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**
   ```bash
   pip install flask flask-sqlalchemy pymysql
   ```

## 🚀 Quick Start

1. **Run the application**
   ```bash
   python app.py
   ```

2. **Open your browser**
   Navigate to `http://127.0.0.1:5000`

3. **Load sample data**
   Click the "Seed" button in the navigation to populate sample products, locations, and movements

## 📱 Usage

### Products
- View all products with current quantities
- Add new products with ID, name, and description
- Edit products and optionally add stock to locations
- Delete products (only if no movements exist)

### Locations
- Manage warehouse and shop locations
- Add locations with ID, name, and address
- Edit or delete locations (only if not referenced by movements)

### Movements
- Record stock movements between locations
- Support inbound (to location), outbound (from location), and transfers
- Automatic validation prevents negative stock
- View movement history with timestamps

### Balance Report
- Real-time inventory balances by product and location
- Shows only non-zero quantities
- Updated automatically with each movement

## 🎨 UI Features

- **Animated Homepage**: Smooth fade-in effects and hover animations
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Color-coded Icons**: Custom SVG logos for each section
- **Interactive Elements**: Collapsible details and smooth transitions
- **Modern Styling**: Gradient backgrounds and professional color scheme

## ⚙️ Configuration

### Database
- **Default**: SQLite (`inventory.db`)
- **MySQL**: Set `DATABASE_URL=mysql+pymysql://user:pass@host:port/db`
- **PostgreSQL**: Set `DATABASE_URL=postgresql+psycopg2://user:pass@host:port/db`

### Environment Variables
- `DATABASE_URL`: Database connection string
- `SECRET_KEY`: Flask session secret key

## 🔧 Development

### Project Structure
```
├── app.py                 # Main Flask application
├── templates/            # Jinja2 templates
│   ├── base.html         # Base template with navigation
│   ├── home.html         # Dashboard homepage
│   ├── products/         # Product CRUD templates
│   ├── locations/        # Location CRUD templates
│   ├── movements/        # Movement CRUD templates
│   └── report.html       # Balance report
├── static/img/           # SVG logos and assets
└── README.md            # This file
```

### Key Functions
- `compute_balances()`: Calculate current stock levels
- `get_available_qty()`: Get available quantity for a product at a location
- `validate_movement_form()`: Validate movement data and stock availability
