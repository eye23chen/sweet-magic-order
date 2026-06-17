from flask import Flask, render_template, request, jsonify, redirect
from dotenv import load_dotenv
load_dotenv()
import os
import threading
import urllib.request
import json
from datetime import datetime
import psycopg2
import psycopg2.extras
import hashlib
import urllib.parse
import time

app = Flask(__name__, static_folder='static', template_folder='templates')

DATABASE_URL = os.environ.get('DATABASE_URL', '')

BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
FROM_EMAIL = 'yinding90141369@gmail.com'
FROM_NAME = '甘甜魔法 Sweet Magic'


def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
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
    cur.close()
    conn.close()


def send_confirm_email(to_email, name, quantity, total, payment, address, order_id=None, status='待處理'):
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
                <tr><td style="padding:6px 0;color:#888;">訂單編號</td><td style="padding:6px 0;font-weight:700;color:#333;">#{order_id}</td></tr>
                <tr><td style="padding:6px 0;color:#888;">商品</td><td style="padding:6px 0;font-weight:700;color:#333;">甘甜魔法（1盒20小包裝入）</td></tr>
                <tr><td style="padding:6px 0;color:#888;">數量</td><td style="padding:6px 0;">{quantity} 盒</td></tr>
                <tr><td style="padding:6px 0;color:#888;">金額</td><td style="padding:6px 0;font-size:1.2rem;font-weight:900;color:#ff8c00;">NT${total:,}（含運）</td></tr>
                <tr><td style="padding:6px 0;color:#888;">收件地址</td><td style="padding:6px 0;">{address}</td></tr>
                <tr><td style="padding:6px 0;color:#888;">付款方式</td><td style="padding:6px 0;">{payment}</td></tr>
                <tr><td style="padding:6px 0;color:#888;">付款狀態</td><td style="padding:6px 0;font-weight:700;color:{'#2e7d32' if status == '已付款' else '#e07000'};">{'✅ 已付款' if status == '已付款' else '⏳ 待付款'}</td></tr>
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


ECPAY_MERCHANT_ID = os.environ.get('ECPAY_MERCHANT_ID', '2000132')
ECPAY_HASH_KEY    = os.environ.get('ECPAY_HASH_KEY', '5294y06JbISpM5x9')
ECPAY_HASH_IV     = os.environ.get('ECPAY_HASH_IV', 'v77hoKGq4kWxNNIS')
ECPAY_API_URL     = 'https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5'
BASE_URL          = os.environ.get('BASE_URL', 'https://web-production-baae6.up.railway.app')

def ecpay_check_mac(params):
    sorted_params = sorted(params.items(), key=lambda x: x[0].lower())
    raw = '&'.join(f'{k}={v}' for k, v in sorted_params)
    raw = f'HashKey={ECPAY_HASH_KEY}&{raw}&HashIV={ECPAY_HASH_IV}'
    raw = urllib.parse.quote_plus(raw).lower()
    return hashlib.sha256(raw.encode()).hexdigest().upper()

def build_ecpay_form(order_id, total, name):
    trade_no = f'SM{order_id:08d}{int(time.time()) % 100000:05d}'
    trade_date = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    params = {
        'MerchantID':        ECPAY_MERCHANT_ID,
        'MerchantTradeNo':   trade_no,
        'MerchantTradeDate': trade_date,
        'PaymentType':       'aio',
        'TotalAmount':       str(total),
        'TradeDesc':         '甘甜魔法訂單',
        'ItemName':          f'甘甜魔法x{total//700 if total % 700 == 0 else 1}',
        'ReturnURL':         f'{BASE_URL}/ecpay/callback',
        'OrderResultURL':    f'{BASE_URL}/ecpay/result',
        'CustomField1':      str(order_id),
        'ChoosePayment':     'ALL',
        'EncryptType':       '1',
    }
    params['CheckMacValue'] = ecpay_check_mac(params)
    fields = ''.join(f'<input type="hidden" name="{k}" value="{v}">' for k, v in params.items())
    return f'''<!DOCTYPE html><html><body>
    <form id="ecpay" action="{ECPAY_API_URL}" method="POST">{fields}</form>
    <script>document.getElementById("ecpay").submit();</script>
    </body></html>'''

API_KEY = os.environ.get('API_KEY', 'yinding-sweet-magic-2026')

LINE_TOKEN = os.environ.get('LINE_TOKEN', '')
LINE_USER_ID = os.environ.get('LINE_USER_ID', '')

def send_line_notify(name, phone, quantity, total, payment, address, order_id=None):
    if not LINE_TOKEN or not LINE_USER_ID:
        return
    try:
        order_str = f"訂單編號：#{order_id}\n" if order_id else ""
        msg = f"🛒 新訂單通知！\n{order_str}姓名：{name}\n電話：{phone}\n數量：{quantity} 盒\n金額：NT${total:,}\n付款：{payment}\n地址：{address}"
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
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM orders ORDER BY id DESC')
    rows = cur.fetchall()
    cur.close()
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
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO orders (created_at,name,phone,email,address,quantity,total,payment) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',
        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), name, phone, email, address, quantity, total, payment)
    )
    order_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    if payment == '線上金流（綠界）':
        return jsonify({'success': True, 'order_id': order_id, 'ecpay': True})

    threading.Thread(target=send_confirm_email, args=(email, name, quantity, total, payment, address, order_id), daemon=True).start()
    threading.Thread(target=send_line_notify, args=(name, phone, quantity, total, payment, address, order_id), daemon=True).start()

    return jsonify({'success': True, 'order_id': order_id})


@app.route('/ecpay/checkout/<int:order_id>')
def ecpay_checkout(order_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM orders WHERE id=%s', (order_id,))
    o = cur.fetchone()
    cur.close()
    conn.close()
    if not o:
        return '訂單不存在', 404
    return build_ecpay_form(o['id'], o['total'], o['name'])


@app.route('/ecpay/callback', methods=['POST'])
def ecpay_callback():
    data = request.form.to_dict()
    rtn_code = data.get('RtnCode', '')
    order_id = data.get('CustomField1', '')
    if rtn_code == '1' and order_id:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("UPDATE orders SET status='已付款' WHERE id=%s RETURNING *", (int(order_id),))
        o = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if o:
            threading.Thread(target=send_confirm_email, args=(o['email'], o['name'], o['quantity'], o['total'], o['payment'], o['address'], o['id'], '已付款'), daemon=True).start()
            threading.Thread(target=send_line_notify, args=(o['name'], o['phone'], o['quantity'], o['total'], '已付款✅', o['address'], o['id']), daemon=True).start()
    return '1|OK'


@app.route('/ecpay/result')
def ecpay_result():
    rtn_code = request.args.get('RtnCode', '')
    order_id = request.args.get('CustomField1', '')
    if rtn_code == '1':
        return redirect(f'/?paid=1&order={order_id}')
    return redirect(f'/?paid=0&order={order_id}')


init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5051))
    app.run(debug=False, host='0.0.0.0', port=port)
