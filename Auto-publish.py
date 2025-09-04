# إصلاح لمشكلة imghdr في Python 3.13
import sys
try:
    import imghdr
except ModuleNotFoundError:
    # إنشاء بديل لـ imghdr
    class SimpleImghdr:
        def what(self, filename):
            if isinstance(filename, str):
                if filename.endswith(('.jpg', '.jpeg')):
                    return 'jpeg'
                elif filename.endswith('.png'):
                    return 'png'
                elif filename.endswith('.gif'):
                    return 'gif'
                elif filename.endswith('.bmp'):
                    return 'bmp'
                elif filename.endswith('.webp'):
                    return 'webp'
            return None
    sys.modules['imghdr'] = SimpleImghdr()
    import imghdr

# الآن استورد باقي المكتبات
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneNumberInvalidError
from telethon.sync import TelegramClient
import asyncio
import os
import json
import threading
import time
from datetime import datetime, timedelta

# إعداد Flask app
app = Flask(__name__)

# إعدادات البوت
api_id = 25217515
api_hash = "1bb27e5be73593e33fc735c1fbe0d855"
token = "8438319213:AAEoJq5V2aexlllC7z6KxqI-piW6jj6tRHY"

# تعريف المطور
DEVELOPER_ID = 7115002714
DEVELOPER_USERNAME = "@I_e_e_l"

# قناة الاشتراك الإجباري
CHANNEL_USERNAME = "@Scorpion_scorp"
CHANNEL_LINK = "https://t.me/Scorpion_scorp"

users_file = "users.json"
subscriptions_file = "subscriptions.json"

# إنشاء event loop رئيسي
main_loop = asyncio.new_event_loop()
asyncio.set_event_loop(main_loop)

clients = {}
user_states = {}  # لتتبع حالة المستخدم
admin_states = {}  # لتتبع حالة المطور
posting_status = {}  # لتتبع حالة النشر لكل مستخدم

bot = telebot.TeleBot(token)

# تحميل وتخزين الاشتراكات
def load_subscriptions():
    if not os.path.exists(subscriptions_file):
        with open(subscriptions_file, "w") as f:
            json.dump({}, f)
    with open(subscriptions_file, "r") as f:
        return json.load(f)

def save_subscriptions(subscriptions):
    with open(subscriptions_file, "w") as f:
        json.dump(subscriptions, f, indent=2)

# حساب الوقت المتبقي للاشتراك
def get_remaining_time(expiry_date_str):
    expiry_date = datetime.fromisoformat(expiry_date_str)
    now = datetime.now()
    
    if now >= expiry_date:
        return "⛔️ منتهي"
    
    remaining = expiry_date - now
    days = remaining.days
    hours = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60
    
    return f"⏳ {days} يوم و {hours} ساعة و {minutes} دقيقة"

# التحقق من صلاحية الاشتراك
def check_subscription(user_id):
    subscriptions = load_subscriptions()
    user_id_str = str(user_id)
    
    if user_id_str not in subscriptions:
        return False, None
    
    expiry_date = datetime.fromisoformat(subscriptions[user_id_str]["expiry_date"])
    return datetime.now() < expiry_date, subscriptions[user_id_str]

# التحقق من اشتراك المستخدم في القناة - الطريقة البديلة
def check_channel_subscription(user_id):
    try:
        # محاولة استخدام get_chat_member
        chat_member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"خطأ في التحقق من الاشتراك: {e}")
        # إذا فشل التحقق، نطلب من المستخدم الضغط على زر التحقق
        return False

# وظيفة لفحص الاشتراكات تلقائياً
def check_subscriptions_periodically():
    while True:
        time.sleep(86400)  # الانتظار 24 ساعة
        subscriptions = load_subscriptions()
        now = datetime.now()
        
        expired_users = []
        for user_id, data in subscriptions.items():
            expiry_date = datetime.fromisoformat(data["expiry_date"])
            if now >= expiry_date:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del subscriptions[user_id]
        
        save_subscriptions(subscriptions)
        print("✅ تم فحص الاشتراكات وإزالة المنتهية")

# بدء فحص الاشتراكات في خلفية
subscription_thread = threading.Thread(target=check_subscriptions_periodically, daemon=True)
subscription_thread.start()

def load_users():
    if not os.path.exists(users_file):
        with open(users_file, "w") as f:
            json.dump({}, f)
    with open(users_file, "r") as f:
        return json.load(f)

def save_users(users):
    with open(users_file, "w") as f:
        json.dump(users, f, indent=2)

def ensure_user(users, user_id):
    if user_id not in users:
        users[user_id] = {"settings": {}, "sessions": {}, "selected_groups": []}

def create_client(session_str=None):
    return TelegramClient(
        StringSession(session_str) if session_str else StringSession(),
        api_id=api_id,
        api_hash=api_hash,
        device_model="iPad 9",
        loop=main_loop
    )

# التحقق من الاشتراك في القناة قبل أي أمر
def check_channel_subscription_decorator(func):
    def wrapper(message):
        user_id = message.from_user.id
        
        # لا تطبق على المطور
        if user_id == DEVELOPER_ID:
            return func(message)
            
        # التحقق من الاشتراك في القناة
        if not check_channel_subscription(user_id):
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(text="📢 انضم للقناة أولاً", url=CHANNEL_LINK))
            markup.add(InlineKeyboardButton(text="✅ تحقق من الاشتراك", callback_data="check_subscription"))
            
            bot.send_message(
                message.chat.id,
                f"⛔️ يجب عليك الانضمام إلى قناتنا أولاً:\n{CHANNEL_USERNAME}",
                reply_markup=markup,
                parse_mode="html"
            )
            return
        
        # التحقق من الاشتراك في البوت
        is_subscribed, sub_data = check_subscription(user_id)
        if not is_subscribed:
            bot.send_message(message.chat.id, f"⛔️ عذراً، يجب عليك الاشتراك لاستخدام البوت.\n📞 راسل المطور {DEVELOPER_USERNAME} للاشتراك.")
            return
            
        return func(message)
    return wrapper

# التحقق من الاشتراك للـ callbacks
def check_channel_subscription_callback(func):
    def wrapper(call):
        user_id = call.from_user.id
        
        # لا تطبق على المطور
        if user_id == DEVELOPER_ID:
            return func(call)
            
        # التحقق من الاشتراك في القناة
        if not check_channel_subscription(user_id):
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(text="📢 انضم للقناة أولاً", url=CHANNEL_LINK))
            markup.add(InlineKeyboardButton(text="✅ تحقق من الاشتراك", callback_data="check_subscription"))
            
            bot.edit_message_text(
                f"⛔️ يجب عليك الانضمام إلى قناتنا أولاً:\n{CHANNEL_USERNAME}",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="html"
            )
            return
        
        # التحقق من الاشتراك في البوت
        is_subscribed, sub_data = check_subscription(user_id)
        if not is_subscribed:
            bot.answer_callback_query(call.id, "⛔️ اشتراكك منتهي، راسل المطور", show_alert=True)
            return
            
        return func(call)
    return wrapper

# زر التحقق من الاشتراك
@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription_callback(call):
    user_id = call.from_user.id
    
    if check_channel_subscription(user_id):
        # إذا كان مشترك، إعادة تحميل القائمة الرئيسية
        bot.answer_callback_query(call.id, "✅ تم التحقق من الاشتراك بنجاح")
        start_from_callback(call)
    else:
        bot.answer_callback_query(call.id, "❌ لم تنضم بعد إلى القناة", show_alert=True)

# بدء من callback للاستخدام بعد التحقق
def start_from_callback(call):
    user_id = str(call.from_user.id)
    
    users = load_users()
    ensure_user(users, user_id)
    save_users(users)
    
    # عرض معلومات الاشتراك
    is_subscribed, sub_data = check_subscription(user_id)
    expiry_date = datetime.fromisoformat(sub_data["expiry_date"]) if sub_data else None
    
    if is_subscribed and expiry_date:
        remaining_time = get_remaining_time(sub_data["expiry_date"])
        subscription_info = f"""
✅ <strong>اشتراكك ({sub_data['days']} يوم) فعال حتى:</strong>
<code>{expiry_date.strftime('%Y-%m-%d %H:%M:%S')}</code>

{remaining_time}
        """
    else:
        subscription_info = "⛔️ <strong>لا يوجد اشتراك فعال</strong>"
    
    markup = InlineKeyboardMarkup(row_width=2)
    
    # الأزرار الرئيسية
    markup.add(
        InlineKeyboardButton(text="👤 إدارة الحسابات", callback_data="account_management"),
        InlineKeyboardButton(text="📢 إدارة النشر", callback_data="post_management"),
        InlineKeyboardButton(text="👥 إدارة المجموعات", callback_data="group_management"),
        InlineKeyboardButton(text="ℹ️ معلومات الاشتراك", callback_data="subscription_info")
    )
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"<strong>مرحباً بك في بوت النشر التلقائي للتليجرام 👋</strong>\n\n{subscription_info}",
        reply_markup=markup,
        parse_mode="html"
    )

# أمر /ad لإدارة الاشتراكات (للمطور فقط)
@bot.message_handler(commands=["ad"])
def ad_command(message):
    user_id = str(message.from_user.id)
    
    # التحقق إذا كان المستخدم هو المطور
    if int(user_id) != DEVELOPER_ID:
        bot.send_message(message.chat.id, "⛔️ هذا الأمر متاح للمطور فقط.")
        return
    
    # تعيين حالة المطور
    admin_states[user_id] = "awaiting_ad_command"
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(text="➕ إضافة اشتراك", callback_data="admin_add_sub"),
        InlineKeyboardButton(text="🗑️ حذف اشتراك", callback_data="admin_remove_sub"),
        InlineKeyboardButton(text="📋 قائمة المشتركين", callback_data="admin_list_subs"),
        InlineKeyboardButton(text="🔙 إلغاء", callback_data="admin_cancel")
    )
    
    bot.send_message(message.chat.id, "👑 <strong>لوحة إدارة الاشتراكات</strong>\n\nاختر الإجراء المطلوب:", reply_markup=markup, parse_mode="html")

# معالجة أزرار إدارة الاشتراكات
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def handle_admin_buttons(call):
    user_id = str(call.from_user.id)
    
    # التحقق إذا كان المستخدم هو المطور
    if int(user_id) != DEVELOPER_ID:
        bot.answer_callback_query(call.id, "⛔️ هذا الأمر متاح للمطور فقط.")
        return
    
    if call.data == "admin_add_sub":
        admin_states[user_id] = "awaiting_user_id"
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="👤 <strong>إضافة اشتراك جديد</strong>\n\nأرسل ايدي المستخدم:",
            parse_mode="html"
        )
    
    elif call.data == "admin_remove_sub":
        admin_states[user_id] = "awaiting_remove_id"
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🗑️ <strong>حذف اشتراك</strong>\n\nأرسل ايدي المستخدم لحذف اشتراكه:",
            parse_mode="html"
        )
    
    elif call.data == "admin_list_subs":
        subscriptions = load_subscriptions()
        
        if not subscriptions:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="📋 <strong>قائمة المشتركين</strong>\n\n❌ لا يوجد مشتركين حالياً.",
                parse_mode="html"
            )
            return
        
        subs_text = "📋 <strong>قائمة المشتركين</strong>\n\n"
        for i, (sub_id, sub_data) in enumerate(subscriptions.items(), 1):
            expiry_date = datetime.fromisoformat(sub_data["expiry_date"])
            remaining = get_remaining_time(sub_data["expiry_date"])
            subs_text += f"{i}. ايدي: <code>{sub_id}</code>\n   المدة: {sub_data['days']} يوم\n   الإنتهاء: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}\n   الحالة: {remaining}\n\n"
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=subs_text,
            parse_mode="html"
        )
    
    elif call.data == "admin_cancel":
        if user_id in admin_states:
            del admin_states[user_id]
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="✅ تم إلغاء العملية.",
            parse_mode="html"
        )

# معالجة رسائل المطور لإدارة الاشتراكات
@bot.message_handler(func=lambda message: str(message.from_user.id) == str(DEVELOPER_ID) and str(message.from_user.id) in admin_states)
def handle_admin_messages(message):
    user_id = str(message.from_user.id)
    state = admin_states[user_id]
    
    if state == "awaiting_user_id":
        try:
            target_user_id = int(message.text)
            admin_states[user_id] = {"action": "add_sub", "user_id": target_user_id}
            
            bot.send_message(message.chat.id, "🕐 <strong>إضافة اشتراك</strong>\n\nأرسل عدد أيام الاشتراك:", parse_mode="html")
        
        except ValueError:
            bot.send_message(message.chat.id, "❌ يرجى إرسال ايدي صحيح (أرقام فقط).")
    
    elif state == "awaiting_remove_id":
        try:
            target_user_id = int(message.text)
            subscriptions = load_subscriptions()
            
            if str(target_user_id) in subscriptions:
                del subscriptions[str(target_user_id)]
                save_subscriptions(subscriptions)
                
                bot.send_message(message.chat.id, f"✅ تم حذف اشتراك المستخدم <code>{target_user_id}</code> بنجاح.", parse_mode="html")
                
                # إرسال إشعار للمستخدم
                try:
                    bot.send_message(target_user_id, "⛔️ تم إلغاء اشتراكك في البوت بواسطة المطور.")
                except:
                    pass  # إذا كان المستخدم لم يبدأ محادثة مع البوت
            else:
                bot.send_message(message.chat.id, f"❌ لا يوجد اشتراك للمستخدم <code>{target_user_id}</code>.", parse_mode="html")
            
            del admin_states[user_id]
        
        except ValueError:
            bot.send_message(message.chat.id, "❌ يرجى إرسال ايدي صحيح (أرقام فقط).")
    
    elif isinstance(state, dict) and state.get("action") == "add_sub":
        try:
            days = int(message.text)
            target_user_id = state["user_id"]
            
            # حساب تاريخ الانتهاء
            expiry_date = datetime.now() + timedelta(days=days)
            
            # حفظ الاشتراك
            subscriptions = load_subscriptions()
            subscriptions[str(target_user_id)] = {
                "days": days,
                "expiry_date": expiry_date.isoformat(),
                "added_date": datetime.now().isoformat()
            }
            save_subscriptions(subscriptions)
            
            bot.send_message(message.chat.id, f"✅ تم تفعيل اشتراك المستخدم <code>{target_user_id}</code> لمدة {days} يوم.\n⏰ ينتهي في: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}", parse_mode="html")
            
            # إرسال إشعار للمستخدم
            try:
                bot.send_message(target_user_id, f"🎉 تم تفعيل اشتراكك في البوت لمدة {days} يوم.\n⏰ ينتهي في: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}\n\nاستمتع باستخدام البوت! 🤩")
            except:
                pass  # إذا كان المستخدم لم يبدأ محادثة مع البوت
            
            del admin_states[user_id]
        
        except ValueError:
            bot.send_message(message.chat.id, "❌ يرجى إرسال عدد أيام صحيح (أرقام فقط).")

@bot.message_handler(commands=["start"])
@check_channel_subscription_decorator
def start(message):
    user_id = str(message.from_user.id)
    
    # التحقق من الاشتراك
    if int(user_id) != DEVELOPER_ID:
        is_subscribed, sub_data = check_subscription(user_id)
        if not is_subscribed:
            bot.send_message(message.chat.id, f"⛔️ عذراً، يجب عليك الاشتراك لاستخدام البوت.\n📞 راسل المطور {DEVELOPER_USERNAME} للاشتراك.")
            return
    
    users = load_users()
    ensure_user(users, user_id)
    save_users(users)
    
    # عرض معلومات الاشتراك
    is_subscribed, sub_data = check_subscription(user_id)
    expiry_date = datetime.fromisoformat(sub_data["expiry_date"]) if sub_data else None
    
    if is_subscribed and expiry_date:
        remaining_time = get_remaining_time(sub_data["expiry_date"])
        subscription_info = f"""
✅ <strong>اشتراكك ({sub_data['days']} يوم) فعال حتى:</strong>
<code>{expiry_date.strftime('%Y-%m-%d %H:%M:%S')}</code>

{remaining_time}
        """
    else:
        subscription_info = "⛔️ <strong>لا يوجد اشتراك فعال</strong>"
    
    markup = InlineKeyboardMarkup(row_width=2)
    
    # الأزرار الرئيسية
    markup.add(
        InlineKeyboardButton(text="👤 إدارة الحسابات", callback_data="account_management"),
        InlineKeyboardButton(text="📢 إدارة النشر", callback_data="post_management"),
        InlineKeyboardButton(text="👥 إدارة المجموعات", callback_data="group_management"),
        InlineKeyboardButton(text="ℹ️ معلومات الاشتراك", callback_data="subscription_info")
    )
    
    bot.send_message(message.chat.id, f"<strong>مرحباً بك في بوت النشر التلقائي للتليجرام 👋</strong>\n\n{subscription_info}", reply_markup=markup, parse_mode="html")

# إدارة الحسابات
@bot.callback_query_handler(func=lambda call: call.data == "account_management")
@check_channel_subscription_callback
def account_management(call):
    user_id = str(call.from_user.id)
    users = load_users()
    ensure_user(users, user_id)
    
    markup = InlineKeyboardMarkup(row_width=2)
    
    # عرض الحسابات المسجلة
    if "sessions" in users[user_id] and users[user_id]["sessions"]:
        for session_name, session_str in users[user_id]["sessions"].items():
            markup.add(InlineKeyboardButton(text=f"🗑️ {session_name}", callback_data=f"delete_account_{session_name}"))
    else:
        markup.add(InlineKeyboardButton(text="❌ لا توجد حسابات", callback_data="none"))
    
    markup.add(
        InlineKeyboardButton(text="📱 إضافة بالهاتف", callback_data="add_account_phone"),
        InlineKeyboardButton(text="🔑 إضافة بالكود", callback_data="add_session_string"),
        InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main")
    )
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="<strong>👤 إدارة الحسابات</strong>\n\nيمكنك إضافة أو حذف الحسابات المسجلة في البوت",
        reply_markup=markup,
        parse_mode="html"
    )

# حذف حساب
@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_account_"))
@check_channel_subscription_callback
def delete_account(call):
    user_id = str(call.from_user.id)
    session_name = call.data.replace("delete_account_", "")
    
    users = load_users()
    
    if "sessions" in users[user_id] and session_name in users[user_id]["sessions"]:
        del users[user_id]["sessions"][session_name]
        save_users(users)
        
        bot.answer_callback_query(call.id, "✅ تم حذف الحساب")
        account_management(call)  # تحديث القائمة

# إضافة حساب بالهاتف
@bot.callback_query_handler(func=lambda call: call.data == "add_account_phone")
@check_channel_subscription_callback
def add_account_phone(call):
    user_id = str(call.from_user.id)
    users = load_users()
    
    # التحقق إذا كان لديه حساب بالفعل
    if "sessions" in users[user_id] and users[user_id]["sessions"]:
        bot.answer_callback_query(call.id, "❌ لديك حساب بالفعل، يمكنك حذفه أولاً", show_alert=True)
        return
    
    # تعيين حالة المستخدم
    user_states[user_id] = "awaiting_phone"
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="account_management"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="<strong>📱 إضافة حساب برقم الهاتف</strong>\n\nأرسل رقم هاتفك مع رمز الدولة (مثل +20123456789):",
        reply_markup=markup,
        parse_mode="html"
    )

# إضافة حساب بكود الجلسة
@bot.callback_query_handler(func=lambda call: call.data == "add_session_string")
@check_channel_subscription_callback
def add_session_string(call):
    user_id = str(call.from_user.id)
    users = load_users()
    
    # التحقق إذا كان لديه حساب بالفعل
    if "sessions" in users[user_id] and users[user_id]["sessions"]:
        bot.answer_callback_query(call.id, "❌ لديك حساب بالفعل، يمكنك حذفه أولاً", show_alert=True)
        return
    
    # تعيين حالة المستخدم
    user_states[user_id] = "awaiting_session"
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="account_management"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="<strong>🔑 إضافة حساب بكود الجلسة</strong>\n\nأرسل كود الجلسة الخاص بحسابك:",
        reply_markup=markup,
        parse_mode="html"
    )

# معالجة رسائل المستخدم
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = str(message.from_user.id)
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    if state == "awaiting_phone":
        handle_phone_input(message, user_id)
    elif state == "awaiting_code":
        handle_code_input(message, user_id)
    elif state == "awaiting_password":
        handle_password_input(message, user_id)
    elif state == "awaiting_session":
        handle_session_input(message, user_id)
    elif state == "awaiting_time":
        handle_time_input(message, user_id)
    elif state == "awaiting_message":
        handle_message_input(message, user_id)

def handle_phone_input(message, user_id):
    phone = message.text
    
    if not phone.startswith('+'):
        bot.send_message(message.chat.id, "❌ يرجى إرسال رقم الهاتف مع رمز الدولة مثل +20123456789")
        return
    
    users = load_users()
    ensure_user(users, user_id)
    
    # حفظ رقم الهاتف مؤقتاً
    users[user_id]["temp_phone"] = phone
    save_users(users)
    
    # تغيير حالة المستخدم
    user_states[user_id] = "awaiting_code"
    
    # استخدام الدالة الجديدة التي تعمل بشكل متزامن
    asyncio.run_coroutine_threadsafe(send_code_request(phone, message.chat.id, user_id), main_loop)

async def send_code_request(phone, chat_id, user_id):
    try:
        client = create_client()
        await client.connect()
        sent = await client.send_code_request(phone)
        
        users = load_users()
        ensure_user(users, user_id)
        users[user_id]["phone_code_hash"] = sent.phone_code_hash
        save_users(users)
        
        # حفظ العميل مؤقتاً
        clients[user_id] = client
        
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="account_management"))
        
        bot.send_message(chat_id, "📩 تم إرسال رمز التحقق إلى حسابك. أرسل الرمز الآن:", reply_markup=markup)
        
    except PhoneNumberInvalidError:
        bot.send_message(chat_id, "❌ رقم الهاتف غير صحيح. يرجى إرسال رقم هاتف صحيح مع رمز الدولة.")
        user_states[user_id] = "awaiting_phone"
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ في إرسال الرمز: {str(e)}")
        user_states[user_id] = "awaiting_phone"

def handle_code_input(message, user_id):
    code = message.text.strip()
    
    users = load_users()
    ensure_user(users, user_id)
    
    phone = users[user_id].get("temp_phone", "")
    phone_code_hash = users[user_id].get("phone_code_hash", "")
    
    if not phone or not phone_code_hash:
        bot.send_message(message.chat.id, "❌ حدث خطأ، يرجى المحاولة مرة أخرى")
        user_states[user_id] = "awaiting_phone"
        return
    
    client = clients.get(user_id)
    if client:
        asyncio.run_coroutine_threadsafe(sign_in(client, phone, code, phone_code_hash, message.chat.id, user_id), main_loop)
    else:
        bot.send_message(message.chat.id, "❌ حدث خطأ، يرجى المحاولة مرة أخرى")
        user_states[user_id] = "awaiting_phone"

async def sign_in(client, phone, code, phone_code_hash, chat_id, user_id):
    try:
        # استخدام الطريقة القديمة الموثوقة لتسجيل الدخول
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        
        # الحصول على معلومات المستخدم
        me = await client.get_me()
        session_str = client.session.save()
        
        # حفظ الجلسة
        users = load_users()
        ensure_user(users, user_id)
        
        # إنشاء اسم للحساب
        account_name = f"حساب_{me.id}"
        if "sessions" not in users[user_id]:
            users[user_id]["sessions"] = {}
        
        users[user_id]["sessions"][account_name] = session_str
        
        # تنظيف البيانات المؤقتة
        if "temp_phone" in users[user_id]:
            del users[user_id]["temp_phone"]
        if "phone_code_hash" in users[user_id]:
            del users[user_id]["phone_code_hash"]
        
        save_users(users)
        
        # تنظيف العميل مؤقت
        if user_id in clients:
            del clients[user_id]
        
        # إزالة حالة المستخدم
        if user_id in user_states:
            del user_states[user_id]
        
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="account_management"))
        
        first_name = me.first_name or ""
        username = f"@{me.username}" if me.username else "لا يوجد"
        
        bot.send_message(chat_id, f"✅ تم تسجيل الحساب بنجاح: {first_name} ({username})", reply_markup=markup)
        
        await client.disconnect()
        
    except SessionPasswordNeededError:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="account_management"))
        
        bot.send_message(chat_id, "🔒 الحساب محمي بكلمة مرور ثنائية. أرسل كلمة المرور الآن:", reply_markup=markup)
        
        # تغيير حالة المستخدم لانتظار كلمة المرور
        user_states[user_id] = "awaiting_password"
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ في تسجيل الدخول: {str(e)}")
        user_states[user_id] = "awaiting_phone"

def handle_password_input(message, user_id):
    password = message.text
    
    users = load_users()
    ensure_user(users, user_id)
    
    phone = users[user_id].get("temp_phone", "")
    phone_code_hash = users[user_id].get("phone_code_hash", "")
    
    if not phone or not phone_code_hash:
        bot.send_message(message.chat.id, "❌ حدث خطأ، يرجى المحاولة مرة أخرى")
        if user_id in user_states:
            del user_states[user_id]
        return
    
    client = clients.get(user_id)
    if client:
        asyncio.run_coroutine_threadsafe(sign_in_with_password(client, phone, password, phone_code_hash, message.chat.id, user_id), main_loop)
    else:
        bot.send_message(message.chat.id, "❌ حدث خطأ، يرجى المحاولة مرة أخرى")
        if user_id in user_states:
            del user_states[user_id]

async def sign_in_with_password(client, phone, password, phone_code_hash, chat_id, user_id):
    try:
        await client.sign_in(phone=phone, password=password, phone_code_hash=phone_code_hash)
        
        # الحصول على معلومات المستخدم
        me = await client.get_me()
        session_str = client.session.save()
        
        # حفظ الجلسة
        users = load_users()
        ensure_user(users, user_id)
        
        # إنشاء اسم للحساب
        account_name = f"حساب_{me.id}"
        if "sessions" not in users[user_id]:
            users[user_id]["sessions"] = {}
        
        users[user_id]["sessions"][account_name] = session_str
        
        # تنظيف البيانات المؤقتة
        if "temp_phone" in users[user_id]:
            del users[user_id]["temp_phone"]
        if "phone_code_hash" in users[user_id]:
            del users[user_id]["phone_code_hash"]
        
        save_users(users)
        
        # تنظيف العميل المؤقت
        if user_id in clients:
            del clients[user_id]
        
        # إزالة حالة المستخدم
        if user_id in user_states:
            del user_states[user_id]
        
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="account_management"))
        
        first_name = me.first_name or ""
        username = f"@{me.username}" if me.username else "لا يوجد"
        
        bot.send_message(chat_id, f"✅ تم تسجيل الحساب بنجاح: {first_name} ({username})", reply_markup=markup)
        
        await client.disconnect()
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ في تسجيل الدخول: {str(e)}")
        if user_id in user_states:
            del user_states[user_id]

def handle_session_input(message, user_id):
    session_string = message.text.strip()
    
    # استخدام الدالة الجديدة التي تعمل بشكل متزامن
    asyncio.run_coroutine_threadsafe(test_session(session_string, message.chat.id, user_id), main_loop)

async def test_session(session_string, chat_id, user_id):
    try:
        client = create_client(session_string)
        await client.connect()
        
        # التحقق من صحة الجلسة
        if not await client.is_user_authorized():
            await client.disconnect()
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="account_management"))
            bot.send_message(chat_id, "❌ كود الجلسة غير صالح أو منتهي الصلاحية", reply_markup=markup)
            return
        
        # الحصول على معلومات المستخدم
        me = await client.get_me()
        
        # حفظ الجلسة
        users = load_users()
        ensure_user(users, user_id)
        
        # إنشاء اسم للحساب
        account_name = f"حساب_{me.id}"
        if "sessions" not in users[user_id]:
            users[user_id]["sessions"] = {}
        
        users[user_id]["sessions"][account_name] = session_string
        save_users(users)
        
        # إزالة حالة المستخدم
        if user_id in user_states:
            del user_states[user_id]
        
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="account_management"))
        
        first_name = me.first_name or ""
        username = f"@{me.username}" if me.username else "لا يوجد"
        
        bot.send_message(chat_id, f"✅ تم تسجيل الحساب بنجاح: {first_name} ({username})", reply_markup=markup)
        
        await client.disconnect()
        
    except Exception as e:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="account_management"))
        bot.send_message(chat_id, f"❌ خطأ في تسجيل الدخول: {str(e)}", reply_markup=markup)
        if user_id in user_states:
            del user_states[user_id]

# إدارة النشر
@bot.callback_query_handler(func=lambda call: call.data == "post_management")
@check_channel_subscription_callback
def post_management(call):
    user_id = str(call.from_user.id)
    users = load_users()
    ensure_user(users, user_id)
    
    settings = users[user_id].get("settings", {})
    time_val = settings.get("time", "غير مضبوط")
    message_text = settings.get("message", "غير مضبوطة")
    
    if len(message_text) > 50:
        message_preview = message_text[:50] + "..."
    else:
        message_preview = message_text
    
    # التحقق من حالة النشر
    is_posting = posting_status.get(user_id, False)
    posting_button_text = "⏹️ إيقاف النشر" if is_posting else "🚀 بدء النشر"
    posting_button_data = "stop_posting" if is_posting else "start_posting"
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(text=f"⏱️ الوقت: {time_val} ثانية", callback_data="set_time"),
        InlineKeyboardButton(text=f"📝 الرسالة: {message_preview}", callback_data="set_message"),
        InlineKeyboardButton(text=posting_button_text, callback_data=posting_button_data),
        InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main")
    )
    
    status_text = "🟢 <strong>جاري النشر حالياً</strong>" if is_posting else "🔴 <strong>النشر متوقف</strong>"
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"<strong>📢 إدارة النشر</strong>\n\n{status_text}\n\nيمكنك ضبط إعدادات النشر وبدء/إيقاف النشر التلقائي",
        reply_markup=markup,
        parse_mode="html"
    )

# ضبط الوقت
@bot.callback_query_handler(func=lambda call: call.data == "set_time")
@check_channel_subscription_callback
def set_time_callback(call):
    user_id = str(call.from_user.id)
    user_states[user_id] = "awaiting_time"
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="post_management"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="<strong>⏱️ أرسل الوقت بين كل رسالة بالثواني</strong>\n\n📝 مثال: 30 (لنشر كل 30 ثانية)",
        reply_markup=markup,
        parse_mode="html"
    )

def handle_time_input(message, user_id):
    try:
        time_val = int(message.text)
        if time_val < 5:
            bot.send_message(message.chat.id, "❌ الوقت يجب أن يكون 5 ثواني على الأقل")
            return
        
        users = load_users()
        ensure_user(users, user_id)
        
        if "settings" not in users[user_id]:
            users[user_id]["settings"] = {}
            
        users[user_id]["settings"]["time"] = time_val
        save_users(users)
        
        del user_states[user_id]
        
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="post_management"))
        
        bot.send_message(message.chat.id, f"✅ تم ضبط الوقت إلى {time_val} ثانية", reply_markup=markup, parse_mode="html")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ يرجى إرسال رقم صحيح (أرقام فقط)")

# ضبط الرسالة
@bot.callback_query_handler(func=lambda call: call.data == "set_message")
@check_channel_subscription_callback
def set_message_callback(call):
    user_id = str(call.from_user.id)
    user_states[user_id] = "awaiting_message"
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="post_management"))
    
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="<strong>📝 أرسل الرسالة التي تريد نشرها في المجموعات</strong>\n\n💡 يمكنك إرسال نص، صورة، أو أي نوع من المحتوى",
            reply_markup=markup,
            parse_mode="html"
        )

def handle_message_input(message, user_id):
    users = load_users()
    ensure_user(users, user_id)
    
    if "settings" not in users[user_id]:
        users[user_id]["settings"] = {}
        
    # حفظ محتوى الرسالة بناءً على نوعها
    if message.text:
        users[user_id]["settings"]["message"] = message.text
        users[user_id]["settings"]["message_type"] = "text"
    elif message.photo:
        users[user_id]["settings"]["message"] = message.caption or ""
        users[user_id]["settings"]["photo_id"] = message.photo[-1].file_id
        users[user_id]["settings"]["message_type"] = "photo"
    elif message.video:
        users[user_id]["settings"]["message"] = message.caption or ""
        users[user_id]["settings"]["video_id"] = message.video.file_id
        users[user_id]["settings"]["message_type"] = "video"
    elif message.document:
        users[user_id]["settings"]["message"] = message.caption or ""
        users[user_id]["settings"]["document_id"] = message.document.file_id
        users[user_id]["settings"]["message_type"] = "document"
    else:
        users[user_id]["settings"]["message"] = "رسالة غير معروفة"
        users[user_id]["settings"]["message_type"] = "unknown"
    
    save_users(users)
    
    del user_states[user_id]
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="post_management"))
    
    bot.send_message(message.chat.id, "✅ تم حفظ الرسالة بنجاح", reply_markup=markup, parse_mode="html")

# بدء النشر
@bot.callback_query_handler(func=lambda call: call.data == "start_posting")
@check_channel_subscription_callback
def start_posting_callback(call):
    user_id = str(call.from_user.id)
    
    # تعيين حالة النشر إلى نشط
    posting_status[user_id] = True
    
    # بدء النشر في خلفية
    posting_thread = threading.Thread(target=start_posting_thread, args=(call.message, user_id))
    posting_thread.start()
    
    bot.answer_callback_query(call.id, "🚀 بدأ النشر في الخلفية")
    
    # تحديث واجهة النشر
    post_management(call)

# إيقاف النشر
@bot.callback_query_handler(func=lambda call: call.data == "stop_posting")
@check_channel_subscription_callback
def stop_posting_callback(call):
    user_id = str(call.from_user.id)
    
    # إيقاف النشر
    posting_status[user_id] = False
    
    bot.answer_callback_query(call.id, "⏹️ تم إيقاف النشر")
    
    # تحديث واجهة النشر
    post_management(call)

def start_posting_thread(message, user_id):
    users = load_users()
    user_id_str = str(user_id)
    ensure_user(users, user_id_str)
    settings = users[user_id_str].get("settings", {})
    sessions = users[user_id_str].get("sessions", {})
    selected_groups = users[user_id_str].get("selected_groups", [])

    # التحقق من الإعدادات المطلوبة
    if not settings.get("time") or not settings.get("message"):
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="post_management"))
        bot.send_message(message.chat.id, "<strong>❌ يرجى إكمال جميع الإعدادات أولاً (الوقت والرسالة)</strong>",
                         parse_mode="html", reply_markup=markup)
        return
    
    if not sessions:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="post_management"))
        bot.send_message(message.chat.id, "<strong>❌ لا توجد حسابات مسجلة. يرجى إضافة حساب أولاً.</strong>",
                         parse_mode="html", reply_markup=markup)
        return

    try:
        time_val = int(settings["time"])
        message_type = settings.get("message_type", "text")
        message_content = settings["message"]
        
        # بدء النشر
        asyncio.run_coroutine_threadsafe(
            start_posting_async(user_id_str, message.chat.id, time_val, message_type, message_content, settings, sessions, selected_groups), 
            main_loop
        )
    
    except Exception as e:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="post_management"))
        bot.send_message(message.chat.id, f"<strong>❌ خطأ في بدء النشر: {str(e)}</strong>", parse_mode="html", reply_markup=markup)

async def start_posting_async(user_id, chat_id, time_val, message_type, message_content, settings, sessions, selected_groups):
    sent_count = 0
    error_count = 0
    
    while posting_status.get(user_id, False):
        for session_name, session_str in sessions.items():
            if not posting_status.get(user_id, False):
                break
                
            try:
                client = create_client(session_str)
                await client.connect()
                
                # الحصول على المجموعات
                dialogs = await client.get_dialogs()
                groups_to_post = []
                
                if selected_groups:
                    # النشر في المجموعات المحددة فقط
                    for group_id in selected_groups:
                        try:
                            entity = await client.get_entity(int(group_id))
                            if hasattr(entity, 'title'):
                                groups_to_post.append(entity)
                        except:
                            continue
                else:
                    # النشر في جميع المجموعات
                    for dialog in dialogs:
                        if dialog.is_group and hasattr(dialog.entity, 'title'):
                            groups_to_post.append(dialog.entity)
                
                if not groups_to_post:
                    if posting_status.get(user_id, False):
                        bot.send_message(chat_id, f"❌ لم يتم العثور على أي مجموعات في الحساب {session_name}")
                    await client.disconnect()
                    continue
                
                # النشر في المجموعات
                for group in groups_to_post:
                    if not posting_status.get(user_id, False):
                        break
                        
                    try:
                        await client.send_message(group, message_content)
                        sent_count += 1
                        await asyncio.sleep(time_val)
                        
                    except Exception as e:
                        error_count += 1
                        error_msg = f"❌ خطأ في المجموعة {getattr(group, 'title', group.id)}: {str(e)}"
                        if len(error_msg) > 4000:
                            error_msg = error_msg[:4000] + "..."
                        if posting_status.get(user_id, False):
                            bot.send_message(chat_id, error_msg)
                        await asyncio.sleep(2)  # انتظار قبل المحاولة التالية
                
                await client.disconnect()
                
            except Exception as e:
                error_count += 1
                error_msg = f"❌ خطأ في الجلسة {session_name}: {str(e)}"
                if len(error_msg) > 4000:
                    error_msg = error_msg[:4000] + "..."
                if posting_status.get(user_id, False):
                    bot.send_message(chat_id, error_msg)
        
        # انتظار قبل البدء في الدورة التالية
        if posting_status.get(user_id, False):
            await asyncio.sleep(5)
    
    # إرسال تقرير نهائي
    report_text = f"""
📊 <strong>تقرير النشر</strong>

✅ الرسائل المرسلة: {sent_count}
❌ الأخطاء: {error_count}
🟢 الحالة: تم إيقاف النشر
    """
    bot.send_message(chat_id, report_text, parse_mode="html")

# إدارة المجموعات
@bot.callback_query_handler(func=lambda call: call.data == "group_management")
@check_channel_subscription_callback
def group_management(call):
    user_id = str(call.from_user.id)
    users = load_users()
    ensure_user(users, user_id)
    
    # تحميل المجموعات من الحسابات
    asyncio.run_coroutine_threadsafe(load_user_groups(call.message.chat.id, user_id, call.message.message_id), main_loop)

async def load_user_groups(chat_id, user_id, message_id=None):
    try:
        users = load_users()
        ensure_user(users, user_id)
        sessions = users[user_id].get("sessions", {})
        
        if not sessions:
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main"))
            
            if message_id:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="<strong>👥 إدارة المجموعات</strong>\n\n❌ لا توجد حسابات مسجلة. يرجى إضافة حساب أولاً.",
                    reply_markup=markup,
                    parse_mode="html"
                )
            else:
                bot.send_message(chat_id, "<strong>👥 إدارة المجموعات</strong>\n\n❌ لا توجد حسابات مسجلة. يرجى إضافة حساب أولاً.", reply_markup=markup, parse_mode="html")
            return
        
        # استخدام الجلسة الأولى
        session_str = list(sessions.values())[0]
        client = create_client(session_str)
        await client.connect()
        
        # الحصول على المجموعات
        dialogs = await client.get_dialogs()
        groups = []
        
        for dialog in dialogs:
            if dialog.is_group and hasattr(dialog.entity, 'title'):
                groups.append(dialog.entity)
        
        await client.disconnect()
        
        if not groups:
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main"))
            
            if message_id:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="<strong>👥 إدارة المجموعات</strong>\n\n❌ لم يتم العثور على أي مجموعات في الحساب.",
                    reply_markup=markup,
                    parse_mode="html"
                )
            else:
                bot.send_message(chat_id, "<strong>👥 إدارة المجموعات</strong>\n\n❌ لم يتم العثور على أي مجموعات في الحساب.", reply_markup=markup, parse_mode="html")
            return
        
        # عرض المجموعات
        markup = InlineKeyboardMarkup(row_width=1)
        
        selected_groups = users[user_id].get("selected_groups", [])
        
        for group in groups:
            is_selected = str(group.id) in selected_groups
            emoji = "✅" if is_selected else "❌"
            button_text = f"{emoji} {group.title}"
            if len(button_text) > 50:
                button_text = button_text[:47] + "..."
            markup.add(InlineKeyboardButton(
                text=button_text,
                callback_data=f"toggle_group_{group.id}"
            ))
        
        markup.add(
            InlineKeyboardButton(text="📋 عرض المجموعات المحددة", callback_data="show_selected_groups"),
            InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main")
        )
        
        if message_id:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="<strong>👥 إدارة المجموعات</strong>\n\nاختر المجموعات التي تريد النشر فيها:",
                reply_markup=markup,
                parse_mode="html"
            )
        else:
            bot.send_message(chat_id, "<strong>👥 إدارة المجموعات</strong>\n\nاختر المجموعات التي تريد النشر فيها:", reply_markup=markup, parse_mode="html")
        
    except Exception as e:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main"))
        
        error_msg = f"<strong>❌ خطأ في تحميل المجموعات:</strong>\n{str(e)}"
        if len(error_msg) > 4000:
            error_msg = error_msg[:4000] + "..."
        
        if message_id:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=error_msg,
                reply_markup=markup,
                parse_mode="html"
            )
        else:
            bot.send_message(chat_id, error_msg, reply_markup=markup, parse_mode="html")

# تبديل اختيار المجموعة
@bot.callback_query_handler(func=lambda call: call.data.startswith("toggle_group_"))
@check_channel_subscription_callback
def toggle_group_selection(call):
    user_id = str(call.from_user.id)
    group_id = call.data.replace("toggle_group_", "")
    
    users = load_users()
    ensure_user(users, user_id)
    
    if "selected_groups" not in users[user_id]:
        users[user_id]["selected_groups"] = []
    
    selected_groups = users[user_id]["selected_groups"]
    
    if group_id in selected_groups:
        selected_groups.remove(group_id)
    else:
        selected_groups.append(group_id)
    
    save_users(users)
    
    # إعادة تحميل قائمة المجموعات
    asyncio.run_coroutine_threadsafe(load_user_groups(call.message.chat.id, user_id, call.message.message_id), main_loop)

# عرض المجموعات المحددة
@bot.callback_query_handler(func=lambda call: call.data == "show_selected_groups")
@check_channel_subscription_callback
def show_selected_groups(call):
    user_id = str(call.from_user.id)
    users = load_users()
    ensure_user(users, user_id)
    
    selected_groups = users[user_id].get("selected_groups", [])
    
    if not selected_groups:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="group_management"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="<strong>✅ المجموعات المحددة</strong>\n\n❌ لم يتم اختيار أي مجموعات بعد",
            reply_markup=markup,
            parse_mode="html"
        )
        return
    
    groups_text = "<strong>✅ المجموعات المحددة:</strong>\n\n"
    for i, group_id in enumerate(selected_groups, 1):
        groups_text += f"{i}. <code>{group_id}</code>\n"
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(text="🗑️ مسح الكل", callback_data="clear_all_groups"),
        InlineKeyboardButton(text="🔙 رجوع", callback_data="group_management")
    )
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=groups_text,
        reply_markup=markup,
        parse_mode="html"
    )

# مسح جميع المجموعات المحددة
@bot.callback_query_handler(func=lambda call: call.data == "clear_all_groups")
@check_channel_subscription_callback
def clear_all_groups(call):
    user_id = str(call.from_user.id)
    users = load_users()
    ensure_user(users, user_id)
    
    if "selected_groups" in users[user_id]:
        users[user_id]["selected_groups"] = []
        save_users(users)
        
        bot.answer_callback_query(call.id, "✅ تم مسح جميع المجموعات المحددة")
        
        # العودة إلى قائمة إدارة المجموعات
        group_management(call)

# معلومات الاشتراك
@bot.callback_query_handler(func=lambda call: call.data == "subscription_info")
@check_channel_subscription_callback
def subscription_info(call):
    user_id = str(call.from_user.id)
    
    is_subscribed, sub_data = check_subscription(user_id)
    expiry_date = datetime.fromisoformat(sub_data["expiry_date"]) if sub_data else None
    
    if is_subscribed and expiry_date:
        remaining_time = get_remaining_time(sub_data["expiry_date"])
        subscription_text = f"""
<strong>ℹ️ معلومات الاشتراك</strong>

✅ <strong>حالة الاشتراك:</strong> فعال
📅 <strong>مدة الاشتراك:</strong> {sub_data['days']} يوم
⏳ <strong>ينتهي في:</strong> {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}

{remaining_time}
        """
    else:
        subscription_text = f"""
<strong>ℹ️ معلومات الاشتراك</strong>

⛔️ <strong>حالة الاشتراك:</strong> غير فعال
📞 <strong>للاشتراك:</strong> راسل المطور {DEVELOPER_USERNAME}
        """
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=subscription_text,
        reply_markup=markup,
        parse_mode="html"
    )

# الرجوع للقائمة الرئيسية
@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
@check_channel_subscription_callback
def back_to_main(call):
    user_id = str(call.from_user.id)
    
    # التحقق من الاشتراك للمستخدمين العاديين
    if int(user_id) != DEVELOPER_ID:
        is_subscribed, sub_data = check_subscription(user_id)
        if not is_subscribed:
            bot.answer_callback_query(call.id, "⛔️ اشتراكك منتهي، راسل المطور", show_alert=True)
            return
    
    users = load_users()
    ensure_user(users, user_id)
    save_users(users)
    
    # عرض معلومات الاشتراك
    is_subscribed, sub_data = check_subscription(user_id)
    expiry_date = datetime.fromisoformat(sub_data["expiry_date"]) if sub_data else None
    
    if is_subscribed and expiry_date:
        remaining_time = get_remaining_time(sub_data["expiry_date"])
        subscription_info = f"""
✅ <strong>اشتراكك ({sub_data['days']} يوم) فعال حتى:</strong>
<code>{expiry_date.strftime('%Y-%m-%d %H:%M:%S')}</code>

{remaining_time}
        """
    else:
        subscription_info = "⛔️ <strong>لا يوجد اشتراك فعال</strong>"
    
    markup = InlineKeyboardMarkup(row_width=2)
    
    # الأزرار الرئيسية
    markup.add(
        InlineKeyboardButton(text="👤 إدارة الحسابات", callback_data="account_management"),
        InlineKeyboardButton(text="📢 إدارة النشر", callback_data="post_management"),
        InlineKeyboardButton(text="👥 إدارة المجموعات", callback_data="group_management"),
        InlineKeyboardButton(text="ℹ️ معلومات الاشتراك", callback_data="subscription_info")
    )
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"<strong>مرحباً بك في بوت النشر التلقائي للتليجرام 👋</strong>\n\n{subscription_info}",
        reply_markup=markup,
        parse_mode="html"
    )

# Routes for Flask app
@app.route('/', methods=['GET', 'POST'])
def main_home():
    if request.method == 'POST':
        print("📩 تم استلام POST request على / - توجيه إلى /webhook")
        return telegram_webhook()
    return "🤖 البوت يعمل بشكل طبيعي!"

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    print("📩 تم استلام طلب ويب هوك على /webhook")
    
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        print(f"📦 حجم البيانات: {len(json_string)} bytes")
        
        try:
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            print("✅ تم معالجة التحديث بنجاح")
            return 'OK', 200
        except Exception as e:
            print(f"❌ خطأ في معالجة التحديث: {e}")
            return 'Error', 500
    
    print("❌ طلب غير صحيح")
    return 'Bad Request', 400

@app.route('/health')
def health_check():
    return "✅ البوت نشط ومستعد للعمل"

def keep_alive():
    """
    دالة لإبقاء البوت نشطًا عن طريق تشغيل خادم ويب بسيط
    """
    print("🌐 خادم الويب يعمل على المنفذ 8080")

# وظيفة لضبط الويب هوك تلقائياً
def setup_webhook():
    try:
        WEBHOOK_URL = "https://auto-publish.onrender.com/webhook"
        bot.remove_webhook()
        time.sleep(2)
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"✅ تم ضبط الويب هوك على: {WEBHOOK_URL}")
        
        # التحقق من الإعدادات
        webhook_info = bot.get_webhook_info()
        print(f"📊 معلومات الويب هوك: {webhook_info.url}")
        
    except Exception as e:
        print(f"❌ خطأ في ضبط الويب هوك: {e}")

# تشغيل البوت
if __name__ == "__main__":
    # ضبط الويب هوك تلقائياً
    setup_webhook()
    
    # تشغيل خادم الويب لإبقاء البوت نشطاً
    keep_alive()
    
    print("✅ البوت يعمل الآن")
    
    # تشغيل event loop في خلفية
    def run_loop():
        asyncio.set_event_loop(main_loop)
        main_loop.run_forever()
    
    loop_thread = threading.Thread(target=run_loop, daemon=True)
    loop_thread.start()
    
    # بدء الاستطلاع كخيار احتياطي
    polling_thread = threading.Thread(target=bot.infinity_polling)
    polling_thread.daemon = True
    polling_thread.start()
    
    # إبقاء البرنامج الرئيسي يعمل
    while True:
        time.sleep(3600)  # انتظر ساعة ثم كرر
