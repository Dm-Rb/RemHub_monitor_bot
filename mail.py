import imaplib
import email



class CheckMail:


    mail_pass = "0MMZZzyK"
    username = "notify@remzona.by"
    imap_server = "imap.yandex.ru"

    def __init__(self, config_obg):
        self.user_name = config_obg.mail.name
        self.password = config_obg.mail.password
        self.imap_server = "imap.yandex.ru"
    def check_mail_box(self):
        imap = imaplib.IMAP4_SSL(self.imap_server)
        imap.login(self.user_name, self.password)
        imap.select("inbox")

        status, response = imap.uid('search', "UNSEEN", "ALL")
        if status == 'OK':
            messages = []
            unread_msg_nums = response[0].split()
            for ms_num in unread_msg_nums:
                res, msg = imap.uid('fetch', ms_num, '(RFC822)')  #Для метода uid
                msg = email.message_from_bytes(msg[0][1])
                for part in msg.walk():
                    if part.get_content_maintype() == 'text' and part.get_content_subtype() == 'plain':
                        message = part.get_payload()
                    else:
                        message = part.get_payload(decode=True).decode()
                        message = message.replace('<div>', '')
                        message = message.replace('</div>', '')
                    text = f"<b>Уведомдение с почты {self.user_name}></b>\n{message}"
                    messages.append(text)
            return messages
