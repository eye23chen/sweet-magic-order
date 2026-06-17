from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
load_dotenv()
import sqlite3
import os
import threading
import urllib.request
import json
from datetime import datetime

app = Flask(__name__, static_folder='static', template_folder='templates')

DB_PATH = os.path.join(os.path.dirname(__file__), 'orders.db')

BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
FROM_EMAIL = 'yinding90141369@gmail.com'
FROM_NAME = '甘甜魔法 Sweet Magic'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            address TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            total INTEGER NOT NULL,
            payment TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '待處理'
        )
    ''')
    conn.commit()
    conn.close()


def send_confirm_email(to_email, name, quantity, total, payment, address):
    if not BREVO_API_KEY:
        return
    try:
        bank_html = "<div style='background:#e8f5e9;border-radius:12px;padding:20px;margin-bottom:24px;'><h3 style='color:#2e7d32;margin:0 0 12px;'>🏦 匯款資訊</h3><p style='color:#555;font-size:.9rem;line-height:2;margin:0;'>銀行：新光商業銀行（代碼 103）北嘉義分行<br>帳號：0666-10-100559-5<br>戶名：飲鼎國際有限公司<br><strong style='color:#2e7d32;'>匯款後請加入 LINE @607eldnj 並傳送匯款截圖</strong></p></div>" if payment == "銀行匯款" else ""
        html = f'''
        <div style="font-family:'Noto Sans TC',sans-serif;max-width:560px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.1);">
          <div style="background:linear-gradient(135deg,#ff8c00,#ffa500);padding:32px;text-align:center;">
            <h1 style="color:#fff;margin:0;font-size:1.6rem;">✨ 甘甜魔法</h1>
            <p style="color:#fff3e0;margin:8px 0 0;">Sweet Magic Miracle Fruit Licorice Salt Powder</p>
          </div>
          <div style="padding:32px;">
            <p style="font-size:1rem;color:#333;">親愛的 <strong>{name}</strong> 您好，</p>
            <p style="color:#555;margin-top:8px;line-height:1.8;">感謝您訂購甘甜魔法！我們已收到您的訂單，將盡快與您聯繫確認出貨。</p>

            <div style="background:#fff8f0;border-radius:12px;padding:20px;margin:24px 0;border-left:4px solid #ffa500;">
              <h3 style="color:#e07000;margin:0 0 12px;">📋 訂單明細</h3>
              <table style="width:100%;font-size:.95rem;color:#555;border-collapse:collapse;">
                <tr><td style="padding:6px 0;color:#888;">商品</td><td style="padding:6px 0;font-weight:700;color:#333;">甘甜魔法（1盒20小包裝入）</td></tr>
                <tr><td style="padding:6px 0;color:#888;">數量</td><td style="padding:6px 0;">{quantity} 盒</td></tr>
                <tr><td style="padding:6px 0;color:#888;">金額</td><td style="padding:6px 0;font-size:1.2rem;font-weight:900;color:#ff8c00;">NT${total:,}（含運）</td></tr>
                <tr><td style="padding:6px 0;color:#888;">收件地址</td><td style="padding:6px 0;">{address}</td></tr>
                <tr><td style="padding:6px 0;color:#888;">付款方式</td><td style="padding:6px 0;">{payment}</td></tr>
              </table>
            </div>

            {bank_html}

            <p style="color:#555;line-height:1.8;">如有任何問題，歡迎透過以下方式聯繫我們：</p>
            <div style="margin-top:12px;font-size:.9rem;color:#555;line-height:2;">
              📧 yinding90141369@gmail.com<br>
              💬 LINE 官方帳號：@607eldnj
            </div>
          </div>
          <div style="background:#f5f5f5;padding:16px;text-align:center;font-size:.8rem;color:#aaa;">
            飲鼎國際有限公司｜嘉義市西區大同路783號1樓｜統編 90141369
          </div>
        </div>
        '''

        payload = json.dumps({
            'sender': {'name': FROM_NAME, 'email': FROM_EMAIL},
            'to': [{'email': to_email}],
            'subject': '【甘甜魔法】訂單確認通知',
            'htmlContent': html
        }).encode()

        req = urllib.request.Request(
            'https://api.brevo.com/v3/smtp/email',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'api-key': BREVO_API_KEY
            }
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f'Email 寄送失敗: {e}')


API_KEY = os.environ.get('API_KEY', 'yinding-sweet-magic-2026')

LINE_TOKEN = os.environ.get('LINE_TOKEN', '')
LINE_USER_ID = os.environ.get('LINE_USER_ID', '')

def send_line_notify(name, phone, quantity, total, payment, address):
    if not LINE_TOKEN or not LINE_USER_ID:
        return
    try:
        msg = f"🛒 新訂單通知！\n姓名：{name}\n電話：{phone}\n數量：{quantity} 盒\n金額：NT${total:,}\n付款：{payment}\n地址：{address}"
        data = json.dumps({'to': LINE_USER_ID, 'messages': [{'type': 'text', 'text': msg}]}).encode()
        req = urllib.request.Request(
            'https://api.line.me/v2/bot/message/push',
            data=data,
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {LINE_TOKEN}'}
        )
        urllib.request.urlopen(req, timeout=8)
    except Exception as e:
        print(f'LINE 通知失敗: {e}')

@app.route('/api/orders')
def api_orders():
    if request.headers.get('X-API-Key') != API_KEY:
        return jsonify({'error': 'unauthorized'}), 401
    conn = get_db()
    rows = conn.execute('SELECT * FROM orders ORDER BY id DESC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/order', methods=['POST'])
def order():
    data = request.get_json()
    name     = data.get('name', '').strip()
    phone    = data.get('phone', '').strip()
    email    = data.get('email', '').strip()
    address  = data.get('address', '').strip()
    quantity = int(data.get('quantity', 1))
    payment  = data.get('payment', '線上金流（綠界）').strip()
    shipping = 0 if quantity >= 2 else 80
    total    = quantity * 700 + shipping

    if not all([name, phone, email, address]):
        return jsonify({'success': False, 'message': '請填寫所有必填欄位'})

    conn = get_db()
    conn.execute(
        'INSERT INTO orders (created_at,name,phone,email,address,quantity,total,payment) VALUES (?,?,?,?,?,?,?,?)',
        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), name, phone, email, address, quantity, total, payment)
    )
    conn.commit()
    conn.close()

    threading.Thread(target=send_confirm_email, args=(email, name, quantity, total, payment, address), daemon=True).start()
    threading.Thread(target=send_line_notify, args=(name, phone, quantity, total, payment, address), daemon=True).start()

    return jsonify({'success': True})


init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5051))
    app.run(debug=False, host='0.0.0.0', port=port)
