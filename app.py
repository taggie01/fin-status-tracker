from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from sqlalchemy import func
import os

# NEW IMPORTS FOR AUTHENTICATION
from flask_login import UserMixin, LoginManager, login_required, login_user, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default-fallback-key')

# ******************************************************
# DB CONFIG (PostgreSQL for Render / SQLite for Local)
# ******************************************************
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    # แก้ชื่อเป็น new_fin_tracker.db เพื่อให้สร้างใหม่ (ตามที่คุยกัน)
    DATABASE_URL = 'sqlite:///new_fin_tracker.db'

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ==============================
#  FLASK-LOGIN CONFIG
# ==============================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # กำหนดให้ redirect ไปหน้า login หากยังไม่ล็อกอิน


@login_manager.user_loader
def load_user(user_id):
    """ฟังก์ชันนี้บอก Flask-Login ว่าจะโหลดข้อมูล User อย่างไรจาก ID ที่เก็บใน Session"""
    return User.query.get(int(user_id))


# ==============================
#  MODELS (โครงสร้างฐานข้อมูล)
# ==============================

# NEW: User Model สำหรับการล็อกอิน
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    # เพิ่ม method สำหรับเข้ารหัสและตรวจสอบรหัสผ่าน
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# แก้ไข: Transaction Model เพื่อเชื่อมโยงกับผู้ใช้
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10))
    category = db.Column(db.String(50))
    description = db.Column(db.String(200))
    amount = db.Column(db.Float)
    date_posted = db.Column(db.Date, default=datetime.now().date())

    # NEW: Foreign Key เพื่อระบุเจ้าของรายการ
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='transactions')


with app.app_context():
    db.create_all()


# ==============================
#  AUTHENTICATION ROUTES (Routes ที่คุณเพิ่งเพิ่มโค้ด Logic)
# ==============================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # 1. ตรวจสอบว่า Username นี้มีอยู่แล้วหรือไม่
        user = User.query.filter_by(username=username).first()
        if user:
            flash('ชื่อผู้ใช้งานนี้มีคนใช้แล้ว', 'danger')
            return redirect(url_for('register'))

        # 2. สร้างผู้ใช้ใหม่และเข้ารหัสรหัสผ่าน
        new_user = User(username=username)
        new_user.set_password(password)

        # 3. บันทึกเข้าฐานข้อมูล
        try:
            db.session.add(new_user)
            db.session.commit()

            flash('ลงทะเบียนสำเร็จ! กรุณาเข้าสู่ระบบ', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            db.session.rollback()
            flash(f'เกิดข้อผิดพลาดในการลงทะเบียน: {e}', 'danger')
            return redirect(url_for('register'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        # ตรวจสอบว่ามีผู้ใช้หรือไม่ และรหัสผ่านถูกต้องหรือไม่
        if user is None or not user.check_password(password):
            flash('ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง', 'danger')
            return redirect(url_for('login'))

        # ล็อกอินสำเร็จ
        login_user(user)
        return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('คุณออกจากระบบแล้ว', 'success')
    return redirect(url_for('login'))


# ==============================
#  MAIN APP ROUTES (ใช้ @login_required และ filter ข้อมูลตาม user_id)
# ==============================

@app.route('/', methods=['GET'])
@login_required  # ต้องล็อกอินก่อนเข้าถึง
def index():
    date_filter = request.args.get('date')

    # Query: ดึงข้อมูลเฉพาะของผู้ใช้ที่ล็อกอินอยู่ (current_user.id)
    base_query = Transaction.query.filter_by(user_id=current_user.id)

    if date_filter:
        try:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
            transactions = base_query.filter_by(date_posted=date_obj).order_by(
                Transaction.date_posted.desc()).all()
        except ValueError:
            flash('รูปแบบวันที่ไม่ถูกต้อง', 'danger')
            transactions = base_query.order_by(Transaction.date_posted.desc()).all()
    else:
        transactions = base_query.order_by(Transaction.date_posted.desc()).all()

    # คำนวณสรุปยอด (จากรายการที่ถูก Filter แล้ว)
    total_income = sum(t.amount for t in transactions if t.type == 'Income')
    total_expense = sum(t.amount for t in transactions if t.type == 'Expense')
    net_balance = total_income - total_expense

    # สรุปยอดรายจ่ายตามหมวดหมู่สำหรับกราฟ
    category_summary = {}
    for t in transactions:
        if t.type == 'Expense':
            category_summary[t.category] = category_summary.get(t.category, 0) + t.amount

    category_summary = list(category_summary.items())
    current_date = datetime.now().strftime('%Y-%m-%d')

    return render_template(
        'index.html',
        transactions=transactions,
        total_income=total_income,
        total_expense=total_expense,
        net_balance=net_balance,
        category_summary=category_summary,
        current_date=current_date
    )


# ------------------------------
# 1. เพิ่มรายการ (Create)
# ------------------------------
@app.route('/add', methods=['POST'])
@login_required
def add_transaction():
    try:
        t_type = request.form['type']
        amount = float(request.form['amount'])
        category = request.form['category']
        description = request.form.get('description', '')
        date_str = request.form.get('date_posted', '')

        date_posted = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now().date()

        # บันทึกรายการพร้อม user_id
        new_t = Transaction(type=t_type, amount=amount, category=category, description=description,
                            date_posted=date_posted, user_id=current_user.id)
        db.session.add(new_t)
        db.session.commit()
        flash('เพิ่มรายการเรียบร้อยแล้ว', 'success')
    except Exception as e:
        flash(f'เกิดข้อผิดพลาดในการเพิ่มรายการ: {e}', 'danger')
    return redirect(url_for('index'))


# ------------------------------
# 2. แก้ไขรายการ (Update)
# ------------------------------
@app.route('/edit/<int:transaction_id>', methods=['POST'])
@login_required
def edit_transaction(transaction_id):
    try:
        # ตรวจสอบความเป็นเจ้าของด้วย user_id
        t = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()

        t.type = request.form['type']
        t.amount = float(request.form['amount'])
        t.category = request.form['category']
        t.description = request.form.get('description', t.description)
        date_str = request.form.get('date_posted', '')

        if date_str:
            t.date_posted = datetime.strptime(date_str, '%Y-%m-%d').date()

        db.session.commit()
        flash('แก้ไขรายการเรียบร้อยแล้ว', 'success')
    except Exception as e:
        flash(f'เกิดข้อผิดพลาดในการแก้ไขรายการ: {e}', 'danger')
    return redirect(url_for('index'))


# ------------------------------
# 3. ลบรายการ (Delete)
# ------------------------------
@app.route('/delete/<int:transaction_id>', methods=['POST'])
@login_required
def delete_transaction(transaction_id):
    # ตรวจสอบความเป็นเจ้าของด้วย user_id
    t = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first()
    if t:
        db.session.delete(t)
        db.session.commit()
        flash('ลบรายการเรียบร้อยแล้ว', 'danger')
    else:
        flash('ไม่พบรายการที่ต้องการลบ', 'warning')
    return redirect(url_for('index'))


# ------------------------------
# 4. ล้างข้อมูลทั้งหมด
# ------------------------------
@app.route('/clear_all', methods=['POST'])
@login_required
def clear_all():
    # ลบรายการทั้งหมดที่ user_id ตรงกับผู้ใช้ปัจจุบันเท่านั้น
    Transaction.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('ล้างข้อมูลทั้งหมดเรียบร้อยแล้ว', 'warning')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)