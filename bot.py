import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
import jdatetime
import logging

# تنظیمات logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توکن ربات (بعدا تغییر بده)
TOKEN = '8477954060:AAF0XfLfowQvpIanCIbkAMzh1f45uTFsn3U'
bot = telebot.TeleBot(TOKEN)

# آیدی ادمین
ADMIN_ID = 7418672521

# دیکشنری برای ذخیره اطلاعات کاربران (کلید: user_id)
user_data = {}

# دیکشنری برای ذخیره پیام‌های ارسالی به ادمین (برای تأیید)
admin_messages = {}

# دیکشنری برای ذخیره زمان تأیید کاربران
approval_timestamps = {}

# لیست فیلدها به ترتیب برای دریافت خودکار
FIELDS = [
    'نام', 'نام خانوادگی', 'کد ملی', 'نام پدر', 'تاریخ تولد', 'شماره تماس', 'دوره انتخابی'
]

# لیست دپارتمان‌ها و دوره‌ها با کدهای کوتاه
DEPARTMENTS = {
    'دپارتمان خودرو': [
        ('c1', 'گیربکس'),
        ('c2', 'برق جامع'),
        ('c3', 'برق پایه'),
        ('c4', 'ریمپ'),
        ('c5', 'مالتی پلکس'),
        ('c6', 'تعویض روغن'),
        ('c7', 'جلوبندی'),
        ('c8', 'کارشناسی'),
        ('c9', 'مکانیک'),
        ('c10', 'موتورسیکلت')
    ],
    'دپارتمان الکترونیک': [
        ('c11', 'موبایل'),
        ('c12', 'برد'),
        ('c13', 'تجهیزات پزشکی'),
        ('c14', 'تجهیزات دندانپزشکی')
    ],
    'دپارتمان برق': [
        ('c15', 'برق صنعتی'),
        ('c16', 'آسانسور'),
        ('c17', 'یخچال'),
        ('c18', 'لباسشویی'),
        ('c19', 'لوازم خرد'),
        ('c20', 'دوربین'),
        ('c21', 'هوشمندسازی'),
        ('c22', 'سولار'),
        ('c23', 'برق ساختمان')
    ],
    'دپارتمان تاسیسات': [
        ('c24', 'اسپرسو'),
        ('c25', 'شوفاژ'),
        ('c26', 'کولر'),
        ('c27', 'تصفیه آب')
    ],
    'دپارتمان فناوری اطلاعات': [
        ('c28', 'سئو'),
        ('c29', 'پایتون'),
        ('c30', 'ICDL'),
        ('c31', 'لپ تاپ'),
        ('c32', 'پایتون سیاه (تست امنیت سیستم)'),
        ('c33', 'هوش مصنوعی'),
        ('c34', 'برنامه‌نویسی وردپرس'),
        ('c35', 'فوتوشوپ'),
        ('c36', 'حسابداری')
    ]
}

# دیکشنری برای مپ کردن کد به نام کامل دوره
COURSE_CODE_TO_NAME = {code: name for dept in DEPARTMENTS.values() for code, name in dept}
COURSE_NAME_TO_CODE = {name: code for dept in DEPARTMENTS.values() for code, name in dept}

# حالت‌های ورودی (برای تشخیص اینکه کاربر داره چی وارد می‌کنه)
user_states = {}

# تابع برای تبدیل تاریخ به شمسی
def get_persian_date(dt=None):
    try:
        dt = dt or datetime.now()
        jalili_date = jdatetime.date.fromgregorian(
            day=dt.day,
            month=dt.month,
            year=dt.year
        )
        return jalili_date.strftime("%Y/%m/%d")
    except Exception as e:
        logger.error(f"خطا در تبدیل تاریخ: {e}")
        return "1403/01/01"  # تاریخ پیش‌فرض در صورت خطا

# تابع برای ساخت reply keyboard اولیه
def get_start_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton('📋 اطلاعات اولیه'))
    markup.add(KeyboardButton('📚 سوالات متداول'))
    return markup

# تابع برای ساخت inline keyboard اصلی (نمایش اطلاعات واردشده)
def get_inline_keyboard(user_id):
    markup = InlineKeyboardMarkup(row_width=2)
    user_info = user_data.get(user_id, {})
    for field in FIELDS:
        if field == 'دوره انتخابی':
            courses = user_info.get(field, [])
            value = ', '.join([COURSE_CODE_TO_NAME.get(code, 'خالی') for code in courses]) if courses else 'خالی'
        else:
            value = user_info.get(field, 'خالی')
        button_text = f'{field}: {value}'
        markup.add(InlineKeyboardButton(button_text, callback_data=f'edit_{field}'))
    markup.add(InlineKeyboardButton('✅ تایید نهایی', callback_data='confirm'))
    return markup

# تابع برای ساخت inline keyboard انتخاب دپارتمان‌ها
def get_courses_keyboard(user_id):
    markup = InlineKeyboardMarkup(row_width=1)
    for dept in DEPARTMENTS:
        markup.add(InlineKeyboardButton(f'📚 {dept}', callback_data=f'dept_{dept}'))
    markup.add(InlineKeyboardButton('⬅️ بازگشت', callback_data='back_to_main'))
    return markup

# تابع برای ساخت inline keyboard دوره‌های یک دپارتمان
def get_department_courses_keyboard(user_id, dept):
    markup = InlineKeyboardMarkup(row_width=1)
    user_courses = user_data.get(user_id, {}).get('دوره انتخابی', [])
    
    for code, course in DEPARTMENTS[dept]:
        status = '✅ ' if code in user_courses else ''
        markup.add(InlineKeyboardButton(f'{status}{course}', callback_data=f'course_{code}'))
    
    markup.add(InlineKeyboardButton('⬅️ بازگشت به دپارتمان‌ها', callback_data='back_to_courses'))
    return markup

# تابع برای ساخت inline keyboard سوالات متداول
def main_faq_keyboard():
    keyboard = [
        [InlineKeyboardButton("⏰ زمان آزمون کتبی من کی هست؟", callback_data="exam_time")],
        [InlineKeyboardButton("📊 مشاهده نتیجه آزمون کتبی", callback_data="exam_result")],
        [InlineKeyboardButton("🔧 آزمون عملی کی هست؟", callback_data="practical_exam")],
        [InlineKeyboardButton("🕘 ساعت و محل آزمون عملی", callback_data="exam_location")],
        [InlineKeyboardButton("📮 چه مدارکی باید ارسال کنم؟ و به کی تحویل بدم؟", callback_data="send_documents")],
        [InlineKeyboardButton("💰 تعرفه خدمات آموزشی چیه؟", callback_data="service_tariff")],
        [InlineKeyboardButton("🏫 سوالات مربوط به آموزشگاه", callback_data="institute_questions")],
        [InlineKeyboardButton("📞 شماره تماس پرسنل آموزشگاه", callback_data="contact_staff")],
        [InlineKeyboardButton("👨‍💼 شماره تماس مسئول فنی و حرفه ای", callback_data="contact_technical")],
        [InlineKeyboardButton("📜 مدرک مو چجوری دریافت کنم", callback_data="certificate")],
        [InlineKeyboardButton("🎫 کارت ورود به جلسه آزمون کتبی", callback_data="exam_card")],
        [InlineKeyboardButton("❌ کارت ورود به جلسه دانلود نمیشه", callback_data="card_problem")],
        [InlineKeyboardButton("📝 نمونه سوالات از کجا دریافت کنم", callback_data="sample_questions")],
    ]
    return InlineKeyboardMarkup(keyboard)

# تابع برای ساخت inline keyboard بازگشت
def back_to_main_faq_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی سوالات", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# تابع برای دریافت فیلد بعدی
def get_next_field(user_id):
    user_info = user_data.get(user_id, {})
    for i, field in enumerate(FIELDS):
        if field not in user_info or not user_info[field]:
            return field, i
    return None, None

# تابع برای درخواست فیلد از کاربر
def request_field(user_id, field, chat_id):
    user_states[user_id] = field
    if field == 'کد ملی':
        bot.send_message(chat_id, 'لطفا کد ملی (۱۰ رقم) را وارد کنید:')
    elif field == 'شماره تماس':
        bot.send_message(chat_id, 'لطفا شماره تماس (۱۱ رقم، شروع با ۰۹) را وارد کنید:')
    elif field == 'تاریخ تولد':
        bot.send_message(chat_id, 'لطفا تاریخ تولد (فرمت: سال/ماه/روز، مثال: 1380/05/15) را وارد کنید:')
    elif field == 'دوره انتخابی':
        bot.send_message(chat_id, '📚 لطفا دپارتمان مورد نظر را انتخاب کنید:', reply_markup=get_courses_keyboard(user_id))
    else:
        bot.send_message(chat_id, f'لطفا {field} را وارد کنید:')

# تابع برای صحت‌سنجی یک فیلد
def validate_field(field, value):
    if not value:
        return f"{field} نمی‌تواند خالی باشد"
    
    if field == 'کد ملی':
        if not value.isdigit() or len(value) != 10:
            return "کد ملی باید ۱۰ رقم باشد"
    elif field == 'شماره تماس':
        if not value.startswith('09') or not value.isdigit() or len(value) != 11:
            return "شماره تماس باید با ۰۹ شروع شود و ۱۱ رقم باشد"
    elif field == 'تاریخ تولد':
        try:
            year, month, day = map(int, value.split('/'))
            if not (1 <= month <= 12 and 1 <= day <= 31 and 1300 <= year <= 1405):
                return "تاریخ تولد نامعتبر است"
        except:
            return "فرمت تاریخ تولد باید سال/ماه/روز باشد (مثال: 1380/05/15)"
    elif field == 'دوره انتخابی':
        if not value:
            return "حداقل یک دوره انتخاب کنید"
    return None

# تابع برای صحت‌سنجی کل اطلاعات
def validate_data(data):
    errors = []
    for field in FIELDS:
        value = data.get(field, [])
        error = validate_field(field, value)
        if error:
            errors.append(error)
    return errors

# هندلر برای /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    bot.send_message(message.chat.id, '🎉 خوش آمدید! برای وارد کردن یا ویرایش اطلاعات یا مشاهده سوالات متداول، یکی از دکمه‌های زیر را انتخاب کنید:', reply_markup=get_start_keyboard())

# هندلر برای پیام‌های متنی
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == '📋 اطلاعات اولیه':
        user_info = user_data.get(user_id, {})
        errors = validate_data(user_info)
        if not errors:  # همه فیلدها پر و معتبرن
            bot.send_message(message.chat.id, '📝 آیا نیاز به ویرایش اطلاعات دارید؟ اطلاعات فعلی:', reply_markup=get_inline_keyboard(user_id))
        else:
            bot.send_message(message.chat.id, '📝 لطفا اطلاعات را به ترتیب وارد کنید. از "نام" شروع می‌کنیم:', reply_markup=get_inline_keyboard(user_id))
            request_field(user_id, 'نام', message.chat.id)
        return
    
    if text == '📚 سوالات متداول':
        welcome_text = """
        🌟 به ربات آموزشگاه فنی و حرفه ای ایده پاژ خوش آمدید! 🌟
        برای دریافت پاسخ سوالات پرتکرار، یکی از گزینه‌های زیر را انتخاب کنید:
        """
        bot.send_message(message.chat.id, welcome_text, reply_markup=main_faq_keyboard())
        return
    
    if user_id in user_states:
        field = user_states[user_id]
        if field != 'دوره انتخابی':  # دوره انتخابی از طریق inline keyboard پر می‌شه
            error = validate_field(field, text.strip())
            if error:
                bot.send_message(message.chat.id, f'⚠️ خطا: {error}. لطفا دوباره وارد کنید:')
                return
            
            user_data[user_id][field] = text.strip()
            bot.send_message(message.chat.id, f'✅ {field} با موفقیت ذخیره شد: {text}')
            del user_states[user_id]  # حالت رو پاک کن
            
            # پیدا کردن فیلد بعدی
            next_field, _ = get_next_field(user_id)
            if next_field:
                request_field(user_id, next_field, message.chat.id)
            else:
                bot.send_message(message.chat.id, '📝 همه فیلدها پر شدند! می‌توانید اطلاعات را ویرایش کنید یا تایید کنید:', reply_markup=get_inline_keyboard(user_id))

# هندلر برای callback (دکمه‌های inline)
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    if data.startswith('edit_'):
        field = data[5:]  # حذف 'edit_'
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, '📝 اطلاعات فعلی:', reply_markup=get_inline_keyboard(user_id))
        request_field(user_id, field, call.message.chat.id)
    
    elif data.startswith('dept_'):
        dept = data[5:]  # حذف 'dept_'
        bot.answer_callback_query(call.id)
        bot.edit_message_text(f'📚 دوره‌های {dept}:', call.message.chat.id, call.message.message_id, reply_markup=get_department_courses_keyboard(user_id, dept))
    
    elif data.startswith('course_'):
        code = data[7:]  # حذف 'course_'
        bot.answer_callback_query(call.id)
        if user_id not in user_data:
            user_data[user_id] = {}
        if 'دوره انتخابی' not in user_data[user_id]:
            user_data[user_id]['دوره انتخابی'] = []
        
        if code in user_data[user_id]['دوره انتخابی']:
            user_data[user_id]['دوره انتخابی'].remove(code)
            bot.send_message(call.message.chat.id, f'❌ {COURSE_CODE_TO_NAME[code]} از لیست دوره‌ها حذف شد.')
        else:
            user_data[user_id]['دوره انتخابی'].append(code)
            bot.send_message(call.message.chat.id, f'✅ {COURSE_CODE_TO_NAME[code]} به لیست دوره‌ها اضافه شد.')
        
        # به‌روزرسانی کیبورد دپارتمان
        dept = next(d for d, courses in DEPARTMENTS.items() if code in [c[0] for c in courses])
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=get_department_courses_keyboard(user_id, dept))
        
        # چک کردن دوره انتخابی
        error = validate_field('دوره انتخابی', user_data[user_id]['دوره انتخابی'])
        if error:
            bot.send_message(call.message.chat.id, f'⚠️ خطا: {error}. لطفا حداقل یک دوره انتخاب کنید.')
            return
        
        # بازگشت به منوی اصلی
        next_field, _ = get_next_field(user_id)
        if not next_field:
            bot.send_message(call.message.chat.id, '📝 همه فیلدها پر شدند! می‌توانید اطلاعات را ویرایش کنید یا تایید کنید:', reply_markup=get_inline_keyboard(user_id))
        else:
            bot.send_message(call.message.chat.id, '📝 لطفا اطلاعات باقی‌مانده را پر کنید:', reply_markup=get_inline_keyboard(user_id))
            request_field(user_id, next_field, call.message.chat.id)
    
    elif data == 'back_to_courses':
        bot.answer_callback_query(call.id)
        bot.edit_message_text('📚 لطفا دپارتمان مورد نظر را انتخاب کنید:', call.message.chat.id, call.message.message_id, reply_markup=get_courses_keyboard(user_id))
    
    elif data == 'back_to_main':
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, '📝 اطلاعات فعلی:', reply_markup=get_inline_keyboard(user_id))
    
    elif data == 'confirm':
        bot.answer_callback_query(call.id)
        if user_id not in user_data:
            bot.send_message(call.message.chat.id, '⚠️ هیچ اطلاعاتی وارد نشده!')
            return
        
        errors = validate_data(user_data[user_id])
        if errors:
            error_msg = '⚠️ خطاها:\n' + '\n'.join([f'- {e}' for e in errors])
            bot.send_message(call.message.chat.id, error_msg + '\nلطفا اطلاعات را تکمیل یا اصلاح کنید.', reply_markup=get_inline_keyboard(user_id))
            return
        
        info = '\n'.join([f'{k}: {v}' if k != 'دوره انتخابی' else f'{k}: {", ".join([COURSE_CODE_TO_NAME[code] for code in v])}' for k, v in user_data[user_id].items()])
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton('✅ تأیید اطلاعات', callback_data=f'approve_{user_id}'))
        try:
            sent_message = bot.send_message(ADMIN_ID, f'📬 اطلاعات جدید از کاربر {user_id}:\n{info}', reply_markup=markup)
            admin_messages[user_id] = sent_message.message_id
            bot.send_message(call.message.chat.id, '🎉 اطلاعات با موفقیت برای ادمین ارسال شد! منتظر تأیید باشید.')
            bot.send_message(call.message.chat.id, 'برای ادامه، دکمه زیر را بزنید:', reply_markup=get_start_keyboard())
        except Exception as e:
            logger.error(f"خطا در ارسال به ادمین: {e}")
            bot.send_message(call.message.chat.id, '⚠️ خطا در ارسال اطلاعات به ادمین. لطفا دوباره تلاش کنید.')
    
    elif data.startswith('approve_'):
        bot.answer_callback_query(call.id)
        target_user_id = int(data.split('_')[1])
        if call.from_user.id != ADMIN_ID:
            bot.send_message(call.message.chat.id, '⚠️ فقط ادمین می‌تواند اطلاعات را تأیید کند!')
            return
        try:
            # ذخیره زمان تأیید و نام کامل کاربر
            approval_timestamps[target_user_id] = {
                'timestamp': datetime.now(),
                'full_name': f"{user_data.get(target_user_id, {}).get('نام', '')} {user_data.get(target_user_id, {}).get('نام خانوادگی', '')}"
            }
            bot.edit_message_text(f'📬 اطلاعات کاربر {target_user_id}:\n{call.message.text}\n\n✅ تأیید شده توسط ادمین', ADMIN_ID, call.message.message_id)
            bot.send_message(target_user_id, '🎉 اطلاعات شما توسط ادمین تأیید شد!')
            if target_user_id in user_data:
                del user_data[target_user_id]
            if target_user_id in admin_messages:
                del admin_messages[target_user_id]
        except Exception as e:
            logger.error(f"خطا در تأیید اطلاعات توسط ادمین: {e}")
            bot.send_message(call.message.chat.id, '⚠️ خطا در تأیید اطلاعات. لطفا دوباره تلاش کنید.')
    
    elif data == 'exam_time':
        bot.answer_callback_query(call.id)
        if user_id in approval_timestamps:
            approval_time = approval_timestamps[user_id]['timestamp']
            full_name = approval_timestamps[user_id]['full_name']
            exam_date = approval_time + timedelta(days=60)  # 2 ماه بعد
            days_remaining = (exam_date - datetime.now()).days
            if days_remaining < 0:
                days_remaining = 0
            response = f"""
            ⏰ زمان آزمون کتبی من کی هست؟
            
            زمان آزمون شما "{full_name}" بعد از پرداخت حق تعرفه توسط سازمان فنی و حرفه ای تعیین می‌گردد.
            تا زمان تقریبی آزمون شما {days_remaining} روز مانده است. همکاران ما با شما تماس می‌گیرند.
            """
        else:
            response = """
            ⏰ زمان آزمون کتبی من کی هست؟
            
            زمان آزمون شما توسط سازمان فنی و حرفه ای تعیین می‌گردد و معمولا بعد از پرداخت حق تعرفه ۱ الی ۲ ماه زمان خواهد برد.
            """
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=back_to_main_faq_keyboard())
    
    elif data == 'exam_result':
        bot.answer_callback_query(call.id)
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🌐 مشاهده نتیجه آزمون", url="https://azmoon.portaltvto.com/result/result/index/1/80"))
        keyboard.add(InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu"))
        response = """
        📊 نتیجه آزمون کتبی و شرایط قبولی به چه صورت است؟
        
        می‌توانید از طریق سایت فنی و حرفه ای نتیجه آزمون خود را ببینید.
        شرایط قبولی در آزمون کتبی گرفتن حداقل نمره ۵۰ می‌باشد.
        
        در صورت مردودی به بخش شماره تماس مسئول فنی و حرفه مراجعه کنید و هزینه آزمون را پرداخت کنید.
        """
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    
    elif data == 'practical_exam':
        bot.answer_callback_query(call.id)
        response = """
        🔧 آزمون عملی من کی هست؟
        
        آزمون عملی در هر ماه توسط سازمان فنی و حرفه ای تعیین می‌گردد و اطلاع‌رسانی از طریق مسئول فنی و حرفه ای انجام می‌گیرد. تاریخ آزمون عملی شهریورماه به این صورت می‌باشد:
        اگر آزمون کتبی شما در بازه زمانی
        1404/05/16 تا 1404/06/15 بوده است
        آزمون عملی شما در تاریخ 1404/06/26 می‌باشد.
        توجه داشته باشید:
        شرط حضور در آزمون عملی، قبولی در آزمون کتبی است.
        """
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=back_to_main_faq_keyboard())
    
    elif data == 'exam_location':
        bot.answer_callback_query(call.id)
        response = """
        🕘 ساعت آزمون و محل آزمون عملی
        
        ساعت ۹ صبح و در محل آموزشگاه ایده پاژ برگزار می‌گردد.
        نیازی به دریافت کارت ورود به جلسه نمی‌باشد.
        """
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=back_to_main_faq_keyboard())
    
    elif data == 'send_documents':
        bot.answer_callback_query(call.id)
        response = """
        📮 مدارکمو کجا ارسال کنم؟
        
        مدارک خود را به آیدی مسئول فنی و حرفه ای ایده پاژ ارسال کنید:
        
        👤 آیدی: https://t.me/idepazhs
        
        🔹 کارت ملی (یا صفحه اول شناسنامه)
        🔹 برای اتباع (عکس از مدرک حاوی شناسه یکتا)
        🔹 عکس پرسنلی 4*3
        ⭕️ نکات مهم:
        - عکس حداکثر باید مربوط به ۶ ماه گذشته باشد.
        - روی مدرک درج می‌شود، حتما با پس‌زمینه سفید و با کیفیت باشد.
        - بدون مهر، منگنه و پارگی باشد.
        در غیر این صورت عکس شما توسط سازمان فنی و حرفه ای رد خواهد شد و اجازه شرکت در آزمون نخواهید داشت.
        """
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=back_to_main_faq_keyboard())
    
    elif data == 'service_tariff':
        bot.answer_callback_query(call.id)
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🌐 استعلام دهک یارانه‌ای", url="https://sso.mcls.gov.ir/auth/realms/sso/protocol/openid-connect/auth?response_type=code&client_id=hemayat&scope=openid%20profile%20email&state=132&redirect_uri=https://hemayat.mcls.gov.ir/api/sso/auth?provider=REFAH"))
        keyboard.add(InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu"))
        response = """
        💰 تعرفه خدمات آموزشی دولت چیه و چرا باید پرداخت کنم؟
        
        تعرفه خدمات دولت بر اساس دهک‌بندی یارانه‌ای شما می‌باشد. این مصوبه در سال ۱۴۰۴ توسط سازمان فنی و حرفه‌ای به آموزشگاه‌های فنی و حرفه‌ای ابلاغ گردید.
        هزینه تعرفه خدمات آموزشی بستگی به دوره انتخابی شما دارد.
        📊 دهک‌بندی یارانه‌ای:
        • دهک ۱ تا ۵: نیازی به پرداخت تعرفه خدمات آموزشی ندارند.
        • دهک ۶ به بالا: موظف به پرداخت تعرفه می‌باشند.
        برای استعلام دهک یارانه‌ای خود می‌توانید با اطلاعات سرپرست خانوار به لینک زیر مراجعه کنید.
        """
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    
    elif data == 'institute_questions':
        bot.answer_callback_query(call.id)
        response = """
        🏫 سوالات مربوط به موسسه ایده پاژ
        
        لطفا با شماره موسسه تماس بگیرید:
        ساعت اداری ۹ الی ۲۰
        
        📞 05138452386
        📞 05138401556
        """
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=back_to_main_faq_keyboard())
    
    elif data == 'contact_staff':
        bot.answer_callback_query(call.id)
        response = """
        📞 شماره تماس پرسنل ایده پاژ
        
        آقای سهیلی: [09359202990](tel:+989359202990)
        ________________________
        آقای عمرانی: [09355251039](tel:+989355251039)
        ________________________
        آقای سلطانی: [09376255707](tel:+989376255707)
        ________________________
        آقای چهارمحالی: [09152093244](tel:+989152093244)
        ________________________
        آقای ریاضی: [09330761741](tel:+989330761741)
        ________________________
        آقای صالح آبادی: [09389791122](tel:+989389791122)
        ________________________
        آقای اژدری: [09155465113](tel:+989155465113)
        ________________________
        خانم سیار: [09010702940](tel:+989010702940)
        ________________________
        آقای شبرنگی: [09051092940](tel:+989051092940)
        """
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=back_to_main_faq_keyboard())
    
    elif data == 'contact_technical':
        bot.answer_callback_query(call.id)
        response = """
        👨‍💼 شماره تماس مسئول فنی و حرفه‌ای
        
        دینکو: [09301024593](tel:+989301024593)
        
        لطفا در ساعت ۹ الی ۱۴ تماس بگیرید.
        """
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=back_to_main_faq_keyboard())
    
    elif data == 'certificate':
        bot.answer_callback_query(call.id)
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🌐 آموزش نحوه دریافت مدرک", url="https://idepazh.ir/blog/certificate-inquiry"))
        keyboard.add(InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu"))
        response = """
        📜 مدرکم رو چجوری دریافت کنم؟
        
        مدرک شما بعد از قبولی در آزمون کتبی با حداقل نمره ۵۰ و آزمون عملی با حداقل نمره ۷۸ به مدت حداکثر ۴۵ روز زمان خواهد برد.
        
        مدرک شما ۴۵ روز بعد از قبولی در آزمون عملی صادر می‌شود.
        """
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    
    elif data == 'exam_card':
        bot.answer_callback_query(call.id)
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🌐 دریافت کارت ورود به جلسه", url="https://azmoon.portaltvto.com/card/card/index/1/80"))
        keyboard.add(InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu"))
        response = """
        🎫 کارت ورود به جلسه آزمون چجوری دریافت کنم؟
        اطلاعات محل برگزاری آزمون کتبی (ساعت و آدرس) در کارت ورود به جلسه درج شده است.
        لطفا ۱ روز قبل از آزمون اقدام به دانلود کارت کنید.
        """
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    
    elif data == 'card_problem':
        bot.answer_callback_query(call.id)
        today = get_persian_date()
        response = f"""
        ❌ کارت ورود به جلسه دانلود نمیشه؟
        
        به این نکات خوب دقت کنید:
        
        امروز {today}
        
        • اگر تاریخ آزمون شما یک روز قبل از تاریخ امروز می‌باشد لطفا از ساعت ۱۲ به بعد امتحان کنید.
        • در صورتی که باز هم با دریافت کارت مشکل مواجه شدید در روز آزمون ساعت ۷ به آدرس مشهد- میدان نمایشگاه بزرگراه آیت الله هاشمی رفسنجانی میدان خلیج فارس مجیدیه ۳۷- نبش صادقیه ۱۰ مجتمع ثامن(سازمان سنجش) مراجعه کنید.
        
        • حتما قبل از هر اقدام مطمئن شوید آزمون کتبی دارید.
        """
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=back_to_main_faq_keyboard())
    
    elif data == 'sample_questions':
        bot.answer_callback_query(call.id)
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🌐 دریافت نمونه سوالات", url="https://idepazh.ir/sample-professional-technical-questions/"))
        keyboard.add(InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu"))
        response = """
        📝 نمونه سوالات از کجا باید دریافت کنم؟
        
        از طریق لینک زیر دوره خود را انتخاب کنید و نمونه سوالات را بخوانید.
        اطلاعات نمونه سوالات از سازمان سنجش دریافت شده است و مورد تائید سازمان فنی و حرفه ای می‌باشد.
        لطفا توجه داشته باشید نمونه سوالات به صورت کمکی می‌باشد.
        """
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    
    elif data == 'main_menu':
        bot.answer_callback_query(call.id)
        welcome_text = """
        🌟 سلام من پاسخگوی هوشمند آموزشگاه ایده پاژ هستم! 🌟
        برای دریافت پاسخ سوالات خود، یکی از گزینه‌های زیر را انتخاب کنید:
        """
        bot.edit_message_text(welcome_text, call.message.chat.id, call.message.message_id, reply_markup=main_faq_keyboard())

# شروع ربات
if __name__ == "__main__":
    try:
        logger.info("✅ ربات آموزشگاه ایده پاژ در حال اجراست...")
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        logger.error(f"خطای جدی در اجرای ربات: {e}")
