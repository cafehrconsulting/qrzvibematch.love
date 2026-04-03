import os
import sqlite3
from datetime import datetime, date
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
    abort,
    jsonify,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


# ============================================================
# CORE PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DATABASE_PATH = INSTANCE_DIR / "qrz_vibe.db"
UPLOAD_DIR = BASE_DIR / "static" / "uploads" / "photos"

INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# APP CONFIG
# ============================================================

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key-in-production")
app.config["DATABASE"] = str(DATABASE_PATH)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "webp", "gif"}

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_db(query, params=(), one=False):
    cur = get_db().execute(query, params)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute_db(query, params=()):
    db = get_db()
    cur = db.execute(query, params)
    db.commit()
    lastrowid = cur.lastrowid
    cur.close()
    return lastrowid


def executescript_db(script: str):
    db = get_db()
    db.executescript(script)
    db.commit()


def table_exists(table_name: str) -> bool:
    row = query_db(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
        one=True,
    )
    return row is not None


def get_table_columns(table_name: str) -> set[str]:
    if not table_exists(table_name):
        return set()
    rows = query_db(f"PRAGMA table_info({table_name})")
    return {row["name"] for row in rows}


def safe_add_column(table_name: str, column_sql: str, column_name: str):
    existing = get_table_columns(table_name)
    if column_name not in existing:
        execute_db(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def rebuild_table_gift_transactions():
    db = get_db()

    old_rows = []
    if table_exists("gift_transactions"):
        old_columns = get_table_columns("gift_transactions")
        selectable = []
        if "sender_user_id" in old_columns:
            selectable.append("sender_user_id")
        elif "user_id" in old_columns:
            selectable.append("user_id AS sender_user_id")
        else:
            selectable.append("NULL AS sender_user_id")

        if "receiver_user_id" in old_columns:
            selectable.append("receiver_user_id")
        else:
            selectable.append("NULL AS receiver_user_id")

        if "gift_id" in old_columns:
            selectable.append("gift_id")
        else:
            selectable.append("NULL AS gift_id")

        if "quantity" in old_columns:
            selectable.append("quantity")
        else:
            selectable.append("1 AS quantity")

        if "total_coin_cost" in old_columns:
            selectable.append("total_coin_cost")
        else:
            selectable.append("0 AS total_coin_cost")

        if "total_cash_value" in old_columns:
            selectable.append("total_cash_value")
        else:
            selectable.append("0.0 AS total_cash_value")

        if "receiver_cash_credit" in old_columns:
            selectable.append("receiver_cash_credit")
        else:
            selectable.append("0.0 AS receiver_cash_credit")

        if "receiver_benefit_points" in old_columns:
            selectable.append("receiver_benefit_points")
        else:
            selectable.append("0 AS receiver_benefit_points")

        if "message" in old_columns:
            selectable.append("message")
        else:
            selectable.append("NULL AS message")

        if "created_at" in old_columns:
            selectable.append("created_at")
        else:
            selectable.append("CURRENT_TIMESTAMP AS created_at")

        try:
            old_rows = query_db(
                f"""
                SELECT {', '.join(selectable)}
                FROM gift_transactions
                """
            )
        except Exception:
            old_rows = []

    db.execute("DROP TABLE IF EXISTS gift_transactions")
    db.commit()

    db.execute(
        """
        CREATE TABLE gift_transactions (
            tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_user_id INTEGER NOT NULL,
            receiver_user_id INTEGER NOT NULL,
            gift_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            total_coin_cost INTEGER NOT NULL DEFAULT 0,
            total_cash_value REAL NOT NULL DEFAULT 0.0,
            receiver_cash_credit REAL NOT NULL DEFAULT 0.0,
            receiver_benefit_points INTEGER NOT NULL DEFAULT 0,
            message TEXT DEFAULT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (receiver_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (gift_id) REFERENCES gifts(gift_id) ON DELETE CASCADE
        )
        """
    )
    db.commit()

    for row in old_rows:
        sender = row["sender_user_id"] if row["sender_user_id"] is not None else 1
        receiver = row["receiver_user_id"] if row["receiver_user_id"] is not None else sender
        gift_id = row["gift_id"] if row["gift_id"] is not None else 1

        try:
            db.execute(
                """
                INSERT INTO gift_transactions (
                    sender_user_id,
                    receiver_user_id,
                    gift_id,
                    quantity,
                    total_coin_cost,
                    total_cash_value,
                    receiver_cash_credit,
                    receiver_benefit_points,
                    message,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sender,
                    receiver,
                    gift_id,
                    row["quantity"],
                    row["total_coin_cost"],
                    row["total_cash_value"],
                    row["receiver_cash_credit"],
                    row["receiver_benefit_points"],
                    row["message"],
                    row["created_at"],
                ),
            )
        except Exception:
            continue

    db.commit()


def rebuild_table_chat_messages():
    db = get_db()

    old_rows = []
    if table_exists("chat_messages"):
        old_columns = get_table_columns("chat_messages")
        selectable = []

        if "thread_id" in old_columns:
            selectable.append("thread_id")
        else:
            selectable.append("1 AS thread_id")

        if "sender_user_id" in old_columns:
            selectable.append("sender_user_id")
        elif "user_id" in old_columns:
            selectable.append("user_id AS sender_user_id")
        else:
            selectable.append("1 AS sender_user_id")

        if "body" in old_columns:
            selectable.append("body")
        elif "message" in old_columns:
            selectable.append("message AS body")
        else:
            selectable.append("'' AS body")

        if "message_type" in old_columns:
            selectable.append("message_type")
        else:
            selectable.append("'text' AS message_type")

        if "created_at" in old_columns:
            selectable.append("created_at")
        else:
            selectable.append("CURRENT_TIMESTAMP AS created_at")

        try:
            old_rows = query_db(
                f"""
                SELECT {', '.join(selectable)}
                FROM chat_messages
                """
            )
        except Exception:
            old_rows = []

    db.execute("DROP TABLE IF EXISTS chat_messages")
    db.commit()

    db.execute(
        """
        CREATE TABLE chat_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id INTEGER NOT NULL,
            sender_user_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            message_type TEXT DEFAULT 'text',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (thread_id) REFERENCES chat_threads(thread_id) ON DELETE CASCADE,
            FOREIGN KEY (sender_user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """
    )
    db.commit()

    for row in old_rows:
        try:
            db.execute(
                """
                INSERT INTO chat_messages (
                    thread_id,
                    sender_user_id,
                    body,
                    message_type,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["thread_id"],
                    row["sender_user_id"],
                    row["body"],
                    row["message_type"],
                    row["created_at"],
                ),
            )
        except Exception:
            continue

    db.commit()


# ============================================================
# AUTH USER MODEL
# ============================================================

class User(UserMixin):
    def __init__(self, row):
        self.row = row
        self.id = str(row["user_id"])

    @property
    def user_id(self):
        return self.row["user_id"]

    @property
    def username(self):
        return self.row["username"]

    @property
    def email(self):
        return self.row["email"]

    @property
    def subscription_plan(self):
        active = query_db(
            """
            SELECT plan_name
            FROM subscriptions
            WHERE user_id = ?
              AND status = 'active'
            ORDER BY sub_id DESC
            LIMIT 1
            """,
            (self.user_id,),
            one=True,
        )
        return active["plan_name"] if active else "free"

    @property
    def is_premium(self):
        return self.subscription_plan in {"premium", "vip"}

    @property
    def is_vip(self):
        return self.subscription_plan == "vip"


@login_manager.user_loader
def load_user(user_id):
    row = query_db("SELECT * FROM users WHERE user_id = ?", (user_id,), one=True)
    return User(row) if row else None


# ============================================================
# DECORATORS
# ============================================================

def subscription_required(*plans):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()

            current_plan = current_user.subscription_plan
            if current_plan not in plans:
                flash("This feature requires a higher membership plan.", "warning")
                return redirect(url_for("subscriptions"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================
# DB BOOTSTRAP / SCHEMA SYNC
# ============================================================

def init_db():
    base_schema = """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        gender TEXT DEFAULT NULL,
        birth_date TEXT NOT NULL,
        bio TEXT DEFAULT NULL,
        location_lat REAL DEFAULT NULL,
        location_lon REAL DEFAULT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_photos (
        photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        photo_url TEXT NOT NULL,
        is_profile_picture INTEGER DEFAULT 0,
        display_order INTEGER DEFAULT 0,
        visibility TEXT DEFAULT 'public',
        uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS subscriptions (
        sub_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        plan_name TEXT DEFAULT 'free',
        status TEXT DEFAULT 'active',
        start_date TEXT,
        end_date TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS affiliate_stats (
        click_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        partner TEXT NOT NULL,
        target_url TEXT NOT NULL,
        click_time TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS gifts (
        gift_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        icon TEXT DEFAULT '🎁',
        coin_cost INTEGER NOT NULL DEFAULT 25,
        cash_price REAL NOT NULL DEFAULT 0.99,
        is_active INTEGER DEFAULT 1,
        category TEXT DEFAULT 'standard',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_wallets (
        wallet_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        coin_balance INTEGER NOT NULL DEFAULT 0,
        benefit_points INTEGER NOT NULL DEFAULT 0,
        cashable_balance REAL NOT NULL DEFAULT 0.0,
        lifetime_received_value REAL NOT NULL DEFAULT 0.0,
        gifts_received_count INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS chat_threads (
        thread_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_one_id INTEGER NOT NULL,
        user_two_id INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_one_id, user_two_id),
        FOREIGN KEY (user_one_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (user_two_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """
    executescript_db(base_schema)

    safe_add_column("users", "gender TEXT DEFAULT NULL", "gender")
    safe_add_column("users", "bio TEXT DEFAULT NULL", "bio")
    safe_add_column("users", "location_lat REAL DEFAULT NULL", "location_lat")
    safe_add_column("users", "location_lon REAL DEFAULT NULL", "location_lon")

    safe_add_column("user_photos", "display_order INTEGER DEFAULT 0", "display_order")
    safe_add_column("user_photos", "visibility TEXT DEFAULT 'public'", "visibility")
    safe_add_column("user_photos", "updated_at TEXT DEFAULT CURRENT_TIMESTAMP", "updated_at")

    safe_add_column("subscriptions", "created_at TEXT DEFAULT CURRENT_TIMESTAMP", "created_at")

    safe_add_column("affiliate_stats", "target_url TEXT DEFAULT ''", "target_url")
    safe_add_column("affiliate_stats", "click_time TEXT DEFAULT CURRENT_TIMESTAMP", "click_time")

    safe_add_column("gifts", "coin_cost INTEGER NOT NULL DEFAULT 25", "coin_cost")
    safe_add_column("gifts", "cash_price REAL NOT NULL DEFAULT 0.99", "cash_price")
    safe_add_column("gifts", "is_active INTEGER DEFAULT 1", "is_active")
    safe_add_column("gifts", "category TEXT DEFAULT 'standard'", "category")
    safe_add_column("gifts", "created_at TEXT DEFAULT CURRENT_TIMESTAMP", "created_at")

    safe_add_column("user_wallets", "coin_balance INTEGER NOT NULL DEFAULT 0", "coin_balance")
    safe_add_column("user_wallets", "benefit_points INTEGER NOT NULL DEFAULT 0", "benefit_points")
    safe_add_column("user_wallets", "cashable_balance REAL NOT NULL DEFAULT 0.0", "cashable_balance")
    safe_add_column("user_wallets", "lifetime_received_value REAL NOT NULL DEFAULT 0.0", "lifetime_received_value")
    safe_add_column("user_wallets", "gifts_received_count INTEGER NOT NULL DEFAULT 0", "gifts_received_count")
    safe_add_column("user_wallets", "updated_at TEXT DEFAULT CURRENT_TIMESTAMP", "updated_at")

    gift_tx_columns = get_table_columns("gift_transactions")
    required_gift_tx = {
        "sender_user_id",
        "receiver_user_id",
        "gift_id",
        "quantity",
        "total_coin_cost",
        "total_cash_value",
        "receiver_cash_credit",
        "receiver_benefit_points",
        "message",
        "created_at",
    }
    if not gift_tx_columns or not required_gift_tx.issubset(gift_tx_columns):
        rebuild_table_gift_transactions()

    chat_message_columns = get_table_columns("chat_messages")
    required_chat_messages = {
        "thread_id",
        "sender_user_id",
        "body",
        "message_type",
        "created_at",
    }
    if not chat_message_columns or not required_chat_messages.issubset(chat_message_columns):
        rebuild_table_chat_messages()

    index_script = """
    CREATE INDEX IF NOT EXISTS idx_user_photos_user_id ON user_photos(user_id);
    CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
    CREATE INDEX IF NOT EXISTS idx_affiliate_stats_partner ON affiliate_stats(partner);
    CREATE INDEX IF NOT EXISTS idx_gift_transactions_sender ON gift_transactions(sender_user_id);
    CREATE INDEX IF NOT EXISTS idx_gift_transactions_receiver ON gift_transactions(receiver_user_id);
    CREATE INDEX IF NOT EXISTS idx_chat_threads_users ON chat_threads(user_one_id, user_two_id);
    CREATE INDEX IF NOT EXISTS idx_chat_messages_thread ON chat_messages(thread_id);
    """
    executescript_db(index_script)

    seed_default_gifts()


def seed_default_gifts():
    existing = query_db("SELECT COUNT(*) AS total FROM gifts", one=True)
    if existing and existing["total"] > 0:
        return

    starter_gifts = [
        ("Wink Spark", "wink-spark", "😉", 25, 0.49, "starter"),
        ("Heart Pulse", "heart-pulse", "❤️", 50, 0.99, "starter"),
        ("Rose Drop", "rose-drop", "🌹", 75, 1.49, "starter"),
        ("Sweet Note", "sweet-note", "💌", 100, 1.99, "starter"),
        ("Blush Box", "blush-box", "💕", 150, 2.99, "mid"),
        ("Golden Rose", "golden-rose", "🌹", 200, 3.99, "mid"),
        ("Vibe Flame", "vibe-flame", "🔥", 250, 4.99, "mid"),
        ("Moon Kiss", "moon-kiss", "🌙", 300, 5.99, "mid"),
        ("Diamond Heart", "diamond-heart", "💎", 400, 7.99, "premium"),
        ("Crown Crush", "crown-crush", "👑", 500, 9.99, "premium"),
    ]

    for gift in starter_gifts:
        execute_db(
            """
            INSERT INTO gifts (name, slug, icon, coin_cost, cash_price, category)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            gift,
        )


# ============================================================
# UTILITY HELPERS
# ============================================================

def allowed_file(filename):
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in app.config["ALLOWED_EXTENSIONS"]


def calculate_age(birth_date_str):
    try:
        born = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
        today = date.today()
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    except Exception:
        return None


def ensure_wallet(user_id):
    wallet = query_db("SELECT * FROM user_wallets WHERE user_id = ?", (user_id,), one=True)
    if wallet:
        return wallet

    execute_db(
        """
        INSERT INTO user_wallets (
            user_id,
            coin_balance,
            benefit_points,
            cashable_balance,
            lifetime_received_value,
            gifts_received_count
        )
        VALUES (?, 250, 0, 0.0, 0.0, 0)
        """,
        (user_id,),
    )
    return query_db("SELECT * FROM user_wallets WHERE user_id = ?", (user_id,), one=True)


def get_profile_photo(user_id):
    photo = query_db(
        """
        SELECT *
        FROM user_photos
        WHERE user_id = ?
        ORDER BY is_profile_picture DESC, display_order ASC, photo_id DESC
        LIMIT 1
        """,
        (user_id,),
        one=True,
    )
    return photo["photo_url"] if photo else None


def get_or_create_thread(user_one_id, user_two_id):
    low_id = min(user_one_id, user_two_id)
    high_id = max(user_one_id, user_two_id)

    thread = query_db(
        """
        SELECT * FROM chat_threads
        WHERE user_one_id = ? AND user_two_id = ?
        """,
        (low_id, high_id),
        one=True,
    )
    if thread:
        return thread["thread_id"]

    thread_id = execute_db(
        """
        INSERT INTO chat_threads (user_one_id, user_two_id)
        VALUES (?, ?)
        """,
        (low_id, high_id),
    )
    return thread_id


def user_to_profile_json(user_row):
    wallet = ensure_wallet(user_row["user_id"])
    return {
        "user_id": user_row["user_id"],
        "name": user_row["username"],
        "profession": "Premium member",
        "zodiac": "Strong vibe",
        "bio": user_row["bio"] or "",
        "coins": wallet["coin_balance"],
        "gifts_received": wallet["gifts_received_count"],
        "subscription_plan": query_db(
            """
            SELECT plan_name
            FROM subscriptions
            WHERE user_id = ? AND status = 'active'
            ORDER BY sub_id DESC
            LIMIT 1
            """,
            (user_row["user_id"],),
            one=True,
        )["plan_name"] if query_db(
            """
            SELECT plan_name
            FROM subscriptions
            WHERE user_id = ? AND status = 'active'
            ORDER BY sub_id DESC
            LIMIT 1
            """,
            (user_row["user_id"],),
            one=True,
        ) else "free",
    }


# ============================================================
# APP CONTEXT SETUP
# ============================================================

@app.before_request
def bootstrap():
    init_db()


# ============================================================
# AUTH ROUTES
# ============================================================

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        birth_date = request.form.get("birth_date", "").strip()
        gender = request.form.get("gender", "").strip() or None
        bio = request.form.get("bio", "").strip() or None

        if not username or not email or not password or not birth_date:
            flash("Please complete all required fields.", "danger")
            return render_template("register.html")

        existing = query_db(
            "SELECT user_id FROM users WHERE username = ? OR email = ?",
            (username, email),
            one=True,
        )
        if existing:
            flash("Username or email already exists.", "danger")
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        user_id = execute_db(
            """
            INSERT INTO users (username, email, password_hash, gender, birth_date, bio)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, email, password_hash, gender, birth_date, bio),
        )

        execute_db(
            """
            INSERT INTO subscriptions (user_id, plan_name, status, start_date)
            VALUES (?, 'free', 'active', ?)
            """,
            (user_id, date.today().isoformat()),
        )
        ensure_wallet(user_id)

        user_row = query_db("SELECT * FROM users WHERE user_id = ?", (user_id,), one=True)
        login_user(User(user_row))
        flash("Welcome to QRZ Vibe.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        user_row = query_db("SELECT * FROM users WHERE email = ?", (email,), one=True)
        if not user_row or not check_password_hash(user_row["password_hash"], password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        login_user(User(user_row), remember=True)
        flash("Login successful.", "success")
        next_page = request.args.get("next")
        if next_page and urlparse(next_page).netloc == "":
            return redirect(next_page)
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ============================================================
# MAIN APP ROUTES
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():
    wallet = ensure_wallet(current_user.user_id)

    dashboard_stats = {
        "matches": 24,
        "messages": len(query_db(
            """
            SELECT cm.message_id
            FROM chat_messages cm
            JOIN chat_threads ct ON ct.thread_id = cm.thread_id
            WHERE ct.user_one_id = ? OR ct.user_two_id = ?
            """,
            (current_user.user_id, current_user.user_id),
        )),
        "profile_views": 128,
        "vibe_points": wallet["benefit_points"],
        "unread_messages": 3,
        "gifts_sent": len(query_db(
            "SELECT tx_id FROM gift_transactions WHERE sender_user_id = ?",
            (current_user.user_id,),
        )),
        "match_score": "94%",
    }

    matches = query_db(
        """
        SELECT user_id, username, gender, birth_date, bio
        FROM users
        WHERE user_id != ?
        ORDER BY user_id DESC
        LIMIT 6
        """,
        (current_user.user_id,),
    )

    formatted_matches = []
    for idx, row in enumerate(matches, start=1):
        formatted_matches.append({
            "id": row["user_id"],
            "display_name": row["username"],
            "age": calculate_age(row["birth_date"]),
            "city": "Nearby",
            "bio": row["bio"] or "Strong profile energy and good chemistry potential.",
            "zodiac": "Great vibe",
            "profession": "Interesting match",
            "compatibility": f"{90 + (idx % 8)}%",
            "chat_url": url_for("chat", partner_id=row["user_id"]),
            "profile_url": url_for("profile", user_id=row["user_id"]),
        })

    gifts = query_db(
        """
        SELECT *
        FROM gifts
        WHERE is_active = 1
        ORDER BY coin_cost ASC
        LIMIT 6
        """
    )

    formatted_gifts = []
    for gift in gifts:
        formatted_gifts.append({
            "gift_id": gift["gift_id"],
            "name": gift["name"],
            "icon": gift["icon"],
            "price": f"${gift['cash_price']:.2f}",
            "description": f"Send {gift['name']} inside private chats.",
        })

    return render_template(
        "dashboard.html",
        dashboard_stats=dashboard_stats,
        matches=formatted_matches,
        gifts=formatted_gifts,
        spotlight=formatted_matches[:3],
        messages=[],
    )


@app.route("/matches")
@login_required
def matches():
    users = query_db(
        """
        SELECT user_id, username, gender, birth_date, bio
        FROM users
        WHERE user_id != ?
        ORDER BY user_id DESC
        LIMIT 20
        """,
        (current_user.user_id,),
    )

    match_list = []
    for idx, row in enumerate(users, start=1):
        match_list.append({
            "id": row["user_id"],
            "display_name": row["username"],
            "age": calculate_age(row["birth_date"]),
            "city": "Nearby",
            "bio": row["bio"] or "Ready for a meaningful connection and private conversation.",
            "zodiac": "Strong vibe",
            "profession": "Premium member",
            "compatibility": f"{90 + (idx % 8)}%",
            "chat_url": url_for("chat", partner_id=row["user_id"]),
            "profile_url": url_for("profile", user_id=row["user_id"]),
        })

    likes = match_list[:5]
    vibe_candidates = match_list[5:10]

    return render_template(
        "matches.html",
        matches=match_list,
        likes=likes,
        vibe_candidates=vibe_candidates,
    )


@app.route("/chat", methods=["GET", "POST"])
@login_required
def chat():
    partner_id = request.args.get("partner_id", type=int)
    active_match = None
    message_list = []

    if partner_id and partner_id != current_user.user_id:
        partner = query_db("SELECT * FROM users WHERE user_id = ?", (partner_id,), one=True)
        if partner:
            active_match = {
                "id": partner["user_id"],
                "display_name": partner["username"],
                "city": "Nearby",
                "status": "Available for private chat",
            }

            thread_id = get_or_create_thread(current_user.user_id, partner_id)

            if request.method == "POST":
                body = request.form.get("message", "").strip()
                if body:
                    execute_db(
                        """
                        INSERT INTO chat_messages (thread_id, sender_user_id, body, message_type)
                        VALUES (?, ?, ?, 'text')
                        """,
                        (thread_id, current_user.user_id, body),
                    )
                    flash("Message sent.", "success")
                    return redirect(url_for("chat", partner_id=partner_id))

            messages = query_db(
                """
                SELECT *
                FROM chat_messages
                WHERE thread_id = ?
                ORDER BY message_id ASC
                """,
                (thread_id,),
            )

            for msg in messages:
                message_list.append({
                    "body": msg["body"],
                    "time": msg["created_at"],
                    "is_mine": msg["sender_user_id"] == current_user.user_id,
                })

    thread_rows = query_db(
        """
        SELECT ct.thread_id,
               CASE
                   WHEN ct.user_one_id = ? THEN u2.user_id
                   ELSE u1.user_id
               END AS other_user_id,
               CASE
                   WHEN ct.user_one_id = ? THEN u2.username
                   ELSE u1.username
               END AS other_username
        FROM chat_threads ct
        JOIN users u1 ON u1.user_id = ct.user_one_id
        JOIN users u2 ON u2.user_id = ct.user_two_id
        WHERE ct.user_one_id = ? OR ct.user_two_id = ?
        ORDER BY ct.thread_id DESC
        """,
        (current_user.user_id, current_user.user_id, current_user.user_id, current_user.user_id),
    )

    conversations = []
    for row in thread_rows:
        last_message = query_db(
            """
            SELECT body, created_at
            FROM chat_messages
            WHERE thread_id = ?
            ORDER BY message_id DESC
            LIMIT 1
            """,
            (row["thread_id"],),
            one=True,
        )
        conversations.append({
            "id": row["other_user_id"],
            "display_name": row["other_username"],
            "last_message": last_message["body"] if last_message else "Start your private conversation.",
            "time": last_message["created_at"] if last_message else "Now",
            "unread_count": 0,
            "chat_url": url_for("chat", partner_id=row["other_user_id"]),
        })

    return render_template(
        "chat.html",
        conversations=conversations,
        messages=message_list,
        active_match=active_match,
        message_post_url=url_for("chat", partner_id=partner_id) if partner_id else url_for("chat"),
    )


@app.route("/profile")
@app.route("/profile/<int:user_id>")
@login_required
def profile(user_id=None):
    target_user_id = user_id or current_user.user_id
    row = query_db("SELECT * FROM users WHERE user_id = ?", (target_user_id,), one=True)
    if not row:
        abort(404)

    profile_data = {
        "id": row["user_id"],
        "display_name": row["username"],
        "age": calculate_age(row["birth_date"]),
        "city": "Nearby",
        "profession": "Premium member" if target_user_id != current_user.user_id else "Your profile",
        "zodiac": "Strong chemistry",
        "bio": row["bio"] or "This member is building a stronger profile and better dating presence.",
        "long_bio": row["bio"] or "This profile supports bright visuals, gifting, private chat, subscriptions, and premium upgrades.",
        "looking_for": "Meaningful connection",
        "relationship_style": "Warm, respectful, intentional",
        "education": "Growth-oriented mindset",
        "lifestyle": "Bright energy and authentic conversation",
    }

    photos = query_db(
        """
        SELECT *
        FROM user_photos
        WHERE user_id = ?
        ORDER BY is_profile_picture DESC, display_order ASC, photo_id DESC
        """,
        (target_user_id,),
    )

    photo_objects = [{"photo_url": p["photo_url"]} for p in photos]

    interests = [
        "Travel",
        "Music",
        "Fitness",
        "Coffee dates",
        "Adventure",
        "Deep conversation",
    ]

    prompts = [
        {"question": "A perfect date is...", "answer": "Good conversation, chemistry, and beautiful energy."},
        {"question": "What matters most to me...", "answer": "Respect, attraction, and emotional intelligence."},
        {"question": "My vibe is...", "answer": "Confident, warm, and intentional."},
    ]

    return render_template(
        "profile.html",
        profile=profile_data,
        photos=photo_objects,
        interests=interests,
        prompts=prompts,
    )


# ============================================================
# API ROUTES
# ============================================================

@app.route("/api/profile/<int:user_id>", methods=["GET"])
def api_get_profile(user_id):
    user = query_db("SELECT * FROM users WHERE user_id = ?", (user_id,), one=True)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify(user_to_profile_json(user)), 200


@app.route("/api/send_gift", methods=["POST"])
def api_send_gift():
    data = request.get_json(silent=True) or {}

    sender_id = data.get("sender_id")
    receiver_id = data.get("receiver_id")
    gift_id = data.get("gift_id")
    quantity = int(data.get("quantity", 1)) if str(data.get("quantity", 1)).isdigit() else 1

    if not sender_id or not receiver_id:
        return jsonify({"error": "sender_id and receiver_id are required"}), 400

    if int(sender_id) == int(receiver_id):
        return jsonify({"error": "You cannot send gifts to yourself"}), 400

    sender = query_db("SELECT * FROM users WHERE user_id = ?", (sender_id,), one=True)
    receiver = query_db("SELECT * FROM users WHERE user_id = ?", (receiver_id,), one=True)

    if not sender or not receiver:
        return jsonify({"error": "Sender or receiver not found"}), 404

    if gift_id:
        gift = query_db("SELECT * FROM gifts WHERE gift_id = ? AND is_active = 1", (gift_id,), one=True)
    else:
        gift = query_db(
            """
            SELECT *
            FROM gifts
            WHERE coin_cost = 50
            ORDER BY gift_id ASC
            LIMIT 1
            """,
            one=True,
        )

    if not gift:
        return jsonify({"error": "Gift not found"}), 404

    sender_wallet = ensure_wallet(int(sender_id))
    ensure_wallet(int(receiver_id))

    total_coin_cost = int(gift["coin_cost"]) * max(quantity, 1)
    total_cash_value = float(gift["cash_price"]) * max(quantity, 1)
    receiver_cash_credit = round(total_cash_value * 0.70, 2)

    if sender_wallet["coin_balance"] < total_coin_cost:
        return jsonify({"error": "Insufficient coins"}), 400

    execute_db(
        """
        UPDATE user_wallets
        SET coin_balance = coin_balance - ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        (total_coin_cost, sender_id),
    )

    execute_db(
        """
        UPDATE user_wallets
        SET gifts_received_count = gifts_received_count + ?,
            coin_balance = coin_balance + ?,
            cashable_balance = cashable_balance + ?,
            lifetime_received_value = lifetime_received_value + ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        (
            max(quantity, 1),
            int(round(total_coin_cost * 0.70)),
            receiver_cash_credit,
            total_cash_value,
            receiver_id,
        ),
    )

    execute_db(
        """
        INSERT INTO gift_transactions (
            sender_user_id,
            receiver_user_id,
            gift_id,
            quantity,
            total_coin_cost,
            total_cash_value,
            receiver_cash_credit,
            receiver_benefit_points,
            message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sender_id,
            receiver_id,
            gift["gift_id"],
            max(quantity, 1),
            total_coin_cost,
            total_cash_value,
            receiver_cash_credit,
            10 * max(quantity, 1),
            "API gift send",
        ),
    )

    updated_sender_wallet = ensure_wallet(int(sender_id))
    updated_receiver_wallet = ensure_wallet(int(receiver_id))

    return jsonify(
        {
            "message": "Gift sent successfully!",
            "gift": {
                "gift_id": gift["gift_id"],
                "name": gift["name"],
                "icon": gift["icon"],
                "quantity": max(quantity, 1),
            },
            "sender": {
                "user_id": int(sender_id),
                "new_balance": updated_sender_wallet["coin_balance"],
            },
            "receiver": {
                "user_id": int(receiver_id),
                "gifts_received": updated_receiver_wallet["gifts_received_count"],
                "coins": updated_receiver_wallet["coin_balance"],
                "cashable_balance": updated_receiver_wallet["cashable_balance"],
            },
        }
    ), 200


# ============================================================
# SUBSCRIPTIONS / PREMIUM / VIDEO CHAT
# ============================================================

@app.route("/subscriptions")
@login_required
def subscriptions():
    plans = [
        {
            "name": "free",
            "price": "$0",
            "features": [
                "Basic matching",
                "Limited chat",
                "Receive gifts",
            ],
        },
        {
            "name": "premium",
            "price": "$12.99 / month",
            "features": [
                "Unlimited private chat",
                "Video chat access",
                "Gift discounts",
                "Who liked you",
            ],
        },
        {
            "name": "vip",
            "price": "$29.99 / month",
            "features": [
                "All Premium features",
                "Priority visibility",
                "Better gift conversion benefits",
                "VIP badge and advanced controls",
            ],
        },
    ]
    return render_template("subscriptions.html", plans=plans)


@app.route("/subscribe/<plan_name>", methods=["POST"])
@login_required
def subscribe(plan_name):
    if plan_name not in {"free", "premium", "vip"}:
        abort(404)

    execute_db(
        """
        UPDATE subscriptions
        SET status = 'expired'
        WHERE user_id = ? AND status = 'active'
        """,
        (current_user.user_id,),
    )

    execute_db(
        """
        INSERT INTO subscriptions (user_id, plan_name, status, start_date)
        VALUES (?, ?, 'active', ?)
        """,
        (current_user.user_id, plan_name, date.today().isoformat()),
    )

    flash(f"Your plan is now {plan_name.title()}.", "success")
    return redirect(url_for("subscriptions"))


@app.route("/video-chat/<int:partner_id>")
@login_required
@subscription_required("premium", "vip")
def video_chat(partner_id):
    partner = query_db("SELECT * FROM users WHERE user_id = ?", (partner_id,), one=True)
    if not partner:
        abort(404)

    room_data = {
        "room_name": f"qrz-vibe-room-{current_user.user_id}-{partner_id}",
        "partner_name": partner["username"],
        "message": "This route is the premium gate for private video chat.",
    }
    return render_template("video_chat.html", room=room_data)


# ============================================================
# GIFTS / WALLET / PRIVATE GIFTING
# ============================================================

@app.route("/gifts")
@login_required
def gifts():
    wallet = ensure_wallet(current_user.user_id)
    gift_rows = query_db(
        """
        SELECT *
        FROM gifts
        WHERE is_active = 1
        ORDER BY coin_cost ASC
        """
    )

    gift_list = []
    for row in gift_rows:
        gift_list.append({
            "gift_id": row["gift_id"],
            "name": row["name"],
            "slug": row["slug"],
            "icon": row["icon"],
            "coin_cost": row["coin_cost"],
            "cash_price": row["cash_price"],
            "category": row["category"],
        })

    packages = [
        {"name": "Starter", "coins": 100, "price": "$0.99"},
        {"name": "Casual", "coins": 250, "price": "$1.99"},
        {"name": "Popular", "coins": 700, "price": "$4.99"},
        {"name": "Social", "coins": 1500, "price": "$9.99"},
        {"name": "Premium", "coins": 3500, "price": "$19.99"},
    ]

    return render_template(
        "gifts.html",
        wallet=wallet,
        gifts=gift_list,
        packages=packages,
    )


@app.route("/send-gift/<int:receiver_user_id>", methods=["POST"])
@login_required
def send_gift(receiver_user_id):
    if receiver_user_id == current_user.user_id:
        flash("You cannot send gifts to yourself.", "warning")
        return redirect(url_for("matches"))

    receiver = query_db("SELECT * FROM users WHERE user_id = ?", (receiver_user_id,), one=True)
    if not receiver:
        abort(404)

    gift_id = request.form.get("gift_id", type=int)
    quantity = max(request.form.get("quantity", type=int, default=1), 1)
    message = request.form.get("message", "").strip() or None

    gift = query_db("SELECT * FROM gifts WHERE gift_id = ? AND is_active = 1", (gift_id,), one=True)
    if not gift:
        flash("Gift not found.", "danger")
        return redirect(url_for("matches"))

    sender_wallet = ensure_wallet(current_user.user_id)
    ensure_wallet(receiver_user_id)

    total_coins = gift["coin_cost"] * quantity
    total_cash = float(gift["cash_price"]) * quantity
    receiver_cash_credit = round(total_cash * 0.40, 2)
    receiver_benefits = 10 * quantity

    if sender_wallet["coin_balance"] < total_coins:
        flash("Not enough coins. Please buy a package first.", "warning")
        return redirect(url_for("gifts"))

    execute_db(
        """
        UPDATE user_wallets
        SET coin_balance = coin_balance - ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        (total_coins, current_user.user_id),
    )

    execute_db(
        """
        UPDATE user_wallets
        SET benefit_points = benefit_points + ?,
            gifts_received_count = gifts_received_count + ?,
            cashable_balance = cashable_balance + ?,
            lifetime_received_value = lifetime_received_value + ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        (receiver_benefits, quantity, receiver_cash_credit, total_cash, receiver_user_id),
    )

    execute_db(
        """
        INSERT INTO gift_transactions (
            sender_user_id,
            receiver_user_id,
            gift_id,
            quantity,
            total_coin_cost,
            total_cash_value,
            receiver_cash_credit,
            receiver_benefit_points,
            message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            current_user.user_id,
            receiver_user_id,
            gift_id,
            quantity,
            total_coins,
            total_cash,
            receiver_cash_credit,
            receiver_benefits,
            message,
        ),
    )

    thread_id = get_or_create_thread(current_user.user_id, receiver_user_id)
    execute_db(
        """
        INSERT INTO chat_messages (thread_id, sender_user_id, body, message_type)
        VALUES (?, ?, ?, 'gift')
        """,
        (
            thread_id,
            current_user.user_id,
            f"Sent gift: {gift['icon']} {gift['name']}" + (f" — {message}" if message else ""),
        ),
    )

    flash(f"You sent {gift['name']} successfully.", "success")
    return redirect(url_for("chat", partner_id=receiver_user_id))


@app.route("/wallet")
@login_required
def wallet():
    wallet = ensure_wallet(current_user.user_id)

    received = query_db(
        """
        SELECT gt.*, g.name, g.icon, u.username AS sender_name
        FROM gift_transactions gt
        JOIN gifts g ON g.gift_id = gt.gift_id
        JOIN users u ON u.user_id = gt.sender_user_id
        WHERE gt.receiver_user_id = ?
        ORDER BY gt.tx_id DESC
        LIMIT 20
        """,
        (current_user.user_id,),
    )

    return render_template("wallet.html", wallet=wallet, received_gifts=received)


# ============================================================
# PHOTO UPLOAD
# ============================================================

@app.route("/upload-photo", methods=["POST"])
@login_required
def upload_photo():
    if "photo" not in request.files:
        flash("No photo uploaded.", "danger")
        return redirect(url_for("profile"))

    file = request.files["photo"]
    if file.filename == "":
        flash("Please choose a file.", "warning")
        return redirect(url_for("profile"))

    if not allowed_file(file.filename):
        flash("Unsupported file type.", "danger")
        return redirect(url_for("profile"))

    filename = secure_filename(file.filename)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    final_name = f"user_{current_user.user_id}_{timestamp}_{filename}"
    save_path = Path(app.config["UPLOAD_FOLDER"]) / final_name
    file.save(save_path)

    photo_url = f"/static/uploads/photos/{final_name}"
    is_profile_picture = 1 if request.form.get("is_profile_picture") == "1" else 0

    if is_profile_picture:
        execute_db(
            """
            UPDATE user_photos
            SET is_profile_picture = 0, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (current_user.user_id,),
        )

    execute_db(
        """
        INSERT INTO user_photos (user_id, photo_url, is_profile_picture, display_order, visibility)
        VALUES (?, ?, ?, 0, 'public')
        """,
        (current_user.user_id, photo_url, is_profile_picture),
    )

    flash("Photo uploaded successfully.", "success")
    return redirect(url_for("profile"))


# ============================================================
# AFFILIATE REDIRECT
# ============================================================

@app.route("/go/<partner_id>")
@login_required
def affiliate_redirect(partner_id):
    links = {
        "date-safety": "https://www.beenverified.com/affiliate-link-123",
        "therapy": "https://www.betterhelp.com/affiliate-link-456",
        "premium-coaching": "https://example.com/premium-coaching-affiliate",
    }

    target_url = links.get(partner_id)
    if not target_url:
        flash("Affiliate partner not found.", "warning")
        return redirect(url_for("dashboard"))

    execute_db(
        """
        INSERT INTO affiliate_stats (user_id, partner, target_url, click_time)
        VALUES (?, ?, ?, ?)
        """,
        (current_user.user_id, partner_id, target_url, datetime.utcnow().isoformat()),
    )

    return redirect(target_url)


# ============================================================
# DEBUG / DEV SEED
# ============================================================

@app.route("/seed-demo")
def seed_demo():
    existing = query_db("SELECT COUNT(*) AS total FROM users", one=True)
    if existing["total"] > 0:
        flash("Demo users already exist.", "info")
        return redirect(url_for("login"))

    users_to_add = [
        ("alex", "alex@example.com", "Password123!", "male", "1993-06-12", "Confident, warm, and loves meaningful connection."),
        ("maya", "maya@example.com", "Password123!", "female", "1997-03-09", "Bright energy, real conversation, and chemistry."),
        ("sofia", "sofia@example.com", "Password123!", "female", "1995-08-17", "Adventure, music, and emotionally intelligent people."),
        ("julian", "julian@example.com", "Password123!", "male", "1991-11-02", "Professional, romantic, and intentional."),
    ]

    for username, email, password, gender, birth_date, bio in users_to_add:
        user_id = execute_db(
            """
            INSERT INTO users (username, email, password_hash, gender, birth_date, bio)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, email, generate_password_hash(password), gender, birth_date, bio),
        )
        execute_db(
            """
            INSERT INTO subscriptions (user_id, plan_name, status, start_date)
            VALUES (?, 'free', 'active', ?)
            """,
            (user_id, date.today().isoformat()),
        )
        ensure_wallet(user_id)

    flash("Demo data created.", "success")
    return redirect(url_for("login"))


# ============================================================
# HEALTH
# ============================================================

@app.route("/health")
def health():
    return {
        "status": "ok",
        "app": "QRZ Vibe",
        "database": app.config["DATABASE"],
        "time": datetime.utcnow().isoformat(),
    }


# ============================================================
# APP RUN
# ============================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
