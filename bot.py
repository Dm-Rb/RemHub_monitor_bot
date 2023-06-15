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


config: Config = load_config()
BOT_TOKEN: str = config.tg_bot.token
SERVER: str = config.tg_bot.token
MONITOR_URL: str = config.site_monitor.monitor_url

storage = MemoryStorage()
data_base = Database('db_sqlite')
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=storage)
monitoring = MonitoringRemzona()


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

    if message:
        users = data_base.get_users_remzona_chek_on()
        for user in users:
            if type(message) != str:
                await bot.send_media_group(chat_id=user, media=message)

            else:
                await bot.send_message(chat_id=user, text=message, disable_web_page_preview=True)


async def scheduler():
    aioschedule.every(20).seconds.do(send_notification_to_users)
    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(1)


async def on_startup(dp):
    asyncio.create_task(scheduler())


if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)
