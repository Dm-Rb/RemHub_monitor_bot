import sqlite3
from aiogram.dispatcher.filters.state import StatesGroup, State
import requests
from datetime import datetime
import emoji


class UserState(StatesGroup):  # класс для состояний FSM
    jira_token = State()


class Database:

    def __init__(self, db_file):
        self.connection = sqlite3.connect(db_file)
        self.cursor = self.connection.cursor()

        # Создать таблицу, если её нет
        if not bool(self.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users_tokens_data';"
                                        ).fetchone()):
            self.cursor.execute("""
                CREATE TABLE users_tokens_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
                    user_id INTEGER UNIQUE,
                    jira_token TEXT,                
                    remzona_check INTEGER DEFAULT (1));                    
                """)
            self.connection.commit()



    def check_user_id_exist(self, user_id):
        """ Проверить наличие user_id  в базе :return bool """

        with self.connection:
            result = self.cursor.execute(f"SELECT user_id FROM 'users_tokens_data' WHERE user_id = ?", (user_id,)).fetchmany(1)
            return bool(len(result))

    def add_new_row(self, user_id, jira_token):
        """ Добавить новую строку """


        with self.connection:
            return self.cursor.execute(
                "INSERT INTO 'users_tokens_data' ('user_id', 'jira_token') VALUES(?, ?)",
                (user_id, jira_token, ))

    def get_all_data(self):
        """ Достать все записи из БД :return list(tuple1, tuple2, tuple3) | len(tuple) == 4 """

        with self.connection:
            return self.cursor.execute("SELECT user_id, jira_token FROM 'users_tokens_data'").fetchall()


    def del_row(self, user_id):
        """ Удалить строку """

        with self.connection:
            return self.cursor.execute(
                f"DELETE from 'users_tokens_data' WHERE user_id = {user_id}"
            )

    def monitoring_remzona_chek_status(self, user_id):
        with self.connection:
            result = self.cursor.execute(f"SELECT remzona_check FROM 'users_tokens_data' WHERE user_id = ?",
                                         (user_id,)).fetchmany(1)
            return result[0][0]

    def monitoring_remzona_on_off(self, user_id):
        status = self.monitoring_remzona_chek_status(user_id)
        status = int(not bool(status))
        with self.connection:
            return self.cursor.execute(
                f"UPDATE 'users_tokens_data' SET remzona_check={status} WHERE user_id={user_id}"
            )

    def get_users_remzona_chek_on(self):
        with self.connection:
            users = self.cursor.execute(f"SELECT user_id FROM 'users_tokens_data' WHERE remzona_check=1").fetchall()
            result = [i[0] for i in users]
            return result


class MonitoringRemzona:

    URL = 'https://remzona.by/sitemonitor'

    def __init__(self):
        self.pool = []
        self.counter = 0
        self.server_fall = False
        self.average_response_time = []



    def get_text_notification(self, status_code, datetime, response_time):
        if status_code:
            rt = str(round(response_time, 2)) + ' (сек.)'
            if status_code == 200:
                sc = f'{status_code}  ({emoji.emojize(":check_mark_button:", language="en")}Всё ОК)'
            else:
                sc = f'{status_code}  ({emoji.emojize(":exclamation:", language="alias")}Что-то пошло не так, <a href="https://developer.mozilla.org/ru/docs/Web/HTTP/Status">расшифровка кодов ответа сервера</a>)'
        elif status_code == None:
            rt = 'Не удалось связаться с сервером!'
            sc = 'Не удалось связаться с сервером!'

        body_message = f"""
{datetime}
<b>Сайт:</b>   {self.URL}
<b>Время текущего отклика:</b>   {rt}
<b>Среднее время отклика за 5 минут:</b>   {round(self.get_average_response_time(), 2)} (сек)
<b>Код ответа сервера:</b>   {sc}
    """
        if status_code == None:
            header_message = f"{emoji.emojize(':skull_and_crossbones:', language='en')} <b>Сайт не доступен! Всё очень плохо...</b>"
            return str(header_message + '\n' + body_message)

        elif status_code != 200 and response_time >= self.get_average_response_time():
            header_message = f"{emoji.emojize(':exclamation:', language='alias')} <b>Обнаружены проблемы в работе сайта,</b> см. код ответа сервера" + '\n' + f"{emoji.emojize(':clock7:', language='alias')} <b>Сайт слишком долго отвечает на запрос</b>"
            return str(header_message + '\n' + body_message)
        elif status_code != 200:
            header_message = f"{emoji.emojize(':exclamation:', language='alias')} <b>Обнаружены проблемы в работе сайта,</b> см. код ответа сервера"
            return str(header_message + '\n' + body_message)
        elif response_time >= self.get_average_response_time():
            header_message = f"{emoji.emojize(':clock7:', language='alias')} <b>Сайт слишком долго отвечает на запрос</b>"
            return str(header_message + '\n' + body_message)


    def get_average_response_time(self):
        if len(self.average_response_time) > 4:
            self.average_response_time.pop(0)
            art = sum(self.average_response_time) / len(self.average_response_time)
            if art > 1:
                return art
            else:
                return 1
        else:
            return 1

    def make_request(self):
        dt = datetime.now()
        add_null = lambda x: x if len(str(x)) == 2 else '0' + str(x)
        dt = f'<b>Время и дата события:</b>   {add_null(dt.hour)}:{add_null(dt.minute)}:{add_null(dt.second)},  {dt.date()}'
        try:
            r = requests.get(self.URL)
            self.average_response_time.append(r.elapsed.total_seconds())
            response_time = r.elapsed.total_seconds()

        except Exception:
            r = None

        if not self.server_fall:
            try:
                if r.status_code != 200 or r.elapsed.total_seconds() >= self.get_average_response_time():
                    self.server_fall = True
                    message = self.get_text_notification(status_code=r.status_code, datetime=dt,
                                                         response_time=response_time)
                    return message
                else:
                    return None

            except Exception:
                self.server_fall = True
                message = self.get_text_notification(status_code=None, datetime=dt, response_time=None)
                return message

        elif self.server_fall:
            self.counter += 1
            try:
                if r.status_code != 200 or r.elapsed.total_seconds() >= self.get_average_response_time():
                    message = self.get_text_notification(status_code=r.status_code, datetime=dt,
                                                         response_time=response_time)
                    self.pool.append(message)

            except Exception:
                message = self.get_text_notification(status_code=None, datetime=dt, response_time=None)
                self.pool.append(message)

            if self.counter >= 5 and self.pool:
                pool_copy = self.pool.copy()
                self.pool.clear()
                counter_copy = str(self.counter)
                self.counter = 0
                return f"<u>Из {counter_copy} последних запросов зафиксировано проблемных {len(pool_copy)}</u>:" \
                       f"\n\n----------" + '\n----------'.join(pool_copy)

            elif (self.counter >= 5) and (not self.pool):
                self.server_fall = False
                self.counter = 0
                return f'Работа сайта восстановлена {emoji.emojize(":check_mark_button:", language="en")}'






