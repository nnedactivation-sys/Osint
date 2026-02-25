import telebot
import requests
import re
import json
import sqlite3
import time
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

# --- BOT TOKEN ---
BOT_TOKEN = "7502160881:AAHei74Yc2Q3tCuJnOaj4SMA5Fciyoi1uC4"
ADMIN_ID = 8085855107
bot = telebot.TeleBot(BOT_TOKEN)

# --- API CONFIG ---
NUMBER_API = "https://source-code-api.vercel.app/?num="
VEHICLE_API = "https://vehicle-info-aco-api.vercel.app/info?vehicle="
IFSC_API = "https://ifsc.razorpay.com/"

FREE_CREDITS = 3
DAILY_BONUS = 1
DAY = 24 * 60 * 60

# --- USERS DATABASE ---
conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
user_id INTEGER PRIMARY KEY,
credits INTEGER,
last_bonus INTEGER,
last_active INTEGER
)
""")
conn.commit()

# --- KEYBOARD LAYOUTS ---
USER_KEYBOARD_LAYOUT = [
["📱 Phone"],
["🚗 Vehicle", "🏦 IFSC"],
["💳 My Credit", "🎁 Daily Bonus", "💳 Buy Credit"]
]

ADMIN_KEYBOARD_LAYOUT = [
["📱 Phone"],
["🚗 Vehicle", "🏦 IFSC"],
["📊 Statistics", "📢 Broadcast", "➕ Add Credit"]
]

# --- KEYBOARDS FUNCTION ---
def user_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for row in USER_KEYBOARD_LAYOUT:
        kb.row(*row)
    return kb

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for row in ADMIN_KEYBOARD_LAYOUT:
        kb.row(*row)
    return kb

def get_user(uid):
    cur = conn.cursor()
    return cur.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()

def get_total_users():
    cur = conn.cursor()
    return cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]

def is_admin(uid):
    return uid == ADMIN_ID

def deduct(uid):
    if uid == ADMIN_ID:
        return True
    cur = conn.cursor()
    cur.execute("SELECT credits FROM users WHERE user_id=?", (uid,))
    user = cur.fetchone()
    
    if user and user[0] > 0:
        cur.execute("UPDATE users SET credits=credits-1 WHERE user_id=?", (uid,))
        conn.commit()
        return True
    return False

def get_credits_remaining(uid):
    if is_admin(uid):
        return "∞"
    user = get_user(uid)
    if user:
        return str(user[1])
    return "0"

# Global variable for broadcast
broadcast_message = None

# --- START COMMAND ---
@bot.message_handler(commands=["start"])
def start(m):
    uid = m.from_user.id
    name = f"{m.from_user.first_name or ''} {m.from_user.last_name or ''}".strip()

    if not get_user(uid):  
        cur = conn.cursor()
        cur.execute("INSERT INTO users VALUES (?, ?, ?, ?)",  
                    (uid, FREE_CREDITS, 0, int(time.time())))  
        conn.commit()  
          
        # 🔔 ADMIN NOTIFICATION FOR NEW USER  
        bot.send_message(  
            ADMIN_ID,  
            "*🆕 New User Joined*\n\n"  
            f"👤 Name: {name}\n"  
            f"🆔 ID: `{uid}`\n"  
            f"🎁 Free Credits: {FREE_CREDITS}",  
            parse_mode="Markdown"  
        )  

    cur = conn.cursor()
    cur.execute("UPDATE users SET last_active=? WHERE user_id=?",  
                (int(time.time()), uid))  
    conn.commit()  

    bot.send_message(  
        uid,  
        f"👋 *Welcome {name}!*\n\n"  
        "📱 *OSINT Search Bot*\n\n"  
        "*Available Tools:*\n"  
        "• 📱 Phone Number Lookup\n"  
        "• 🚗 Vehicle Information\n"  
        "• 🏦 IFSC Code Search\n\n"  
        "Select an option from the menu below:",  
        parse_mode="Markdown",  
        reply_markup=admin_kb() if uid == ADMIN_ID else user_kb()  
    )

# --- MY CREDIT ---
@bot.message_handler(func=lambda m: m.text == "💳 My Credit")
def my_credit(m):
    user = get_user(m.from_user.id)
    if user:
        credits_display = "∞" if is_admin(m.from_user.id) else str(user[1])
        bot.send_message(
            m.chat.id,
            f"💳 *My Credit*\n\n*🪙 Available Credits:* {credits_display}",
            parse_mode="Markdown"
        )

# --- BUY CREDIT ---
@bot.message_handler(func=lambda m: m.text == "💳 Buy Credit")
def buy_credit(m):
    bot.send_message(
        m.chat.id,
        "💳 *VIP CREDITS STORE*\n\n" +
        "📊 *Credit Pricing:*\n" + 
        "• 💎 10 Credits – ₹15\n" +
        "• 💎 30 Credits – ₹45\n" +
        "• 💎 50 Credits – ₹75\n" +
        "• 💎 70 Credits – ₹105\n\n" +
        "💸 *Payment Options:*\n" +
        "• UPI • Paytm • PhonePe\n\n" +
        "📩 *Contact owner for payment:*\n" +
        "@DMcredit",
        parse_mode="Markdown"
    )

# --- PHONE LOOKUP ---
@bot.message_handler(func=lambda m: m.text == "📱 Phone")
def phone(m):
    bot.send_message(m.chat.id,
    "📱 *Enter Phone Number*\n💡`6395954711`",
    parse_mode="Markdown")
    bot.register_next_step_handler(m, phone_lookup)

def phone_lookup(m):
    chat_id = m.chat.id
    user_id = m.from_user.id
    mobile = m.text.strip()

    if mobile == "/start":    
        start(m)  
        return    
      
    # Check credits
    if not is_admin(user_id):
        user = get_user(user_id)
        if not user or user[1] <= 0:
            bot.send_message(
                chat_id,
                "*❌ No Credits Left*",
                parse_mode="Markdown",
                reply_markup=user_kb()
            )
            return
    
    # --- NUMBER VALIDATION ---  
    PHONE_PATTERN = r'^[0-9]{10}$'  
    if not re.match(PHONE_PATTERN, mobile):    
        bot.send_message(  
            chat_id,  
            "*❌ Invalid Phone Number*",  
            reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
            parse_mode='Markdown'  
        )  
        return    
      
    processing_msg = bot.send_message(  
        chat_id,  
        "*🔄 Processing Your Request...*\n"  
        "*📱 Searching phone database...*\n\n"  
        "*⏳ Please wait...*",   
        parse_mode='Markdown'  
    )  
      
    try:    
        response = requests.get(NUMBER_API + mobile, timeout=15)  
        bot.delete_message(chat_id, processing_msg.message_id)  
          
        if response.status_code == 200:    
            data = response.json()    
              
            if data and isinstance(data, dict):  
                # Deduct credit
                if not deduct(user_id):
                    bot.send_message(
                        chat_id,
                        "*❌ No Credits Left*",
                        parse_mode="Markdown",
                        reply_markup=user_kb()
                    )
                    return
                
                # Get remaining credits
                credits_left = get_credits_remaining(user_id)
                
                # Format JSON response nicely
                json_formatted = json.dumps(data, indent=2, ensure_ascii=False)
                
                result_text = f"```json\n{json_formatted}\n```*💳 Credits Left: {credits_left}*"
                
                bot.send_message(  
                    chat_id,  
                    result_text,
                    reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
                    parse_mode='Markdown'  
                )  
            else:  
                bot.send_message(  
                    chat_id,  
                    "*❌ No data found for this number*",  
                    reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
                    parse_mode='Markdown'  
                )  
                    
        else:    
            bot.send_message(  
                chat_id,  
                f"*❌ API Error (Status: {response.status_code})*",  
                reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
                parse_mode='Markdown'  
            )    
    except requests.exceptions.Timeout:    
        bot.send_message(  
            chat_id,  
            "*❌ Request Timeout*\n\n"  
            "*⚠️ The phone API is taking too long to respond.*",  
            reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
            parse_mode='Markdown'  
        )  
    except Exception as e:    
        error_text = f"*❌ Lookup Failed*\n\n*⚠️ Error:* {str(e)}"    
        bot.send_message(  
            chat_id,  
            error_text,  
            reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
            parse_mode='Markdown'  
        )

# --- VEHICLE LOOKUP ---
@bot.message_handler(func=lambda m: m.text == "🚗 Vehicle")
def vehicle(m):
    bot.send_message(m.chat.id,
    "🚗 *Enter Vehicle Number*\n💡`DL10CA7539`",
    parse_mode="Markdown")
    bot.register_next_step_handler(m, vehicle_lookup)

def vehicle_lookup(m):
    chat_id = m.chat.id
    user_id = m.from_user.id
    vehicle_num = m.text.strip().upper()

    if vehicle_num == "/start":    
        start(m)  
        return    
      
    # Check credits
    if not is_admin(user_id):
        user = get_user(user_id)
        if not user or user[1] <= 0:
            bot.send_message(
                chat_id,
                "*❌ No Credits Left*",
                parse_mode="Markdown",
                reply_markup=user_kb()
            )
            return
    
    # --- VEHICLE VALIDATION ---  
    VEHICLE_PATTERN = r'^[A-Z]{2}[0-9]{1,2}[A-Z]{1,2}[0-9]{4}$'  
    if not re.match(VEHICLE_PATTERN, vehicle_num):    
        bot.send_message(  
            chat_id,  
            "*❌ Invalid Vehicle Number*",  
            reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
            parse_mode='Markdown'  
        )  
        return    
      
    processing_msg = bot.send_message(  
        chat_id,  
        "*🔄 Processing Your Request...*\n"  
        "*🚗 Searching vehicle database...*\n\n"  
        "*⏳ Please wait...*",   
        parse_mode='Markdown'  
    )  
      
    try:    
        response = requests.get(VEHICLE_API + vehicle_num, timeout=15)  
        bot.delete_message(chat_id, processing_msg.message_id)  
          
        if response.status_code == 200:    
            data = response.json()    
              
            if data and isinstance(data, dict):  
                # Deduct credit
                if not deduct(user_id):
                    bot.send_message(
                        chat_id,
                        "*❌ No Credits Left*",
                        parse_mode="Markdown",
                        reply_markup=user_kb()
                    )
                    return
                
                # Get remaining credits
                credits_left = get_credits_remaining(user_id)
                
                # Format JSON response nicely
                json_formatted = json.dumps(data, indent=2, ensure_ascii=False)
                
                result_text = f"```json\n{json_formatted}\n```*💳 Credits Left: {credits_left}*"
                
                bot.send_message(  
                    chat_id,  
                    result_text,
                    reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
                    parse_mode='Markdown'  
                )  
            else:  
                bot.send_message(  
                    chat_id,  
                    "*❌ No data found for this vehicle*",  
                    reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
                    parse_mode='Markdown'  
                )  
                    
        else:    
            bot.send_message(  
                chat_id,  
                f"*❌ API Error (Status: {response.status_code})*",  
                reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
                parse_mode='Markdown'  
            )    
    except requests.exceptions.Timeout:    
        bot.send_message(  
            chat_id,  
            "*❌ Request Timeout*\n\n"  
            "*⚠️ The vehicle API is taking too long to respond.*",  
            reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
            parse_mode='Markdown'  
        )  
    except Exception as e:    
        error_text = f"*❌ Lookup Failed*\n\n*⚠️ Error:* {str(e)}"    
        bot.send_message(  
            chat_id,  
            error_text,  
            reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
            parse_mode='Markdown'  
        )

# --- IFSC LOOKUP ---
@bot.message_handler(func=lambda m: m.text == "🏦 IFSC")
def ifsc(m):
    bot.send_message(m.chat.id,
    "🏦 *Enter IFSC Number*\n💡`SBIN0001111`",
    parse_mode="Markdown")
    bot.register_next_step_handler(m, ifsc_lookup)

def ifsc_lookup(m):
    chat_id = m.chat.id
    user_id = m.from_user.id
    ifsc_code = m.text.strip().upper()

    if ifsc_code == "/start":    
        start(m)  
        return    
      
    # Check credits
    if not is_admin(user_id):
        user = get_user(user_id)
        if not user or user[1] <= 0:
            bot.send_message(
                chat_id,
                "*❌ No Credits Left*",
                parse_mode="Markdown",
                reply_markup=user_kb()
            )
            return
    
    # --- IFSC VALIDATION ---  
    IFSC_PATTERN = r'^[A-Z]{4}0[A-Z0-9]{6}$'  
    if not re.match(IFSC_PATTERN, ifsc_code):    
        bot.send_message(  
            chat_id,  
            "*❌ Invalid IFSC Code*",  
            reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
            parse_mode='Markdown'  
        )  
        return    
      
    processing_msg = bot.send_message(  
        chat_id,  
        "*🔄 Processing Your Request...*\n"  
        "*🏦 Searching IFSC database...*\n\n"  
        "*⏳ Please wait...*",   
        parse_mode='Markdown'  
    )  
      
    try:    
        response = requests.get(IFSC_API + ifsc_code, timeout=15)  
        bot.delete_message(chat_id, processing_msg.message_id)  
          
        if response.status_code == 200:    
            data = response.json()    
              
            if data and isinstance(data, dict):  
                # Deduct credit
                if not deduct(user_id):
                    bot.send_message(
                        chat_id,
                        "*❌ No Credits Left*",
                        parse_mode="Markdown",
                        reply_markup=user_kb()
                    )
                    return
                
                # Get remaining credits
                credits_left = get_credits_remaining(user_id)
                
                # Format JSON response nicely
                json_formatted = json.dumps(data, indent=2, ensure_ascii=False)
                
                result_text = f"```json\n{json_formatted}\n```*💳 Credits Left: {credits_left}*"
                
                bot.send_message(  
                    chat_id,  
                    result_text,
                    reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
                    parse_mode='Markdown'  
                )  
            else:  
                bot.send_message(  
                    chat_id,  
                    "*❌ No data found for this IFSC code*",  
                    reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
                    parse_mode='Markdown'  
                )  
                    
        else:    
            bot.send_message(  
                chat_id,  
                f"*❌ API Error (Status: {response.status_code})*",  
                reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
                parse_mode='Markdown'  
            )    
    except requests.exceptions.Timeout:    
        bot.send_message(  
            chat_id,  
            "*❌ Request Timeout*\n\n"  
            "*⚠️ The IFSC API is taking too long to respond.*",  
            reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
            parse_mode='Markdown'  
        )  
    except Exception as e:    
        error_text = f"*❌ Lookup Failed*\n\n*⚠️ Error:* {str(e)}"    
        bot.send_message(  
            chat_id,  
            error_text,  
            reply_markup=admin_kb() if is_admin(user_id) else user_kb(),  
            parse_mode='Markdown'  
        )

# --- DAILY BONUS ---
@bot.message_handler(func=lambda m: m.text == "🎁 Daily Bonus")
def daily_bonus(m):
    user = get_user(m.from_user.id)
    now = int(time.time())

    if now - user[2] < DAY:  
        left = DAY - (now - user[2])  
        h = left // 3600  
        mnt = (left % 3600) // 60  
        s = left % 60  
        bot.send_message(  
            m.chat.id,  
            f"*⏳ Bonus already claimed*\n\n*🕒 Time remaining:*\n{h} h {mnt} m {s} s",  
            parse_mode="Markdown"  
        )  
        return  

    cur = conn.cursor()
    cur.execute(  
        "UPDATE users SET credits=credits+?, last_bonus=? WHERE user_id=?",  
        (DAILY_BONUS, now, m.from_user.id)  
    )  
    conn.commit()  

    bot.send_message(  
        m.chat.id,  
        f"*🎉 Daily Bonus Claimed!*\n\n*➕ +{DAILY_BONUS} Credit*",  
        parse_mode="Markdown"  
    )

# --- USERS STATISTICS 12-HOUR TIME ---
@bot.message_handler(func=lambda m: m.text == "📊 Statistics")
def stats(m):
    if not is_admin(m.from_user.id):
        return
    now = int(time.time())
    cur = conn.cursor()
    rows = cur.execute("SELECT last_active FROM users").fetchall()
    a7 = sum(1 for r in rows if now - r[0] <= 7 * DAY)
    a30 = sum(1 for r in rows if now - r[0] <= 30 * DAY)
    
    dt = datetime.fromtimestamp(now)
    formattedTime = dt.strftime("%d/%m/%Y | %I:%M %p")

    bot.send_message(  
        m.chat.id,  
        "<b>📊 Bot Live Statistics 📊</b>\n\n" +
        "<b>👥 Total Users: " + str(len(rows)) + "</b>\n\n" +
        "<b>🔥 Active Users</b>\n" +
        "<b>• Last 7 Days: " + str(a7) + "</b>\n" +
        "<b>• Last 30 Days: " + str(a30) + "</b>\n\n" +
        "<b>🕒 " + formattedTime + "</b>",  
        parse_mode="HTML"  
    )

# --- BROADCAST SYSTEM ---
@bot.message_handler(func=lambda m: m.text == "📢 Broadcast")
def admin_broadcast_cmd(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "🚫 You are not authorized to use this command.", parse_mode="Markdown")
        return

    bot.send_message(m.chat.id,   
                     "*📢 Broadcast Message*\n\n"  
                     "*Send Message broadcast:*",  
                     parse_mode='Markdown')  
    bot.register_next_step_handler(m, receive_broadcast_content)

def receive_broadcast_content(m):
    global broadcast_message

    if not is_admin(m.from_user.id):   
        return bot.send_message(m.chat.id, "*🚫 You are not authorized.*", parse_mode="Markdown")  

    broadcast_message = m  

    kb = InlineKeyboardMarkup(row_width=2)  
    kb.add(  
        InlineKeyboardButton("✅ Confirm", callback_data="broadcast_confirm"),  
        InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")  
    )  

    bot.send_message(m.chat.id,   
                 "*⚠️ Broadcast Confirmation*\n\n"  
                 "*Are you sure you want to send this message to ALL users?*\n\n"  
                 f"*📊 Total users:* {get_total_users()}",  
                 reply_markup=kb,   
                 parse_mode='Markdown')

@bot.callback_query_handler(func=lambda c: c.data in ["broadcast_confirm", "broadcast_cancel"])
def process_broadcast_callback(c):
    global broadcast_message

    if not is_admin(c.from_user.id):   
        return bot.answer_callback_query(c.id, "*🚫 Unauthorized*", show_alert=True)  

    if c.data == "broadcast_cancel":  
        broadcast_message = None  
        bot.answer_callback_query(c.id, "❌ Broadcast cancelled")  
        bot.edit_message_text("*❌ Broadcast cancelled.*", c.message.chat.id, c.message.message_id, parse_mode="Markdown")  
        return  

    bot.edit_message_text("*🔄 Broadcasting to all users...*\n*Please wait...*",   
                          c.message.chat.id, c.message.message_id, parse_mode="Markdown")  
    bot.answer_callback_query(c.id, "📢 Broadcasting started...")  

    cur = conn.cursor()  
    cur.execute("SELECT user_id FROM users")  
    users = cur.fetchall()  

    sent = 0  
    failed = 0  
    total = len(users)  

    for (uid,) in users:  
        try:  
            bot.copy_message(uid, broadcast_message.chat.id, broadcast_message.message_id)  
            sent += 1  
            time.sleep(0.05)  
        except Exception as e:  
            print(f"Failed to send to {uid}: {e}")  
            failed += 1  

    bot.edit_message_text(  
        f"*✅ Broadcast Completed!*\n\n"  
        f"*✅ Sent:* {sent} users\n"  
        f"*❌ Failed:* {failed} users\n"  
        f"*📊 Total:* {total} users",   
        c.message.chat.id,   
        c.message.message_id,  
        parse_mode='Markdown'  
    )  
      
    broadcast_message = None

# --- ADD CREDIT (WITH USER NOTIFICATION FOR BOTH ADD AND REMOVE - NO ERROR MESSAGES) ---
@bot.message_handler(func=lambda m: m.text == "➕ Add Credit")
def add_credit_cmd(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "*🚫 You are not authorized.*", parse_mode="Markdown")
        return
        
    bot.send_message(
        m.chat.id,
        "➕ *Add Credits to Users*\n\n"
        "*Send in format:*\n\n"
        "`USER_ID CREDITS`\n\n"
        "*Examples:*\n"
        "`123456789 10`\n"
        "`123456789 -5`",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(m, add_credit)

def add_credit(m):
    # /start command check
    if m.text == "/start":
        start(m)
        return

    try:  
        # Split and validate
        parts = m.text.strip().split()  
          
        # Exactly 2 parts required
        if len(parts) != 2:  
            bot.send_message(
                m.chat.id,
                "*❌ Invalid format!*\n\nUse: `USER_ID CREDITS`",
                parse_mode="Markdown"
            )
            return
          
        uid = int(parts[0])
        amt = int(parts[1])
        
        # Check if user exists
        cur = conn.cursor()
        user = cur.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        
        if not user:  
            # Create new user with credits (allow negative? better to set to amt if positive, else 0)
            if amt < 0:
                # For negative amounts on non-existent users, just create with 0 credits
                cur.execute("INSERT INTO users VALUES (?, ?, ?, ?)",  
                           (uid, 0, 0, int(time.time())))  
                conn.commit()  
                total = 0
                action = f"Remove {abs(amt)} Credits User Not Found 🚫"
            else:
                cur.execute("INSERT INTO users VALUES (?, ?, ?, ?)",  
                           (uid, amt, 0, int(time.time())))  
                conn.commit()  
                total = amt
                action = f"Added {amt} Credits"
            
        else:  
            # Add or remove credits
            current_credits = user[1]
            new_credits = current_credits + amt
            
            # Prevent negative credits
            if new_credits < 0:
                new_credits = 0
                amt = -current_credits  # Adjust amt to reflect actual change
            
            cur.execute("UPDATE users SET credits=? WHERE user_id=?", (new_credits, uid))  
            conn.commit()  
            total = new_credits
            
            if amt > 0:
                action = f"Added {amt} credits"
            elif amt < 0:
                action = f"Remove {abs(amt)} credits"
            else:
                action = "No change (0 credits)"
        
        # Admin confirmation
        bot.send_message(  
            m.chat.id,  
            f"*✅ Credits Updated Successfully!*\n\n"  
            f"*👤 User ID:* `{uid}`\n"  
            f"*🔄 Action:* {action}\n"  
            f"*💰 Total Credits:* {total}",  
            parse_mode="Markdown"  
        )
        
        # Send notification to user for BOTH add and remove (only if user exists and we have a valid change)
        if user and amt > 0:
            try:
                bot.send_message(
                    uid,
                    f"*🎁 Credits Added!*\n\n"
                    f"*➕ +{amt} Credits have been added to your account*\n"
                    f"*💰 Total Credits:* {total}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Failed to notify user {uid}: {e}")
        elif user and amt < 0:
            try:
                bot.send_message(
                    uid,
                    f"*⚠️ Credits Removed!*\n\n"
                    f"*➖ {abs(amt)} Credits have been removed from your account*\n"
                    f"*💰 Total Credits:* {total}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Failed to notify user {uid}: {e}")
        
    except ValueError:  
        bot.send_message(
            m.chat.id, 
            "*❌ Invalid format!*\n\nUse: `USER_ID CREDITS`", 
            parse_mode="Markdown"
        )  
    except Exception as e:  
        bot.send_message(m.chat.id, f"*❌ Error:* {str(e)}", parse_mode="Markdown")

# --- MAIN EXTENSION ---
if __name__ == "__main__":
    print("🚀 OSINT Bot Started")
    print("⚡ Bot is ready...")
    bot.infinity_polling()