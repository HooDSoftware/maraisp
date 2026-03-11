# ISP Backend — MikroTik RB2011

FastAPI backend for a Kenyan ISP. Connects to MikroTik RB2011 via IP Cloud DDNS.
Handles M-Pesa payments, PPPoE/Hotspot management, WhatsApp + Gmail notifications.

## Architecture

```
Customer pays via M-Pesa (STK Push)
        ↓
Daraja callback → Render (this app)
        ↓
librouteros API → MikroTik (762d07842fbf.sn.mynetname.net:28728)
        ↓
PPPoE account OR Hotspot voucher created automatically
        ↓
WhatsApp + Gmail notification sent to customer
```

## File Structure

```
isp-backend/
├── main.py               # FastAPI app + auth
├── database.py           # SQLAlchemy models (SQLite)
├── requirements.txt
├── render.yaml           # Render deployment config
├── .env.template         # Copy to .env and fill in
├── services/
│   ├── mikrotik.py       # librouteros — all router operations
│   ├── mpesa.py          # Daraja STK Push + callback parser
│   ├── whatsapp.py       # pywhatkit sender + message templates
│   └── gmail.py          # SMTP sender + HTML email templates
├── routers/
│   ├── payments.py       # STK Push + callback + activation logic
│   ├── pppoe.py          # PPPoE CRUD
│   ├── hotspot.py        # Hotspot voucher management
│   ├── sessions.py       # Live session viewer + kick
│   └── reports.py        # Revenue + usage reports
└── static/
    └── dashboard.html    # Admin UI (single HTML file)
```

## Deployment Steps

### 1. Fill in .env
```bash
cp .env.template .env
nano .env   # fill in CHANGE_ME values
```

### 2. Test locally
```bash
pip install -r requirements.txt
uvicorn main:app --reload
# Open http://localhost:8000
```

### 3. Deploy to Render
1. Push to GitHub (`.env` is git-ignored — safe)
2. New Web Service → connect repo
3. Render detects `render.yaml` automatically
4. Go to Environment tab → add all secret values
5. Done — your URL: `https://your-app.onrender.com`

### 4. Set M-Pesa callback URL
In your `.env` / Render env:
```
MPESA_CALLBACK_URL=https://your-app.onrender.com/payments/callback
```

### 5. Router port forward check
Run on the router:
```
/ip firewall nat print where comment="WAN-API-28728"
```
Should show `action=redirect to-ports=8728`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness + router ping |
| POST | `/payments/initiate` | Trigger STK Push |
| POST | `/payments/callback` | M-Pesa Daraja webhook (public) |
| GET | `/payments/status/{id}` | Check payment status |
| GET/POST | `/pppoe/` | List / create PPPoE users |
| DELETE | `/pppoe/{name}` | Delete subscriber |
| POST | `/pppoe/{name}/kick` | Disconnect session |
| POST | `/hotspot/voucher` | Generate voucher(s) |
| GET | `/sessions/pppoe` | Live PPPoE sessions |
| GET | `/sessions/hotspot` | Live hotspot sessions |
| GET | `/reports/summary` | Revenue + subscriber counts |
| GET | `/reports/revenue/daily` | 30-day daily chart data |

All routes except `/health` and `/payments/callback` require HTTP Basic Auth.

## MikroTik Connection

- Host:  `762d07842fbf.sn.mynetname.net`
- Port:  `28728` (WAN port forward → router API 8728)
- The `.rsc` setup script already created this port forward.

## WhatsApp Note

`pywhatkit` requires WhatsApp Web open in a browser session.
For headless Render deployment, set `WHATSAPP_BACKEND=api` and configure
`WHATSAPP_API_URL` + `WHATSAPP_API_TOKEN` using Twilio or Meta Cloud API.
