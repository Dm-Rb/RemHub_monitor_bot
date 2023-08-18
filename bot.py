#!/usr/bin/python3
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from support_functions import get_username_from_jira
from custom_classes import Database, UserState
import aioschedule
from messages import messages as mes
from config import Config, load_config
from custom_classes import MonitoringRemzona
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import emoji
from mail import CheckMail

config: Config = load_config()
BOT_TOKEN: str = config.tg_bot.token
SERVER: str = config.tg_bot.token
MONITOR_URL: str = config.site_monitor.monitor_url

storage = MemoryStorage()
data_base = Database('db_sqlite')
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=storage)
monitoring = MonitoringRemzona()
id_messages_callback = {}  # глобальная переменная key = user_id: val = id_messages

inline_btn_1 = InlineKeyboardButton('Я решу эту проблему', callback_data='button1')
inline_kb1 = InlineKeyboardMarkup().add(inline_btn_1)
mail_notific = CheckMail(config)

@dp.message_handler(commands="start")
async def process_start_command(message: types.Message):
    await message.answer(text=mes['start_message'], disable_web_page_preview=True)
    await asyncio.sleep(2)

    if data_base.check_user_id_exist(message.from_user.id):
        await message.answer(text=mes['auth_message_exist'], disable_web_page_preview=True)

    else:
        await UserState.jira_token.set()  # set state
        await message.answer(text=mes['auth_message'], disable_web_page_preview=True)


# If auth successfully
@dp.message_handler(lambda message: bool(get_username_from_jira(message.text)), state=UserState.jira_token)
async def process_auth_success(message: types.Message, state: FSMContext):
    #  record data to db

    user_name, display_name = get_username_from_jira(message.text)
    data_base.add_new_row(user_id=message.from_user.id,
                          jira_token=message.text)

    await state.finish()
    await message.reply(text=f'Аутентификация пройдена, <b>{display_name}</b>!')
    await message.answer(text=mes['auth_success_message'])


# If auth fall
@dp.message_handler(lambda message: not bool(get_username_from_jira(message.text)), state=UserState.jira_token)
async def process_auth_invalid(message: types.Message):

    return await message.reply(text=mes['auth_fall_message'])


@dp.message_handler(commands="del_stop")
async def process_del_command(message: types.Message):
    if data_base.check_user_id_exist(message.from_user.id):
        data_base.del_row(message.from_user.id)
        await message.answer(text=mes['del_yourself_message_true'])
    else:
        await message.answer(text=mes['del_yourself_message_false'])


@dp.message_handler(commands="check_remzona")
async def process_check_remzona_command(message: types.Message):
    keyboard = types.InlineKeyboardMarkup()
    if data_base.check_user_id_exist(message.from_user.id):
        status = data_base.monitoring_remzona_chek_status(message.from_user.id)
        if status:
            text_message = mes['check_remzona_qestion_off']
            button_text = 'Отключить уведомления'
        else:
            text_message = mes['check_remzona_qestion_on']
            button_text = 'Включить уведомления'
        keyboard.add(types.InlineKeyboardButton(text=button_text, callback_data="check_remzona_notific"))
        await message.answer(text_message, reply_markup=keyboard)
    else:
        await message.answer(text='Пройдите авторизацию /auth')


@dp.callback_query_handler(text="check_remzona_notific")
async def process_check_remzona_answer(call: types.CallbackQuery):
    data_base.monitoring_remzona_on_off(call.from_user.id)
    await call.message.answer('Готово')
    await call.answer()


@dp.message_handler()
async def send_notification_to_users():
    message = monitoring.make_request()
    mail_messages = mail_notific.check_mail_box()

    if message:
        users = data_base.get_users_remzona_chek_on()
        for user in users:
            if type(message) == dict:
                counter = message['counter']
                pool = message['pool']
                media = types.MediaGroup()
                text = f"<u>Из {counter} последних запросов зафиксировано с проблемами</u> {len(pool)}:"
                for img in pool:
                    media.attach_photo(types.InputFile(img), caption=text)
                if monitoring.assignee_id == user or (not monitoring.assignee_message):
                    await bot.send_media_group(chat_id=user, media=media)
                    await asyncio.sleep(1)

                # инлайн-кнопка с callback
                if not monitoring.assignee_message:
                    global id_messages_callback
                    msg = await bot.send_message(chat_id=user, text='Готовы устранить неполадки?', reply_markup=inline_kb1)
                    id_messages_callback[user] = msg.message_id

            else:
                await bot.send_message(chat_id=user, text=message, disable_web_page_preview=True)
    if mail_messages:
        users = data_base.get_users_remzona_chek_on()
        for user in users:
            for message in mail_messages:
                await bot.send_message(chat_id=user, text=message)

@dp.callback_query_handler(lambda c: c.data == 'button1')
async def process_callback_button1(callback_query: types.CallbackQuery):
    monitoring.assignee_id = callback_query.from_user.id
    monitoring.assignee_message = True
    global id_messages_callback

    await bot.answer_callback_query(
        callback_query.id,
        text='Все участники были оповещены о том, что вы занялись устранением неполадок', show_alert=True)
    await callback_query.message.delete()

    #  Уведомить всех участников бота о том, что юзер нажал инлайнбатон
    users = data_base.get_users_remzona_chek_on()
    assignee_display_name = data_base.get_display_name(monitoring.assignee_id)
    users.remove(monitoring.assignee_id)

    if users:
        for user in users:
            await bot.send_message(chat_id=user, text=f'{emoji.emojize(":hammer_and_wrench:", language="en")} {assignee_display_name} занялся устранением неполадок')
            await bot.delete_message(chat_id=user, message_id=id_messages_callback.pop(user))



async def scheduler():
    aioschedule.every(60).seconds.do(send_notification_to_users)
    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(1)


async def on_startup(dp):
    asyncio.create_task(scheduler())



if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)
