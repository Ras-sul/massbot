import asyncio, json, os, random, datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command, CommandObject, Text
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.enums import ParseMode

# ── переменные окружения ─────────────────────────────────────────
BOT_TOKEN = os.getenv("7831485774:AAE1aAWOaVXewahPb3GEvCmAh-4prR7ZtHk")                     # токен от @BotFather
ADMIN_ID  = int(os.getenv("6847327581"))        # свой Telegram-ID

# ── загрузка рационов ────────────────────────────────────────────
MEALS = json.loads(Path("meal_plans.json").read_text(encoding="utf-8"))

# ── FSM cостояния опроса ────────────────────────────────────────
class Reg(StatesGroup):
    height = State()
    weight = State()
    goal   = State()

# ── “база данных” в памяти ───────────────────────────────────────
USERS: dict[int, dict] = {}        # {user_id: {height, weight, goal, sub_until, used_ids}}

def get_user(uid: int):
    if uid not in USERS:
        USERS[uid] = {
            "height": 0, "weight": 0, "goal": None,
            "sub_until": datetime.date.today() + datetime.timedelta(days=3),
            "used_ids": set()
        }
    return USERS[uid]

# ── обработчики ──────────────────────────────────────────────────
async def cmd_start(msg: Message, state: FSMContext):
    await msg.answer("Привет! Давай настроим профиль.\nОтправь рост (см):")
    await state.set_state(Reg.height)

async def reg_height(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        return await msg.answer("Число, пожалуйста 🙂")
    user = get_user(msg.from_user.id)
    user["height"] = int(msg.text)
    await msg.answer("Вес (кг):")
    await state.set_state(Reg.weight)

async def reg_weight(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        return await msg.answer("Тоже число 🙂")
    user = get_user(msg.from_user.id)
    user["weight"] = int(msg.text)
    kb = [["Набор массы 💪", "Похудение 🏃‍♂"]]
    await msg.answer("Какая цель?", reply_markup=types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=b)] for b in kb[0]],
        resize_keyboard=True, one_time_keyboard=True))
    await state.set_state(Reg.goal)

async def reg_goal(msg: Message, state: FSMContext):
    user = get_user(msg.from_user.id)
    user["goal"] = "gain" if "Набор" in msg.text else "lose"
    await msg.answer(
        "Готово! У тебя бесплатный доступ на 3 дня.\n"
        "📅 /today — рацион\n💳 /pay — отправить чек\nℹ /left — сколько дней осталось",
        reply_markup=types.ReplyKeyboardRemove())
    await state.clear()

def subscription_active(user):
    return datetime.date.today() <= user["sub_until"]

async def cmd_today(msg: Message):
    user = get_user(msg.from_user.id)
    if not subscription_active(user):
        return await msg.answer("Подписка закончилась. Оплати /pay, чтобы продлить.")

    # выбираем рацион без повторов
    candidates = [m for m in MEALS if m["goal"] == user["goal"] and m["text"] not in user["used_ids"]]
    if not candidates:                      # всё раздали → сброс
        user["used_ids"] = set()
        candidates = [m for m in MEALS if m["goal"] == user["goal"]]

    plan = random.choice(candidates)
    user["used_ids"].add(plan["text"])
    await msg.answer(
        f"<b>🍽 Рацион на сегодня</b> ({plan['calories']} ккал)\n\n"
        f"{plan['text']}\n\n<b>{plan['bju']}</b>",
        parse_mode=ParseMode.HTML)

async def cmd_left(msg: Message):
    user = get_user(msg.from_user.id)
    days = (user["sub_until"] - datetime.date.today()).days
    await msg.answer(f"Дней осталось: {max(days,0)}")

async def cmd_pay(msg: Message):
    await msg.answer("Пришли фото/скрин чека об оплате 1650 тг.")

async def handle_photo(msg: Message, bot: Bot):
    f_id = msg.photo[-1].file_id
    cap  = f"Чек от @{msg.from_user.username or msg.from_user.id}\n/approve_{msg.from_user.id}"
    await bot.send_photo(chat_id=ADMIN_ID, photo=f_id, caption=cap)
    await msg.answer("Чек отправлен администратору. Жди подтверждения ✅")

async def cmd_approve(msg: Message, bot: Bot):
    if msg.from_user.id != ADMIN_ID:
        return
    if not msg.text.startswith("/approve_"):
        return
    user_id = int(msg.text.split("_")[1])
    user = get_user(user_id)
    user["sub_until"] = datetime.date.today() + datetime.timedelta(days=7)
    await bot.send_message(chat_id=user_id, text="✅ Платёж подтверждён! Доступ на 7 дней открыт.")
    await msg.answer("Пользователь одобрен.")

# ── запуск ───────────────────────────────────────────────────────
async def main():
    bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp  = Dispatcher()

    # регистрация
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(reg_height, Reg.height)
    dp.message.register(reg_weight, Reg.weight)
    dp.message.register(reg_goal,   Reg.goal)

    # команды
    dp.message.register(cmd_today, Command("today"))
    dp.message.register(cmd_left,  Command("left"))
    dp.message.register(cmd_pay,   Command("pay"))
    dp.message.register(cmd_approve, F.text.startswith("/approve_"))

    # фото-чек
    dp.message.register(handle_photo, F.photo)

    print("Bot started…")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())