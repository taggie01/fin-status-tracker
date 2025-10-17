from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from sqlalchemy import func

app = Flask(__name__)
app.secret_key = 'secret-key'  # ต้องมีสำหรับ Flash Messages
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///transactions.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # ปิดการแจ้งเตือน
db = SQLAlchemy(app)


# ==============================
#  MODELS (โครงสร้างฐานข้อมูล)
# ==============================
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10))  # 'Income' หรือ 'Expense'
    category = db.Column(db.String(50))
    description = db.Column(db.String(200))  # ใช้สำหรับปุ่มด่วน
    amount = db.Column(db.Float)
    # ใช้ db.Column(db.Date) เพื่อให้เก็บเฉพาะวันที่ได้
    date_posted = db.Column(db.Date, default=datetime.now().date())


with app.app_context():
    db.create_all()


# ==============================
#  ROUTES (เส้นทางเว็บ)
# ==============================

@app.route('/', methods=['GET'])
def index():
    date_filter = request.args.get('date')

    # ดึงข้อมูลตาม Filter
    if date_filter:
        try:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
            transactions = Transaction.query.filter_by(date_posted=date_obj).order_by(
                Transaction.date_posted.desc()).all()
        except ValueError:
            flash('รูปแบบวันที่ไม่ถูกต้อง', 'danger')
            transactions = Transaction.query.order_by(Transaction.date_posted.desc()).all()
    else:
        transactions = Transaction.query.order_by(Transaction.date_posted.desc()).all()

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

    # ส่งวันที่ปัจจุบันเพื่อตั้งค่าเริ่มต้นในฟอร์ม (แก้ไข Error ก่อนหน้า)
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
def add_transaction():
    try:
        t_type = request.form['type']
        amount = float(request.form['amount'])
        category = request.form['category']
        # description ถูกลบจากฟอร์มหลัก แต่รับจากปุ่มด่วน
        description = request.form.get('description', '')
        date_str = request.form.get('date_posted', '')

        date_posted = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now().date()

        new_t = Transaction(type=t_type, amount=amount, category=category, description=description,
                            date_posted=date_posted)
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
def edit_transaction(transaction_id):
    try:
        t = Transaction.query.get_or_404(transaction_id)

        t.type = request.form['type']
        t.amount = float(request.form['amount'])
        t.category = request.form['category']
        # Note: เราอนุญาตให้ Description เป็นค่าว่างได้
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
def delete_transaction(transaction_id):
    t = Transaction.query.get(transaction_id)
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
def clear_all():
    Transaction.query.delete()
    db.session.commit()
    flash('ล้างข้อมูลทั้งหมดเรียบร้อยแล้ว', 'warning')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)