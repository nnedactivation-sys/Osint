import logging
import aiohttp
import asyncio
import json
import os
import re
import time
import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from datetime import datetime, timedelta
from io import BytesIO
import sqlite3
import matplotlib.pyplot as plt
import seaborn as sns

# -------------------- CONFIGURATION --------------------
BOT_TOKEN = "8543664597:AAFTCq3GJvnztQ_T3qi8M0aDDUNv1lQYvA4"  # अपना टोकन डालो
LOOKUP_API = "https://nmdllpezcocquamhgpmb.supabase.co/functions/v1/lookup?number="
TG_API = "https://legend-hosting.x10.mx/api/tg-num.php"
TG_KEY = "LEGEND-BPB4XP"
OWNER_USERNAME = "@CvvAnkitt"
DEV_NAME = "@CvvAnkitt"
ADMIN_IDS = [8085855107]

# PLAN CONFIGURATION
PLANS = {
    "trial": {
        "name": "🎁 TRIAL",
        "duration_days": 1,
        "searches": 5,
        "tg_lookup": True,
        "price": "FREE",
        "color": "🟢",
        "emoji": "🎁",
        "badge": "FREE"
    },
    "basic": {
        "name": "🔥 BASIC",
        "duration_days": 30,
        "searches": 100,
        "tg_lookup": True,
        "price": "₹199",
        "color": "🟡",
        "emoji": "🔥",
        "badge": "POPULAR"
    },
    "premium": {
        "name": "⚡ PREMIUM",
        "duration_days": 90,
        "searches": 500,
        "tg_lookup": True,
        "price": "₹499",
        "color": "🔵",
        "emoji": "⚡",
        "badge": "BEST VALUE"
    },
    "vip": {
        "name": "👑 VIP",
        "duration_days": 365,
        "searches": 2000,
        "tg_lookup": True,
        "price": "₹999",
        "color": "💜",
        "emoji": "👑",
        "badge": "PREMIUM"
    },
    "unlimited": {
        "name": "∞ UNLIMITED",
        "duration_days": 999,
        "searches": 999999,
        "tg_lookup": True,
        "price": "₹1999",
        "color": "💎",
        "emoji": "∞",
        "badge": "ULTIMATE"
    }
}

# UI COLORS
COLORS = {
    "primary": "🔵",
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "premium": "💎",
    "vip": "👑"
}

# ANIMATED FOOTERS
FOOTERS = [
    "🔥 **Powered by Legend**",
    "⚡ **OSINT Master**",
    "💎 **Premium Service**",
    "👑 **VIP Access**",
    "🚀 **Fast & Secure**",
    "🌟 **24/7 Active**"
]
# -------------------------------------------------------

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# User session data store
user_sessions = {}
user_history = {}

# -------------------- DATABASE SETUP --------------------
def init_db():
    """Initialize SQLite database"""
    try:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY,
                      username TEXT,
                      first_name TEXT,
                      last_name TEXT,
                      plan TEXT DEFAULT 'free',
                      expiry_date TEXT,
                      searches_left INTEGER DEFAULT 0,
                      total_searches INTEGER DEFAULT 0,
                      join_date TEXT,
                      last_active TEXT,
                      used_codes TEXT DEFAULT '[]')''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS redeem_codes
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      code TEXT UNIQUE,
                      plan TEXT,
                      duration_days INTEGER,
                      searches INTEGER,
                      created_by INTEGER,
                      created_date TEXT,
                      expiry_date TEXT,
                      max_uses INTEGER DEFAULT 1,
                      used_count INTEGER DEFAULT 0,
                      used_by TEXT DEFAULT '[]',
                      status TEXT DEFAULT 'active')''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS search_history
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      search_type TEXT,
                      query TEXT,
                      timestamp TEXT,
                      status TEXT)''')
        
        c.execute('''CREATE INDEX IF NOT EXISTS idx_code ON redeem_codes(code)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_user_history ON search_history(user_id)''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")
        return True
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        return False

# -------------------- DATABASE FUNCTIONS --------------------
def add_user_to_db(user_id, username, first_name, last_name=None):
    """Add or update user in database"""
    try:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        existing = c.fetchone()
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if not existing:
            c.execute('''INSERT INTO users 
                        (user_id, username, first_name, last_name, join_date, last_active) 
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (user_id, username, first_name, last_name, now, now))
        else:
            c.execute("UPDATE users SET last_active = ? WHERE user_id = ?", 
                     (now, user_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"DB error: {e}")
        return False

def log_search(user_id, search_type, query, status="success"):
    """Log user search history"""
    try:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''INSERT INTO search_history (user_id, search_type, query, timestamp, status)
                    VALUES (?, ?, ?, ?, ?)''',
                 (user_id, search_type, query, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status))
        conn.commit()
        conn.close()
    except:
        pass

def get_user_history(user_id, limit=10):
    """Get user search history"""
    try:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''SELECT search_type, query, timestamp FROM search_history 
                    WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?''',
                 (user_id, limit))
        history = c.fetchall()
        conn.close()
        return history
    except:
        return []

def get_user_data(user_id):
    """Get user data from database"""
    try:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        conn.close()
        
        if user:
            columns = ['user_id', 'username', 'first_name', 'last_name', 'plan', 
                      'expiry_date', 'searches_left', 'total_searches', 'join_date', 
                      'last_active', 'used_codes']
            return dict(zip(columns, user))
        return None
    except Exception as e:
        logger.error(f"DB error: {e}")
        return None

def update_user_plan(user_id, plan, duration_days, searches):
    """Update user plan after redeem"""
    try:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        
        now = datetime.now()
        expiry = (now + timedelta(days=duration_days)).strftime("%Y-%m-%d")
        
        c.execute("SELECT plan, searches_left, total_searches FROM users WHERE user_id = ?", (user_id,))
        current = c.fetchone()
        
        if current:
            current_plan, current_searches, total_searches = current
            new_searches = current_searches + searches
            new_total = total_searches + searches
        else:
            new_searches = searches
            new_total = searches
        
        c.execute('''UPDATE users 
                    SET plan = ?, expiry_date = ?, searches_left = ?, total_searches = ?, last_active = ?
                    WHERE user_id = ?''',
                 (plan, expiry, new_searches, new_total, now.strftime("%Y-%m-%d %H:%M:%S"), user_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"DB error: {e}")
        return False

def deduct_search(user_id):
    """Deduct one search from user"""
    try:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("UPDATE users SET searches_left = searches_left - 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"DB error: {e}")
        return False

def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS

def get_user_plan_display(user_id):
    """Get user plan for display"""
    if is_admin(user_id):
        return {
            "plan": "👑 ADMIN",
            "expiry": "∞ Lifetime",
            "searches": "∞ Unlimited",
            "plan_display": "👑 **ADMIN**",
            "badge": "👑 OWNER",
            "color": "💎"
        }
    
    user_data = get_user_data(user_id)
    if user_data and user_data['plan'] != 'free':
        plan = PLANS.get(user_data['plan'], {})
        expiry_date = user_data['expiry_date']
        days_left = 0
        
        if expiry_date:
            try:
                expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
                days_left = (expiry - datetime.now()).days
                if days_left < 0:
                    days_left = 0
            except:
                pass
        
        return {
            "plan": user_data['plan'],
            "expiry": f"{expiry_date} ({days_left} days left)",
            "searches": user_data['searches_left'],
            "total": user_data['total_searches'],
            "plan_display": f"{plan.get('emoji', '📦')} **{user_data['plan'].upper()}**",
            "badge": plan.get('badge', 'ACTIVE'),
            "color": plan.get('color', '⚪')
        }
    else:
        return {
            "plan": "free",
            "expiry": "Not subscribed",
            "searches": 0,
            "total": 0,
            "plan_display": "⚠️ **FREE USER**",
            "badge": "TRIAL",
            "color": "⚪"
        }

# -------------------- UI ENHANCEMENTS --------------------
def get_random_footer():
    """Get random animated footer"""
    return random.choice(FOOTERS)

def create_progress_bar(value, total, length=10):
    """Create progress bar"""
    filled = int((value / total) * length) if total > 0 else 0
    empty = length - filled
    
    bar = "█" * filled + "░" * empty
    percentage = (value / total * 100) if total > 0 else 0
    
    return f"`{bar}` {percentage:.1f}%"

def format_number(num):
    """Format number with commas"""
    return f"{num:,}"

# -------------------- REDEEM CODE FUNCTIONS --------------------
def generate_redeem_code(length=12):
    """Generate random redeem code"""
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    code = ''.join(random.choice(chars) for _ in range(length))
    return '-'.join([code[i:i+4] for i in range(0, len(code), 4)])

def create_redeem_code(plan, duration_days, searches, created_by, max_uses=1, expiry_days=30):
    """Create new redeem code"""
    try:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        
        code = generate_redeem_code()
        created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        code_expiry = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d")
        code_storage = code.replace('-', '')
        
        c.execute('''INSERT INTO redeem_codes 
                    (code, plan, duration_days, searches, created_by, created_date, 
                     expiry_date, max_uses, used_count, used_by, status) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (code_storage, plan, duration_days, searches, created_by, created_date, 
                  code_expiry, max_uses, 0, '[]', 'active'))
        
        conn.commit()
        conn.close()
        return code
    except Exception as e:
        logger.error(f"Code creation error: {e}")
        return None

def validate_redeem_code(code_input):
    """Validate redeem code"""
    try:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        
        clean_code = code_input.upper().replace('-', '').strip()
        
        c.execute('''SELECT * FROM redeem_codes WHERE code = ?''', (clean_code,))
        code_data = c.fetchone()
        conn.close()
        
        if not code_data:
            return {"valid": False, "message": f"{COLORS['error']} **Invalid redeem code!**"}
        
        columns = ['id', 'code', 'plan', 'duration_days', 'searches', 'created_by', 
                  'created_date', 'expiry_date', 'max_uses', 'used_count', 'used_by', 'status']
        data = dict(zip(columns, code_data))
        
        if data['status'] != 'active':
            return {"valid": False, "message": f"{COLORS['error']} **This code has been deactivated!**"}
        
        if datetime.now() > datetime.strptime(data['expiry_date'], "%Y-%m-%d"):
            return {"valid": False, "message": f"{COLORS['error']} **This code has expired!**"}
        
        if data['used_count'] >= data['max_uses']:
            return {"valid": False, "message": f"{COLORS['error']} **Maximum uses reached!**"}
        
        data['valid'] = True
        return data
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return {"valid": False, "message": f"{COLORS['error']} **Error: {str(e)}**"}

def use_redeem_code(code, user_id):
    """Mark code as used"""
    try:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        
        c.execute("SELECT used_by, used_count FROM redeem_codes WHERE code = ?", (code,))
        result = c.fetchone()
        
        if result:
            used_by = json.loads(result[0]) if result[0] and result[0] != '[]' else []
            used_count = result[1]
            
            if user_id not in used_by:
                used_by.append(user_id)
                used_count += 1
            
            c.execute('''UPDATE redeem_codes 
                        SET used_by = ?, used_count = ? 
                        WHERE code = ?''',
                     (json.dumps(used_by), used_count, code))
            conn.commit()
        
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Use code error: {e}")
        return False

# -------------------- LOOKUP TEXT FORMATTING - FIXED (FULL DETAILS) --------------------
def format_phone_entry(entry, entry_num):
    """Format a single phone entry - WITH FULL DETAILS, NO CUTS"""
    text = f"**📌 ENTRY #{entry_num}**\n"
    text += f"┌{'─'*38}┐\n"
    
    # Mobile
    mobile = entry.get('mobile', 'N/A')
    if mobile != 'N/A' and mobile != 'None' and mobile:
        # Format with space for readability
        if len(str(mobile)) == 10:
            mobile = f"{str(mobile)[:5]} {str(mobile)[5:]}"
        text += f"│ 📞 **Mobile:** `{mobile}`\n"
    
    # Name
    name = entry.get('name', 'N/A')
    if name != 'N/A' and name != 'None' and name:
        text += f"│ 👤 **Name:** `{name}`\n"
    
    # Father's Name
    fname = entry.get('fname', 'N/A')
    if fname != 'N/A' and fname != 'None' and fname:
        text += f"│ 👨 **Father:** `{fname}`\n"
    
    # Aadhar/ID
    aadhar = entry.get('id', 'N/A')
    if aadhar != 'N/A' and aadhar != 'None' and aadhar:
        aadhar_clean = re.sub(r'\D', '', str(aadhar))
        if len(aadhar_clean) == 12:
            aadhar = f"{aadhar_clean[:4]} {aadhar_clean[4:8]} {aadhar_clean[8:]}"
        text += f"│ 🆔 **Aadhar:** `{aadhar}`\n"
    
    # Address - FULL ADDRESS, NO CUTS
    address = entry.get('address', 'N/A')
    if address != 'N/A' and address != 'None' and address:
        # Clean address
        address = re.sub(r'!+', ' ', str(address))
        address = re.sub(r'\s+', ' ', address).strip()
        
        # Check if address is too long for one line
        if len(address) > 40:
            # Split into multiple lines
            words = address.split()
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 <= 40:
                    current_line += word + " "
                else:
                    if current_line:
                        text += f"│ 📍 **Address:** `{current_line.strip()}`\n"
                        current_line = word + " "
                    else:
                        # If single word is too long, split it
                        if len(word) > 40:
                            # Split long word
                            for i in range(0, len(word), 40):
                                text += f"│    `{word[i:i+40]}`\n"
                        else:
                            current_line = word + " "
            
            if current_line:
                text += f"│    `{current_line.strip()}`\n"
        else:
            text += f"│ 📍 **Address:** `{address}`\n"
    
    # Alternative Number - FIXED: Now showing properly
    alt = entry.get('alt', 'N/A')
    if alt and alt != 'N/A' and alt != 'None' and alt:
        if len(str(alt)) == 10:
            alt = f"{str(alt)[:5]} {str(alt)[5:]}"
        text += f"│ 🔄 **Alt No:** `{alt}`\n"
    else:
        text += f"│ 🔄 **Alt No:** ❌ Nahi hai\n"
    
    # Operator/Circle
    circle = entry.get('circle', 'N/A')
    if circle != 'N/A' and circle != 'None' and circle:
        if "AIRTEL" in circle.upper():
            text += f"│ 📡 **Operator:** 🔴 {circle}\n"
        elif "JIO" in circle.upper():
            text += f"│ 📡 **Operator:** 🟣 {circle}\n"
        elif "VI" in circle.upper() or "VODA" in circle.upper():
            text += f"│ 📡 **Operator:** 🟢 {circle}\n"
        elif "BSNL" in circle.upper():
            text += f"│ 📡 **Operator:** 🔵 {circle}\n"
        else:
            text += f"│ 📡 **Operator:** `{circle}`\n"
    
    # Email
    email = entry.get('email', 'N/A')
    if email and email != 'N/A' and email != 'None' and email:
        if '@' in email:
            local, domain = email.split('@')
            if len(local) > 3:
                hidden = local[:3] + '***@' + domain
            else:
                hidden = local + '@' + domain
            text += f"│ 📧 **Email:** `{hidden}`\n"
        else:
            text += f"│ 📧 **Email:** `{email}`\n"
    else:
        text += f"│ 📧 **Email:** ❌ Nahi hai\n"
    
    text += f"└{'─'*38}┘\n\n"
    return text

def create_phone_text(data, phone_number, current_index=0):
    """Create phone lookup text for specific entry"""
    results = data.get('result', [])
    
    if not results:
        return f"{COLORS['error']} **Koi result nahi mila!**"
    
    total = len(results)
    entry = results[current_index]
    
    text = f"🔍 **PHONE LOOKUP RESULT** 🔍\n"
    text += f"{'━'*40}\n"
    text += f"📞 **Number:** `{phone_number}`\n"
    text += f"⏱ **Time:** {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n"
    text += f"📊 **Entry:** {current_index + 1}/{total}\n"
    text += f"{'━'*40}\n\n"
    
    text += format_phone_entry(entry, current_index + 1)
    
    return text

def create_all_entries_text(data, phone_number):
    """Create text with all entries"""
    results = data.get('result', [])
    
    if not results:
        return f"{COLORS['error']} **Koi result nahi mila!**"
    
    total = len(results)
    
    text = f"📋 **ALL ENTRIES - {phone_number}** 📋\n"
    text += f"{'━'*40}\n"
    text += f"📞 **Number:** `{phone_number}`\n"
    text += f"⏱ **Time:** {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n"
    text += f"📊 **Total Entries:** {total}\n"
    text += f"{'━'*40}\n\n"
    
    for idx, entry in enumerate(results, 1):
        text += format_phone_entry(entry, idx)
    
    text += f"{'━'*40}\n"
    text += f"**{get_random_footer()}** 🔥"
    
    return text

def create_lookup_keyboard(phone_number, current_index, total_entries):
    """Create keyboard with navigation and download"""
    keyboard = []
    
    # Navigation buttons
    nav_buttons = []
    if total_entries > 1:
        if current_index > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"prev_{phone_number}_{current_index}"))
        if current_index < total_entries - 1:
            nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"next_{phone_number}_{current_index}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Action buttons
    action_buttons = [
        InlineKeyboardButton("📋 All Entries", callback_data=f"all_{phone_number}"),
        InlineKeyboardButton("📥 Download JSON", callback_data=f"download_{phone_number}")
    ]
    keyboard.append(action_buttons)
    
    # Extra features
    extra_buttons = [
        InlineKeyboardButton("📊 Statistics", callback_data=f"stats_{phone_number}"),
        InlineKeyboardButton("🔄 Share", callback_data=f"share_{phone_number}")
    ]
    keyboard.append(extra_buttons)
    
    # New search
    keyboard.append([InlineKeyboardButton("🆕 New Search", callback_data="new_search")])
    keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def create_main_menu_keyboard(user_id):
    """Create main menu keyboard"""
    plan_info = get_user_plan_display(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🔍 Phone Lookup", callback_data="menu_phone")],
        [InlineKeyboardButton("📱 Telegram Lookup", callback_data="menu_tg")],
        [InlineKeyboardButton("📊 My Stats", callback_data="menu_stats")],
        [InlineKeyboardButton("💎 Plans", callback_data="menu_plans")],
        [InlineKeyboardButton("🎁 Redeem Code", callback_data="menu_redeem")],
        [InlineKeyboardButton("📞 Contact", callback_data="menu_contact")]
    ]
    
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="menu_admin")])
    
    return InlineKeyboardMarkup(keyboard)

# -------------------- TG LOOKUP --------------------
async def tg_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram ID lookup command"""
    user = update.effective_user
    
    # Check access
    if not is_admin(user.id):
        user_data = get_user_data(user.id)
        if not user_data or user_data['plan'] == 'free' or user_data['searches_left'] <= 0:
            await update.message.reply_text(
                f"{COLORS['error']} **PAID FEATURE!**\n\n"
                f"💎 Use /buy or /redeem to get access\n"
                f"👑 Contact: {OWNER_USERNAME}",
                parse_mode='Markdown'
            )
            return
    
    if not context.args:
        await update.message.reply_text(
            f"{COLORS['warning']} **Usage:** `/tg 123456789`\n\n"
            f"Example: `/tg 123456789`",
            parse_mode='Markdown'
        )
        return
    
    tg_id = context.args[0].strip()
    
    if not tg_id.isdigit():
        await update.message.reply_text(f"{COLORS['error']} Invalid ID! Numbers only.")
        return
    
    msg = await update.message.reply_text(f"🔍 Looking up `{tg_id}`...")
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{TG_API}?key={TG_KEY}&usersid={tg_id}"
            async with session.get(url, timeout=15) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('status') == True:
                        results = data.get('results', {})
                        
                        if results.get('success'):
                            result_data = results.get('result', {})
                            
                            # Get details
                            country = result_data.get('country', 'N/A')
                            number = result_data.get('number', 'N/A')
                            msg_text = result_data.get('msg', 'N/A')
                            
                            # Format number properly - NO SPACES, with +91
                            if number and number != 'N/A':
                                # Remove any existing spaces
                                number = re.sub(r'\s+', '', str(number))
                                # Ensure +91 prefix
                                if not number.startswith('+'):
                                    if len(number) == 10:
                                        number = f"+91{number}"
                                    elif len(number) == 12 and number.startswith('91'):
                                        number = f"+{number}"
                                    else:
                                        number = f"+91{number}"  # Default
                            
                            # Format output
                            text = f"📱 **TELEGRAM LOOKUP RESULT** 📱\n"
                            text += f"{'━'*40}\n"
                            text += f"🆔 **TG ID:** `{tg_id}`\n"
                            text += f"⏱ **Time:** {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n"
                            text += f"{'━'*40}\n\n"
                            
                            # Phone - NO SPACES
                            if number and number != 'N/A':
                                text += f"📞 **Phone:** `{number}`\n"
                            
                            # Country - ONLY country name
                            if country and country != 'N/A':
                                text += f"🌍 **Country:** {country}\n"
                            
                            text += f"📊 **Status:** {msg_text}\n"
                            
                            # Footer
                            text += f"\n{'━'*40}\n"
                            text += f"**{get_random_footer()}** 🔥"
                            
                            # Deduct search for non-admin
                            if not is_admin(user.id):
                                deduct_search(user.id)
                                log_search(user.id, "telegram", tg_id, "success")
                            
                            await msg.edit_text(text, parse_mode='Markdown')
                            
                            # Send success notification
                            plan_info = get_user_plan_display(user.id)
                            if not is_admin(user.id):
                                await context.bot.send_message(
                                    chat_id=user.id,
                                    text=f"{COLORS['success']} **Search Used!**\n"
                                         f"📊 **Remaining:** {plan_info['searches']} searches",
                                    parse_mode='Markdown'
                                )
                        else:
                            await msg.edit_text(f"{COLORS['error']} No data found for this ID.")
                    else:
                        await msg.edit_text(f"{COLORS['error']} {data.get('message', 'Unknown error')}")
                else:
                    await msg.edit_text(f"{COLORS['error']} API Error: {response.status}")
                    
    except Exception as e:
        logger.error(f"TG error: {e}")
        await msg.edit_text(f"{COLORS['error']} Error: {str(e)[:100]}")

# -------------------- PHONE LOOKUP HANDLER --------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phone number lookup"""
    user = update.effective_user
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    
    # Clean number
    cleaned = re.sub(r'[\s\+\-]', '', text)
    
    if cleaned.isdigit() and len(cleaned) == 10:
        phone = cleaned
        
        # Check access
        if not is_admin(user.id):
            user_data = get_user_data(user.id)
            if not user_data or user_data['plan'] == 'free' or user_data['searches_left'] <= 0:
                await update.message.reply_text(
                    f"{COLORS['error']} **No searches left!**\n\n"
                    f"💎 Use /buy or /redeem to get access\n"
                    f"👑 Contact: {OWNER_USERNAME}",
                    parse_mode='Markdown'
                )
                return
        
        msg = await update.message.reply_text(f"🔍 Looking up `{phone}`...")
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{LOOKUP_API}{phone}"
                async with session.get(url, timeout=15) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        results = data.get('result', [])
                        
                        if results:
                            # Store in user_sessions
                            if chat_id not in user_sessions:
                                user_sessions[chat_id] = {}
                            user_sessions[chat_id][phone] = {
                                'data': data,
                                'current_index': 0
                            }
                            
                            total = len(results)
                            
                            # Create first entry text
                            text = create_phone_text(data, phone, 0)
                            text += f"{'━'*40}\n"
                            text += f"**{get_random_footer()}** 🔥"
                            
                            # Create keyboard
                            keyboard = create_lookup_keyboard(phone, 0, total)
                            
                            # Deduct search
                            if not is_admin(user.id):
                                deduct_search(user.id)
                                log_search(user.id, "phone", phone, "success")
                            
                            await msg.edit_text(text, parse_mode='Markdown', reply_markup=keyboard)
                            
                            # Send success notification
                            plan_info = get_user_plan_display(user.id)
                            if not is_admin(user.id):
                                await context.bot.send_message(
                                    chat_id=user.id,
                                    text=f"{COLORS['success']} **Search Used!**\n"
                                         f"📊 **Remaining:** {plan_info['searches']} searches",
                                    parse_mode='Markdown'
                                )
                        else:
                            await msg.edit_text(f"{COLORS['error']} No data found for this number.")
                            log_search(user.id, "phone", phone, "failed")
                    else:
                        await msg.edit_text(f"{COLORS['error']} API Error: {response.status}")
                        log_search(user.id, "phone", phone, "failed")
                        
        except Exception as e:
            logger.error(f"Phone error: {e}")
            await msg.edit_text(f"{COLORS['error']} Error: {str(e)[:100]}")
            log_search(user.id, "phone", phone, "error")
    
    elif cleaned.isdigit() and len(cleaned) > 10:
        phone = cleaned[-10:]
        await update.message.reply_text(
            f"{COLORS['info']} Using last 10 digits: `{phone}`\n\n"
            f"Send /start to return to main menu",
            parse_mode='Markdown'
        )

# -------------------- CALLBACK HANDLER --------------------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if data == "new_search":
        await query.edit_message_text(
            f"🔍 **Send a 10-digit phone number**\n\n"
            f"Example: `9811454590`\n\n"
            f"Or use /tg for Telegram lookup",
            parse_mode='Markdown'
        )
        return
    
    if data == "main_menu":
        plan_info = get_user_plan_display(user_id)
        
        welcome_msg = (
            f"🔍 **PRIVATE OSINT BOT** 🔍\n"
            f"{'━'*40}\n"
            f"✨ **Welcome {update.effective_user.first_name}!** ✨\n\n"
            f"👑 **Owner:** {OWNER_USERNAME}\n"
            f"👨‍💻 **Developer:** {DEV_NAME}\n\n"
            f"📊 **Your Status:**\n"
            f"├ Plan: {plan_info['plan_display']}\n"
            f"├ Expiry: {plan_info['expiry']}\n"
            f"├ Searches: {plan_info['searches']}\n"
            f"└ Total: {format_number(plan_info.get('total', 0))}\n\n"
            f"📌 **Commands:**\n"
            f"├ `9811454590` - Phone Lookup\n"
            f"├ `/tg 123456789` - TG Lookup\n"
            f"├ `/redeem CODE` - Redeem Code\n"
            f"├ `/buy` - Buy Premium\n"
            f"├ `/plans` - View Plans\n"
            f"├ `/history` - Search History\n"
            f"└ `/help` - Help Menu"
        )
        
        keyboard = create_main_menu_keyboard(user_id)
        await query.edit_message_text(welcome_msg, parse_mode='Markdown', reply_markup=keyboard)
        return
    
    # Handle menu options
    if data.startswith("menu_"):
        option = data.replace("menu_", "")
        
        if option == "phone":
            await query.edit_message_text(
                f"🔍 **Send a 10-digit phone number**\n\n"
                f"Example: `9811454590`",
                parse_mode='Markdown'
            )
        elif option == "tg":
            await query.edit_message_text(
                f"📱 **Send Telegram ID**\n\n"
                f"Usage: `/tg 123456789`",
                parse_mode='Markdown'
            )
        elif option == "stats":
            plan_info = get_user_plan_display(user_id)
            history = get_user_history(user_id, 5)
            
            text = f"📊 **YOUR STATISTICS** 📊\n"
            text += f"{'━'*40}\n\n"
            text += f"👤 **User:** `{user_id}`\n"
            text += f"📅 **Joined:** {plan_info.get('join_date', 'N/A')}\n"
            text += f"💎 **Plan:** {plan_info['plan_display']}\n"
            text += f"⏱ **Expiry:** {plan_info['expiry']}\n"
            text += f"🔍 **Searches Left:** {plan_info['searches']}\n"
            text += f"📊 **Total Searches:** {format_number(plan_info.get('total', 0))}\n\n"
            
            if history:
                text += f"**Recent Activity:**\n"
                for h in history:
                    text += f"├ {h[0]} - `{h[1]}` - {h[2][:16]}\n"
            else:
                text += f"**Recent Activity:** No searches yet\n"
            
            text += f"\n{get_random_footer()}"
            
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
            ]])
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)
            
        elif option == "plans":
            text = "💰 **PREMIUM PLANS** 💰\n"
            text += f"{'━'*40}\n\n"
            
            for pid, plan in PLANS.items():
                if pid != 'trial':
                    text += f"{plan['emoji']} **{plan['name']}** `{plan['badge']}`\n"
                    text += f"├ Price: {plan['price']}\n"
                    text += f"├ Duration: {plan['duration_days']} Days\n"
                    text += f"├ Searches: {format_number(plan['searches'])}\n"
                    text += f"└ TG Lookup: {'✅' if plan['tg_lookup'] else '❌'}\n\n"
            
            text += f"**Contact:** {OWNER_USERNAME}"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📞 Contact", url=f"https://t.me/{OWNER_USERNAME[1:]}")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ])
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
            
        elif option == "redeem":
            await query.edit_message_text(
                f"🎁 **REDEEM CODE**\n\n"
                f"Usage: `/redeem CODE`\n\n"
                f"Example: `/redeem GNR2-EB2F-PRBX`",
                parse_mode='Markdown'
            )
            
        elif option == "contact":
            await query.edit_message_text(
                f"📞 **CONTACT**\n\n"
                f"👑 Owner: {OWNER_USERNAME}\n"
                f"👨‍💻 Developer: {DEV_NAME}\n\n"
                f"💎 For support, payment, or queries:\n"
                f"📩 DM: {OWNER_USERNAME}",
                parse_mode='Markdown'
            )
            
        elif option == "admin" and is_admin(user_id):
            text = f"⚙️ **ADMIN PANEL** ⚙️\n"
            text += f"{'━'*40}\n\n"
            text += f"📊 **Quick Actions:**\n"
            text += f"├ /gen - Generate codes\n"
            text += f"├ /codes - List codes\n"
            text += f"├ /users - List users\n"
            text += f"├ /stats - Bot stats\n"
            text += f"└ /broadcast - Send message\n\n"
            text += f"📝 **Examples:**\n"
            text += f"├ `/gen trial 5` - 5 trial codes\n"
            text += f"├ `/gen basic 3` - 3 basic codes\n"
            text += f"└ `/broadcast Hello` - Send to all"
            
            await query.edit_message_text(text, parse_mode='Markdown')
        
        return
    
    # Parse phone lookup callback data
    parts = data.split('_')
    
    if parts[0] in ['prev', 'next', 'all', 'download', 'stats', 'share']:
        action = parts[0]
        phone = parts[1]
        
        # Check if data exists
        if chat_id not in user_sessions or phone not in user_sessions[chat_id]:
            await query.edit_message_text(f"{COLORS['error']} Session expired! Search again.")
            return
        
        session = user_sessions[chat_id][phone]
        data = session['data']
        results = data.get('result', [])
        total = len(results)
        
        if action == 'prev' or action == 'next':
            current = int(parts[2])
            new_index = current - 1 if action == 'prev' else current + 1
            
            if 0 <= new_index < total:
                session['current_index'] = new_index
                text = create_phone_text(data, phone, new_index)
                text += f"{'━'*40}\n"
                text += f"**{get_random_footer()}** 🔥"
                
                keyboard = create_lookup_keyboard(phone, new_index, total)
                await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)
        
        elif action == 'all':
            text = create_all_entries_text(data, phone)
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Back to Entries", callback_data=f"back_{phone}_{session['current_index']}")
            ]])
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)
        
        elif action == 'download':
            # Create JSON file
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            file_bytes = BytesIO(json_str.encode('utf-8'))
            file_bytes.name = f"lookup_{phone}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            await query.edit_message_text("📥 Downloading JSON file...")
            await context.bot.send_document(
                chat_id=chat_id,
                document=file_bytes,
                caption=f"📱 Lookup Result for {phone}\n🔍 {get_random_footer()}"
            )
            
            # Show original message again
            text = create_phone_text(data, phone, session['current_index'])
            text += f"{'━'*40}\n"
            text += f"**{get_random_footer()}** 🔥"
            keyboard = create_lookup_keyboard(phone, session['current_index'], total)
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)
        
        elif action == 'stats':
            # Create simple stats
            text = f"📊 **STATISTICS FOR {phone}** 📊\n"
            text += f"{'━'*40}\n\n"
            text += f"📌 **Total Entries:** {total}\n"
            
            # Count unique values
            names = set()
            addresses = set()
            cities = set()
            
            for entry in results:
                if entry.get('name') and entry['name'] != 'N/A' and entry['name'] != 'None':
                    names.add(entry['name'])
                if entry.get('address') and entry['address'] != 'N/A' and entry['address'] != 'None':
                    addresses.add(entry['address'])
            
            text += f"👤 **Unique Names:** {len(names)}\n"
            text += f"📍 **Unique Addresses:** {len(addresses)}\n"
            text += f"\n{get_random_footer()}"
            
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Back", callback_data=f"back_{phone}_{session['current_index']}")
            ]])
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)
        
        elif action == 'share':
            # Share result
            share_text = f"🔍 **Lookup Result for {phone}**\n"
            share_text += f"📊 Found {total} entries\n"
            share_text += f"🔗 Shared by {OWNER_USERNAME}"
            
            await query.edit_message_text(share_text, parse_mode='Markdown')
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ Shared successfully!"
            )
    
    elif parts[0] == 'back':
        phone = parts[1]
        index = int(parts[2])
        
        if chat_id in user_sessions and phone in user_sessions[chat_id]:
            session = user_sessions[chat_id][phone]
            data = session['data']
            results = data.get('result', [])
            total = len(results)
            
            if 0 <= index < total:
                session['current_index'] = index
                text = create_phone_text(data, phone, index)
                text += f"{'━'*40}\n"
                text += f"**{get_random_footer()}** 🔥"
                
                keyboard = create_lookup_keyboard(phone, index, total)
                await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)

# -------------------- BOT COMMANDS --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user = update.effective_user
    add_user_to_db(user.id, user.username, user.first_name, user.last_name)
    
    plan_info = get_user_plan_display(user.id)
    
    welcome_msg = (
        f"🔍 **PRIVATE OSINT BOT** 🔍\n"
        f"{'━'*40}\n"
        f"✨ **Welcome {user.first_name}!** ✨\n\n"
        f"👑 **Owner:** {OWNER_USERNAME}\n"
        f"👨‍💻 **Developer:** {DEV_NAME}\n\n"
        f"📊 **Your Status:**\n"
        f"├ Plan: {plan_info['plan_display']}\n"
        f"├ Expiry: {plan_info['expiry']}\n"
        f"├ Searches: {plan_info['searches']}\n"
        f"└ Total: {format_number(plan_info.get('total', 0))}\n\n"
        f"📌 **Commands:**\n"
        f"├ `9811454590` - Phone Lookup\n"
        f"├ `/tg 123456789` - TG Lookup\n"
        f"├ `/redeem CODE` - Redeem Code\n"
        f"├ `/buy` - Buy Premium\n"
        f"├ `/plans` - View Plans\n"
        f"├ `/history` - Search History\n"
        f"└ `/help` - Help Menu"
    )
    
    keyboard = create_main_menu_keyboard(user.id)
    await update.message.reply_text(welcome_msg, parse_mode='Markdown', reply_markup=keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    user = update.effective_user
    
    help_text = (
        f"📚 **HELP MENU**\n\n"
        f"**🔍 LOOKUP FEATURES:**\n"
        f"• Send 10 digit number for phone lookup\n"
        f"• Multiple entries ke liye Prev/Next buttons\n"
        f"• Download JSON option available\n"
        f"• View statistics of results\n"
        f"• Share results with others\n"
        f"• `/tg 123456789` - TG lookup\n\n"
        f"**💎 REDEEM SYSTEM:**\n"
        f"• `/redeem CODE` - Activate code\n"
        f"• `/plans` - View all plans\n"
        f"• `/buy` - Purchase premium\n"
        f"• `/history` - Your search history\n\n"
        f"**📊 ACCOUNT:**\n"
        f"• `/start` - Main menu\n"
        f"• `/help` - This menu\n"
        f"• `/stats` - Your statistics\n"
    )
    
    if is_admin(user.id):
        help_text += (
            f"\n**👑 ADMIN COMMANDS:**\n"
            f"• `/gen plan qty` - Generate codes\n"
            f"• `/codes` - List all codes\n"
            f"• `/users` - List all users\n"
            f"• `/broadcast msg` - Message all users\n"
            f"• `/stats` - Bot statistics\n"
            f"• `/db` - Database stats\n\n"
            f"**📝 Examples:**\n"
            f"`/gen trial 5` - 5 trial codes\n"
            f"`/gen basic 3` - 3 basic codes\n"
        )
    
    help_text += f"\n**Owner:** {OWNER_USERNAME}"
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user search history"""
    user_id = update.effective_user.id
    history = get_user_history(user_id, 10)
    
    if not history:
        await update.message.reply_text(f"{COLORS['info']} No search history found.")
        return
    
    text = f"📋 **YOUR SEARCH HISTORY**\n"
    text += f"{'━'*40}\n\n"
    
    for i, h in enumerate(history, 1):
        search_type, query, timestamp = h
        emoji = "📱" if search_type == "phone" else "🆔"
        text += f"{i}. {emoji} **{search_type.upper()}:** `{query}`\n"
        text += f"   ⏱ {timestamp[:16]}\n"
    
    text += f"\n{get_random_footer()}"
    await update.message.reply_text(text, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User statistics command"""
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        # Show admin stats
        try:
            conn = sqlite3.connect('users.db', check_same_thread=False)
            c = conn.cursor()
            
            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM users WHERE plan != 'free'")
            paid_users = c.fetchone()[0]
            
            c.execute("SELECT SUM(searches_left) FROM users")
            total_searches = c.fetchone()[0] or 0
            
            c.execute("SELECT SUM(total_searches) FROM users")
            total_used = c.fetchone()[0] or 0
            
            c.execute("SELECT COUNT(*) FROM redeem_codes WHERE status='active'")
            active_codes = c.fetchone()[0]
            
            conn.close()
            
            text = (
                f"📊 **BOT STATISTICS**\n"
                f"{'━'*40}\n\n"
                f"👥 **Users:**\n"
                f"├ Total: {format_number(total_users)}\n"
                f"├ Paid: {format_number(paid_users)}\n"
                f"└ Free: {format_number(total_users - paid_users)}\n\n"
                f"🔍 **Searches:**\n"
                f"├ Available: {format_number(total_searches)}\n"
                f"├ Used: {format_number(total_used)}\n"
                f"└ Total: {format_number(total_searches + total_used)}\n\n"
                f"🎟️ **Active Codes:** {format_number(active_codes)}\n\n"
                f"👑 **Owner:** {OWNER_USERNAME}"
            )
            
        except Exception as e:
            text = f"{COLORS['error']} Error: {e}"
    else:
        # Show user stats
        plan_info = get_user_plan_display(user_id)
        history = get_user_history(user_id, 5)
        
        text = f"📊 **YOUR STATISTICS** 📊\n"
        text += f"{'━'*40}\n\n"
        text += f"👤 **User ID:** `{user_id}`\n"
        text += f"💎 **Plan:** {plan_info['plan_display']}\n"
        text += f"⏱ **Expiry:** {plan_info['expiry']}\n"
        text += f"🔍 **Searches Left:** {plan_info['searches']}\n"
        text += f"📊 **Total Used:** {format_number(plan_info.get('total', 0))}\n"
        
        if history:
            text += f"\n**Recent Activity:**\n"
            for h in history[:3]:
                text += f"├ {h[0]} - `{h[1]}`\n"
        
        text += f"\n{get_random_footer()}"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redeem code command"""
    user = update.effective_user
    
    if is_admin(user.id):
        await update.message.reply_text(f"{COLORS['vip']} **You're Admin!** Unlimited access.", parse_mode='Markdown')
        return
    
    if not context.args:
        await update.message.reply_text(
            f"{COLORS['warning']} Usage: `/redeem CODE`\n"
            f"Example: `/redeem GNR2-EB2F-PRBX`",
            parse_mode='Markdown'
        )
        return
    
    code_input = ' '.join(context.args)
    processing = await update.message.reply_text(f"{COLORS['info']} Validating code...", parse_mode='Markdown')
    
    result = validate_redeem_code(code_input)
    
    if not result['valid']:
        await processing.edit_text(result['message'], parse_mode='Markdown')
        return
    
    user_data = get_user_data(user.id)
    if user_data:
        used_codes = json.loads(user_data['used_codes']) if user_data['used_codes'] and user_data['used_codes'] != '[]' else []
        if result['code'] in used_codes:
            await processing.edit_text(f"{COLORS['error']} You already used this code!", parse_mode='Markdown')
            return
    
    success = update_user_plan(user.id, result['plan'], result['duration_days'], result['searches'])
    
    if success:
        use_redeem_code(result['code'], user.id)
        
        # Update used codes
        try:
            conn = sqlite3.connect('users.db', check_same_thread=False)
            c = conn.cursor()
            used_codes = json.loads(user_data['used_codes']) if user_data and user_data['used_codes'] and user_data['used_codes'] != '[]' else []
            used_codes.append(result['code'])
            c.execute("UPDATE users SET used_codes = ? WHERE user_id = ?", (json.dumps(used_codes), user.id))
            conn.commit()
            conn.close()
        except:
            pass
        
        plan = PLANS.get(result['plan'], {})
        expiry = (datetime.now() + timedelta(days=result['duration_days'])).strftime('%d-%m-%Y')
        
        await processing.edit_text(
            f"{COLORS['success']} **REDEEM SUCCESSFUL!**\n\n"
            f"🎁 **Plan:** {plan.get('emoji', '📦')} {plan.get('name', result['plan'].upper())}\n"
            f"⏱ **Duration:** {result['duration_days']} Days\n"
            f"🔍 **Searches:** {format_number(result['searches'])}\n"
            f"📅 **Expiry:** {expiry}\n\n"
            f"✨ Enjoy premium features!",
            parse_mode='Markdown'
        )
    else:
        await processing.edit_text(f"{COLORS['error']} Error! Contact admin.", parse_mode='Markdown')

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pricing"""
    user = update.effective_user
    
    if is_admin(user.id):
        await update.message.reply_text(f"{COLORS['vip']} You're Admin! Unlimited access.", parse_mode='Markdown')
        return
    
    text = "💰 **PREMIUM PLANS** 💰\n"
    text += f"{'━'*40}\n\n"
    
    for pid, plan in PLANS.items():
        if pid != 'trial':
            text += f"{plan['emoji']} **{plan['name']}** `{plan['badge']}`\n"
            text += f"├ Price: {plan['price']}\n"
            text += f"├ Duration: {plan['duration_days']} Days\n"
            text += f"├ Searches: {format_number(plan['searches'])}\n"
            text += f"├ TG Lookup: {'✅' if plan['tg_lookup'] else '❌'}\n"
            text += f"└ Progress: {create_progress_bar(plan['searches'], PLANS['unlimited']['searches'])}\n\n"
    
    text += f"**Contact:** {OWNER_USERNAME}"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Contact", url=f"https://t.me/{OWNER_USERNAME[1:]}")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def plans_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all plans"""
    text = "📋 **ALL PLANS** 📋\n"
    text += f"{'━'*40}\n\n"
    
    for pid, plan in PLANS.items():
        text += f"{plan['emoji']} **{plan['name']}** `{plan['badge']}`\n"
        text += f"├ Duration: {plan['duration_days']} Days\n"
        text += f"├ Searches: {format_number(plan['searches'])}\n"
        text += f"├ TG Lookup: {'✅' if plan['tg_lookup'] else '❌'}\n"
        text += f"└ Price: {plan['price']}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

# -------------------- ADMIN COMMANDS --------------------
# -------------------- ADMIN COMMANDS --------------------
@bot.message_handler(commands=['gen'])
def gen_command(m):
    """Generate redeem codes"""
    if not is_admin(m.from_user.id):
        bot.reply_to(m, "❌ Admin only!")
        return
    
    try:
        parts = m.text.split()
        if len(parts) < 3:
            plans_list = '\n'.join([f"├ {p['emoji']} {p['name']} ({pid})" for pid, p in PLANS.items()])
            bot.reply_to(m, 
                f"❌ Usage: `/gen plan quantity`\n\n"
                f"**Plans:**\n{plans_list}\n\n"
                f"**Examples:**\n"
                f"`/gen trial 5`\n"
                f"`/gen basic 3`\n"
                f"`/gen vip 2`",
                parse_mode='Markdown'
            )
            return
        
        plan_key = parts[1].lower()
        quantity = int(parts[2])
        
        if plan_key not in PLANS:
            bot.reply_to(m, "❌ Invalid plan!")
            return
        
        plan = PLANS[plan_key]
        codes = []
        
        for i in range(quantity):
            code = create_redeem_code(plan_key, plan['duration_days'], plan['searches'], m.from_user.id)
            if code:
                codes.append(code)
            time.sleep(0.1)
        
        if codes:
            codes_text = '\n'.join([f"`{code}`" for code in codes])
            bot.reply_to(m,
                f"✅ **{quantity} Codes Generated!**\n\n"
                f"📋 **Plan:** {plan['emoji']} {plan['name']}\n"
                f"⏱ **Duration:** {plan['duration_days']} Days\n"
                f"🔍 **Searches:** {plan['searches']}\n\n"
                f"**Codes:**\n{codes_text}",
                parse_mode='Markdown'
            )
        else:
            bot.reply_to(m, "❌ Error generating codes!")
            
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['remove_code'])
def remove_code(m):
    """Remove a specific redeem code"""
    if not is_admin(m.from_user.id):
        bot.reply_to(m, "❌ Admin only!")
        return
    
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "❌ Usage: `/remove_code CODE`\nExample: `/remove_code ABCD1234`", parse_mode='Markdown')
            return
        
        code_input = parts[1].upper().replace('-', '').strip()
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        c.execute("SELECT * FROM redeem_codes WHERE code = ?", (code_input,))
        existing = c.fetchone()
        
        if not existing:
            bot.reply_to(m, f"❌ Code `{code_input}` not found!", parse_mode='Markdown')
            conn.close()
            return
        
        c.execute("DELETE FROM redeem_codes WHERE code = ?", (code_input,))
        conn.commit()
        conn.close()
        
        bot.reply_to(m, f"✅ Code `{code_input}` removed successfully!", parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['bulk_remove'])
def bulk_remove(m):
    """Remove multiple codes at once"""
    if not is_admin(m.from_user.id):
        bot.reply_to(m, "❌ Admin only!")
        return
    
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "❌ Usage: `/bulk_remove PLAN`\nExamples:\n`/bulk_remove trial`\n`/bulk_remove expired`\n`/bulk_remove all`", parse_mode='Markdown')
            return
        
        plan = parts[1].lower()
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        if plan == 'expired':
            c.execute("DELETE FROM redeem_codes WHERE expiry_date < date('now')")
            deleted = c.rowcount
            msg = f"✅ {deleted} expired codes removed!"
            
        elif plan in ['trial', 'basic', 'premium', 'vip', 'unlimited']:
            c.execute("DELETE FROM redeem_codes WHERE plan = ?", (plan,))
            deleted = c.rowcount
            msg = f"✅ {deleted} {plan} codes removed!"
            
        elif plan == 'all':
            c.execute("DELETE FROM redeem_codes")
            deleted = c.rowcount
            msg = f"✅ {deleted} all codes removed!"
            
        else:
            bot.reply_to(m, "❌ Invalid plan! Use: trial/basic/premium/vip/unlimited/expired/all")
            conn.close()
            return
        
        conn.commit()
        conn.close()
        bot.reply_to(m, msg)
        
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['deactivate_code'])
def deactivate_code(m):
    """Deactivate a code without deleting"""
    if not is_admin(m.from_user.id):
        bot.reply_to(m, "❌ Admin only!")
        return
    
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "❌ Usage: `/deactivate_code CODE`", parse_mode='Markdown')
            return
        
        code_input = parts[1].upper().replace('-', '').strip()
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        c.execute("UPDATE redeem_codes SET status = 'deactivated' WHERE code = ?", (code_input,))
        conn.commit()
        
        if c.rowcount > 0:
            bot.reply_to(m, f"✅ Code `{code_input}` deactivated!", parse_mode='Markdown')
        else:
            bot.reply_to(m, f"❌ Code `{code_input}` not found!", parse_mode='Markdown')
        
        conn.close()
        
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['reactivate_code'])
def reactivate_code(m):
    """Reactivate a deactivated code"""
    if not is_admin(m.from_user.id):
        bot.reply_to(m, "❌ Admin only!")
        return
    
    try:
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "❌ Usage: `/reactivate_code CODE`", parse_mode='Markdown')
            return
        
        code_input = parts[1].upper().replace('-', '').strip()
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        c.execute("UPDATE redeem_codes SET status = 'active' WHERE code = ?", (code_input,))
        conn.commit()
        
        if c.rowcount > 0:
            bot.reply_to(m, f"✅ Code `{code_input}` reactivated!", parse_mode='Markdown')
        else:
            bot.reply_to(m, f"❌ Code `{code_input}` not found!", parse_mode='Markdown')
        
        conn.close()
        
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['codes'])
def codes_command(m):
    """List all codes"""
    if not is_admin(m.from_user.id):
        bot.reply_to(m, "❌ Admin only!")
        return
    
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT code, plan, created_date, expiry_date, max_uses, used_count, status FROM redeem_codes ORDER BY created_date DESC LIMIT 20")
        codes = c.fetchall()
        conn.close()
        
        if not codes:
            bot.reply_to(m, "📭 No codes found.")
            return
        
        text = "📋 **RECENT CODES**\n"
        text += f"{'━'*40}\n\n"
        
        for code in codes:
            code_id, plan, created, expiry, max_uses, used, status = code
            status_emoji = "✅" if status == 'active' else "❌"
            plan_emoji = PLANS.get(plan, {}).get('emoji', '📦')
            
            text += f"{status_emoji} `{code_id}`\n"
            text += f"├ {plan_emoji} {plan.upper()}\n"
            text += f"├ Uses: {used}/{max_uses}\n"
            text += f"├ Created: {created[:10]}\n"
            text += f"└ Expiry: {expiry}\n\n"
        
        bot.reply_to(m, text, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {e}")

@bot.message_handler(commands=['users'])
def users_command(m):
    """List all users"""
    if not is_admin(m.from_user.id):
        bot.reply_to(m, "❌ Admin only!")
        return
    
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT user_id, username, plan, searches_left, expiry_date, join_date FROM users ORDER BY join_date DESC LIMIT 20")
        users = c.fetchall()
        conn.close()
        
        if not users:
            bot.reply_to(m, "📭 No users found.")
            return
        
        text = "📋 **RECENT USERS**\n"
        text += f"{'━'*40}\n\n"
        
        for user in users:
            uid, uname, plan, searches, expiry, joined = user
            username = f"@{uname}" if uname else "No username"
            
            if uid in ADMIN_IDS:
                plan_display = "👑 ADMIN"
            else:
                plan_display = plan.upper() if plan != 'free' else '⚠️ FREE'
            
            text += f"🆔 `{uid}`\n"
            text += f"├ User: {username}\n"
            text += f"├ Plan: {plan_display}\n"
            text += f"├ Searches: {searches}\n"
            text += f"├ Expiry: {expiry if expiry else 'N/A'}\n"
            text += f"└ Joined: {joined[:10]}\n\n"
        
        bot.reply_to(m, text, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {e}")

@bot.message_handler(commands=['stats'])
def stats_command(m):
    """Bot statistics"""
    if not is_admin(m.from_user.id):
        user_id = m.from_user.id
        user_data = get_user_data(user_id)
        
        text = f"📊 **YOUR STATISTICS** 📊\n"
        text += f"{'━'*40}\n\n"
        text += f"👤 **User ID:** `{user_id}`\n"
        text += f"💎 **Plan:** {get_user_plan_display(user_id)['plan_display']}\n"
        text += f"🔍 **Searches Left:** {user_data['searches_left'] if user_data else 0}\n"
        text += f"📊 **Total Used:** {user_data['total_searches'] if user_data else 0}\n"
        
        bot.reply_to(m, text, parse_mode='Markdown')
        return
    
    # Admin stats
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM users WHERE plan != 'free'")
        paid_users = c.fetchone()[0]
        
        c.execute("SELECT SUM(searches_left) FROM users")
        total_searches = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(total_searches) FROM users")
        total_used = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM redeem_codes")
        total_codes = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM redeem_codes WHERE status='active'")
        active_codes = c.fetchone()[0]
        
        c.execute("SELECT SUM(used_count) FROM redeem_codes")
        total_redemptions = c.fetchone()[0] or 0
        
        conn.close()
        
        text = (
            f"📊 **BOT STATISTICS**\n"
            f"{'━'*40}\n\n"
            f"👥 **Users:**\n"
            f"├ Total: {total_users}\n"
            f"├ Paid: {paid_users}\n"
            f"└ Free: {total_users - paid_users}\n\n"
            f"🔍 **Searches:**\n"
            f"├ Available: {total_searches}\n"
            f"├ Used: {total_used}\n"
            f"└ Total: {total_searches + total_used}\n\n"
            f"🎟️ **Codes:**\n"
            f"├ Total: {total_codes}\n"
            f"├ Active: {active_codes}\n"
            f"└ Redeemed: {total_redemptions}"
        )
        
        bot.reply_to(m, text, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {e}")

@bot.message_handler(commands=['broadcast'])
def broadcast_command(m):
    """Broadcast to all users"""
    if not is_admin(m.from_user.id):
        bot.reply_to(m, "❌ Admin only!")
        return
    
    try:
        msg_text = m.text.replace('/broadcast', '', 1).strip()
        if not msg_text:
            bot.reply_to(m, "❌ Usage: `/broadcast Your message`", parse_mode='Markdown')
            return
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        conn.close()
        
        status_msg = bot.reply_to(m, f"📢 Broadcasting to {len(users)} users...")
        
        success = 0
        failed = 0
        
        for user in users:
            try:
                bot.send_message(
                    user[0],
                    f"📢 **BROADCAST**\n\n{msg_text}\n\n- {OWNER_USERNAME}",
                    parse_mode='Markdown'
                )
                success += 1
            except:
                failed += 1
            time.sleep(0.05)
        
        bot.edit_message_text(
            f"✅ **Broadcast Complete!**\n\n"
            f"📊 **Stats:**\n"
            f"├ Total: {len(users)}\n"
            f"├ ✅ Success: {success}\n"
            f"└ ❌ Failed: {failed}",
            status_msg.chat.id,
            status_msg.message_id
        )
        
    except Exception as e:
        bot.reply_to(m, f"❌ Error: {e}")

async def db_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Database statistics with enhanced features"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(f"{COLORS['error']} Admin only!", parse_mode='Markdown')
        return
    
    try:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        
        # User statistics
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM users WHERE plan != 'free'")
        paid_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM users WHERE plan = 'free'")
        free_users = c.fetchone()[0]
        
        # Search statistics
        c.execute("SELECT SUM(searches_left) FROM users")
        total_searches = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(total_searches) FROM users")
        total_used = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM search_history")
        total_searches_logged = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(DISTINCT user_id) FROM search_history")
        active_searchers = c.fetchone()[0] or 0
        
        # Code statistics
        c.execute("SELECT COUNT(*) FROM redeem_codes")
        total_codes = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM redeem_codes WHERE status='active'")
        active_codes = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM redeem_codes WHERE status='deactivated'")
        deactivated_codes = c.fetchone()[0] or 0
        
        c.execute("SELECT SUM(used_count) FROM redeem_codes")
        total_redemptions = c.fetchone()[0] or 0
        
        # Plan distribution
        plan_stats = {}
        for plan in PLANS.keys():
            c.execute("SELECT COUNT(*) FROM users WHERE plan = ?", (plan,))
            plan_stats[plan] = c.fetchone()[0]
        
        # Today's activity
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT COUNT(*) FROM search_history WHERE timestamp LIKE ?", (f"{today}%",))
        today_searches = c.fetchone()[0]
        
        c.execute("SELECT COUNT(DISTINCT user_id) FROM search_history WHERE timestamp LIKE ?", (f"{today}%",))
        today_users = c.fetchone()[0]
        
        conn.close()
        
        # Calculate percentages
        paid_percent = (paid_users / total_users * 100) if total_users > 0 else 0
        redemption_rate = (total_redemptions / total_codes * 100) if total_codes > 0 else 0
        
        # Create progress bars
        def create_bar(value, total, length=10):
            filled = int((value / total) * length) if total > 0 else 0
            return "█" * filled + "░" * (length - filled)
        
        # Format the message
        text = (
            f"📊 **DATABASE MASTER STATS** 📊\n"
            f"{'━'*40}\n\n"
            
            f"👥 **USER STATISTICS**\n"
            f"├ Total Users: `{format_number(total_users)}`\n"
            f"├ ├ Paid: `{format_number(paid_users)}` ({paid_percent:.1f}%)\n"
            f"├ └ Free: `{format_number(free_users)}`\n"
            f"├ Active Today: `{format_number(today_users)}`\n"
            f"└ {create_bar(paid_users, total_users)} Paid/Free\n\n"
            
            f"🔍 **SEARCH STATISTICS**\n"
            f"├ Available: `{format_number(total_searches)}`\n"
            f"├ Used: `{format_number(total_used)}`\n"
            f"├ Logged: `{format_number(total_searches_logged)}`\n"
            f"├ Today: `{format_number(today_searches)}` searches\n"
            f"└ Active Searchers: `{format_number(active_searchers)}`\n\n"
            
            f"🎟️ **CODE STATISTICS**\n"
            f"├ Total Codes: `{format_number(total_codes)}`\n"
            f"├ Active: `{format_number(active_codes)}`\n"
            f"├ Deactivated: `{format_number(deactivated_codes)}`\n"
            f"├ Redeemed: `{format_number(total_redemptions)}`\n"
            f"└ Success Rate: `{redemption_rate:.1f}%`\n"
            f"└ {create_bar(total_redemptions, total_codes)} Redemption\n\n"
            
            f"📋 **PLAN DISTRIBUTION**\n"
        )
        
        # Add plan distribution
        for plan, count in plan_stats.items():
            if count > 0:
                plan_emoji = PLANS.get(plan, {}).get('emoji', '📦')
                percent = (count / total_users * 100) if total_users > 0 else 0
                bar = create_bar(count, total_users, 8)
                text += f"├ {plan_emoji} {plan.title()}: `{count}` ({percent:.1f}%)\n"
                text += f"│  {bar}\n"
        
        text += (
            f"\n{'━'*40}\n"
            f"⏱ **Last Updated:** {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n"
            f"**{get_random_footer()}** 🔥"
        )
        
        # Create inline keyboard for actions
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_db_stats"),
             InlineKeyboardButton("📊 Charts", callback_data="db_charts")],
            [InlineKeyboardButton("📥 Export JSON", callback_data="export_db")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=keyboard)
        
    except Exception as e:
        await update.message.reply_text(f"{COLORS['error']} Error: {str(e)}", parse_mode='Markdown')

async def refresh_db_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refresh database statistics"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text(f"{COLORS['error']} Admin only!", parse_mode='Markdown')
        return
    
    # Re-run db_command
    await db_command(update, context)

async def db_charts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show database charts"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text(f"{COLORS['error']} Admin only!", parse_mode='Markdown')
        return
    
    try:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        
        # Get daily activity for last 7 days
        daily_data = []
        for i in range(6, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            c.execute("SELECT COUNT(*) FROM search_history WHERE timestamp LIKE ?", (f"{date}%",))
            count = c.fetchone()[0]
            daily_data.append((date[-5:], count))  # Show MM-DD
        
        # Get plan distribution
        plan_counts = {}
        for plan in PLANS.keys():
            c.execute("SELECT COUNT(*) FROM users WHERE plan = ?", (plan,))
            plan_counts[plan] = c.fetchone()[0]
        
        conn.close()
        
        # Create chart text
        text = f"📊 **DATABASE CHARTS** 📊\n"
        text += f"{'━'*40}\n\n"
        
        text += f"**📅 Last 7 Days Activity:**\n"
        max_count = max([d[1] for d in daily_data]) or 1
        for date, count in daily_data:
            bar = "█" * int((count / max_count) * 20) if max_count > 0 else ""
            text += f"├ {date}: {bar} `{count}`\n"
        
        text += f"\n**📋 Plan Distribution:**\n"
        total_users = sum(plan_counts.values())
        for plan, count in plan_counts.items():
            if count > 0:
                plan_emoji = PLANS.get(plan, {}).get('emoji', '📦')
                percent = (count / total_users * 100) if total_users > 0 else 0
                bar = "█" * int(percent / 5)  # 20 chars max
                text += f"├ {plan_emoji} {plan.title()}: {bar} `{count}` ({percent:.1f}%)\n"
        
        text += f"\n{get_random_footer()}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Back", callback_data="back_to_db_stats")]
        ])
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)
        
    except Exception as e:
        await query.edit_message_text(f"{COLORS['error']} Error: {str(e)}", parse_mode='Markdown')

async def export_db_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export database as JSON"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text(f"{COLORS['error']} Admin only!", parse_mode='Markdown')
        return
    
    try:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        
        # Export users
        c.execute("SELECT * FROM users")
        users = c.fetchall()
        user_columns = [description[0] for description in c.description]
        users_list = [dict(zip(user_columns, user)) for user in users]
        
        # Export codes
        c.execute("SELECT * FROM redeem_codes")
        codes = c.fetchall()
        code_columns = [description[0] for description in c.description]
        codes_list = [dict(zip(code_columns, code)) for code in codes]
        
        # Export history
        c.execute("SELECT * FROM search_history ORDER BY timestamp DESC LIMIT 1000")
        history = c.fetchall()
        history_columns = [description[0] for description in c.description]
        history_list = [dict(zip(history_columns, h)) for h in history]
        
        conn.close()
        
        export_data = {
            "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "statistics": {
                "total_users": len(users_list),
                "total_codes": len(codes_list),
                "total_searches": len(history_list)
            },
            "users": users_list,
            "codes": codes_list,
            "recent_searches": history_list[:100]
        }
        
        # Create JSON file
        json_str = json.dumps(export_data, indent=2, ensure_ascii=False, default=str)
        file_bytes = BytesIO(json_str.encode('utf-8'))
        file_bytes.name = f"db_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        await query.edit_message_text("📥 Exporting database...")
        await context.bot.send_document(
            chat_id=query.from_user.id,
            document=file_bytes,
            caption=f"📊 Database Export\n🕒 {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}"
        )
        
        # Go back to stats
        await db_command(update, context)
        
    except Exception as e:
        await query.edit_message_text(f"{COLORS['error']} Error: {str(e)}", parse_mode='Markdown')
# -------------------- MAIN --------------------
def main():
    """Start bot"""
    init_db()
    
    print("🔥" + "="*60 + "🔥")
    print("      ULTIMATE OSINT BOT - PREMIUM EDITION v2.0")
    print("🔥" + "="*60 + "🔥")
    print(f"👑 Owner: {OWNER_USERNAME}")
    print(f"👨‍💻 Developer: {DEV_NAME}")
    print(f"🆔 Admin IDs: {ADMIN_IDS}")
    print(f"💎 Redeem System: ✅ ACTIVE")
    print(f"📋 Navigation Buttons: ✅ ACTIVE")
    print(f"📥 Download JSON: ✅ ACTIVE")
    print(f"📊 Statistics: ✅ ACTIVE")
    print(f"📱 Search History: ✅ ACTIVE")
    print(f"🎨 UI Enhancements: ✅ ACTIVE")
    print(f"📊 Database Charts: ✅ ACTIVE")
    print(f"📤 Export Database: ✅ ACTIVE")
    print(f"🔄 Live Refresh: ✅ ACTIVE")
    print(f"📡 Bot Starting...")
    print("🔥" + "="*60 + "🔥")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("redeem", redeem_command))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(CommandHandler("plans", plans_command))
    app.add_handler(CommandHandler("tg", tg_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("stats", stats_command))
    
    # Admin commands
    app.add_handler(CommandHandler("gen", gen_command))
    app.add_handler(CommandHandler("codes", codes_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("db", db_command))
    
    # Callback handlers for db stats
    app.add_handler(CallbackQueryHandler(refresh_db_stats_callback, pattern="^refresh_db_stats$"))
    app.add_handler(CallbackQueryHandler(db_charts_callback, pattern="^db_charts$"))
    app.add_handler(CallbackQueryHandler(export_db_callback, pattern="^export_db$"))
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Callback handler for other buttons
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Error handler
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Error: {context.error}")
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    f"{COLORS['error']} Error! Contact {OWNER_USERNAME}",
                    parse_mode='Markdown'
                )
        except:
            pass
    
    app.add_error_handler(error_handler)
    
    print("✅ Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()