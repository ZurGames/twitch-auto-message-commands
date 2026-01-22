import socket
import time
import os
import json
import requests


class TwitchBot:
    def __init__(self):
        self.irc_server = "irc.chat.twitch.tv"
        self.irc_port = 6667
        self.oauth_token = None
        self.access_token = None  # Токен без oauth: префикса
        self.client_id = None
        self.username = None
        self.channel = None
        self.channel_id = None
        self.user_id = None
        self.sock = None
        self.config_file = "twitch_config.json"

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config
            except:
                return None
        return None

    def save_config(self, username, token, client_id):
        config = {
            'username': username,
            'token': token,
            'client_id': client_id
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f)

    def get_user_id(self, username):
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Client-Id': self.client_id
            }

            response = requests.get(
                f'https://api.twitch.tv/helix/users?login={username}',
                headers=headers,
                timeout=10
            )

            print(f"  DEBUG: Статус ответа API: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if data['data']:
                    user_id = data['data'][0]['id']
                    print(f"  Найден ID для {username}: {user_id}")
                    return user_id
                else:
                    print(f"  DEBUG: Пользователь {username} не найден в ответе")
            else:
                print(f"  DEBUG: Ошибка API: {response.text}")

            return None

        except Exception as e:
            print(f"Ошибка получения ID для {username}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def setup_credentials(self):
        print("\n=== Настройка Twitch Bot ===\n")

        config = self.load_config()

        if config:
            print(f"Найдены сохраненные данные для пользователя: {config['username']}")
            use_saved = input("Использовать сохраненные данные? (да/нет): ").strip().lower()

            if use_saved in ['да', 'yes', 'y', 'д']:
                self.username = config['username']
                token = config['token']
                self.client_id = config.get('client_id', '')

                if token.startswith('oauth:'):
                    self.oauth_token = token
                    self.access_token = token.replace('oauth:', '')
                else:
                    self.oauth_token = f'oauth:{token}'
                    self.access_token = token

                if not self.client_id:
                    print("\nClient ID не найден в сохраненных данных")
                    self.client_id = input("Введите Client ID из twitchtokengenerator.com: ").strip()

                print("Используются сохраненные данные\n")
                return

        print("\nДля получения OAuth токена и Client ID:")
        print("1. Перейдите на: https://twitchtokengenerator.com/")
        print("2. Нажмите 'Connect with Twitch' и авторизуйтесь")
        print("3. Выберите необходимые права:")
        print("   chat:read, chat:edit (для сообщений)")
        print("   moderator:manage:banned_users (для блокировки)")
        print("   moderator:manage:chat_messages (для таймаутов)")
        print("4. Скопируйте 'Access Token' (БЕЗ 'oauth:' префикса)")
        print("5. Скопируйте 'Client ID' (находится там же)\n")

        self.username = input("Введите ваш Twitch никнейм: ").strip().lower()
        token = input("Введите Access Token: ").strip()
        self.client_id = input("Введите Client ID: ").strip()

        if token.startswith('oauth:'):
            self.oauth_token = token
            self.access_token = token.replace('oauth:', '')
        else:
            self.oauth_token = f'oauth:{token}'
            self.access_token = token

        save = input("\nСохранить данные для следующего запуска? (да/нет): ").strip().lower()
        if save in ['да', 'yes', 'y', 'д']:
            self.save_config(self.username, token, self.client_id)
            print("Данные сохранены\n")

    def receive_messages(self, timeout=2):
        self.sock.settimeout(timeout)
        try:
            response = self.sock.recv(2048).decode('utf-8', errors='ignore')
            return response
        except socket.timeout:
            return ""
        except Exception as e:
            print(f"Ошибка получения данных: {e}")
            return ""

    def connect(self):
        """Подключение к Twitch IRC"""
        print(f"Подключение к Twitch IRC...")

        try:
            print("Получение ID пользователя...")
            self.user_id = self.get_user_id(self.username)
            if not self.user_id:
                print("Не удалось получить ID пользователя. Проверьте токен!")
                return False

            print("Получение ID канала...")
            self.channel_id = self.get_user_id(self.channel)
            if not self.channel_id:
                print(f"Не удалось получить ID канала {self.channel}")
                return False

            print(f"ID пользователя: {self.user_id}")
            print(f"ID канала: {self.channel_id}\n")

            self.sock = socket.socket()
            self.sock.settimeout(10)
            self.sock.connect((self.irc_server, self.irc_port))
            self.sock.send(f"PASS {self.oauth_token}\r\n".encode('utf-8'))
            self.sock.send(f"NICK {self.username}\r\n".encode('utf-8'))

            time.sleep(1)
            response = self.receive_messages()

            if "Login authentication failed" in response or "NOTICE" in response:
                print("\nОшибка аутентификации IRC!")
                print("Проверьте правильность токена и никнейма")
                return False

            self.sock.send("CAP REQ :twitch.tv/membership twitch.tv/tags twitch.tv/commands\r\n".encode('utf-8'))
            time.sleep(0.5)

            self.sock.send(f"JOIN #{self.channel}\r\n".encode('utf-8'))
            time.sleep(1)

            response = self.receive_messages()

            if f"JOIN #{self.channel}" in response or f"366" in response:
                print(f"Успешно подключено к каналу #{self.channel}")
                print("Ожидание стабилизации подключения...")
                time.sleep(2)
                print("Готов к работе\n")
                return True
            else:
                print(f"Возможны проблемы с подключением к каналу")
                return True

        except Exception as e:
            print(f"Ошибка подключения: {e}")
            return False

    def send_message(self, message):
        """Отправка сообщения"""
        try:
            msg = f"PRIVMSG #{self.channel} :{message}\r\n"
            self.sock.send(msg.encode('utf-8'))

            response = self.receive_messages(timeout=0.5)
            if "PING" in response:
                pong = response.split("PING ")[1].strip()
                self.sock.send(f"PONG {pong}\r\n".encode('utf-8'))

        except Exception as e:
            print(f"Ошибка отправки сообщения: {e}")

    def ban_user_api(self, target_username, reason=""):
        """Блокировка пользователя"""
        try:
            # Получаем ID целевого пользователя
            target_user_id = self.get_user_id(target_username)

            if not target_user_id:
                print(f"  Не удалось найти пользователя {target_username}")
                return False

            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Client-Id': self.client_id,
                'Content-Type': 'application/json'
            }

            data = {
                'data': {
                    'user_id': target_user_id
                }
            }

            if reason:
                data['data']['reason'] = reason

            response = requests.post(
                f'https://api.twitch.tv/helix/moderation/bans?broadcaster_id={self.channel_id}&moderator_id={self.user_id}',
                headers=headers,
                json=data,
                timeout=10
            )

            if response.status_code in [200, 204]:
                print(f"  Забанен: {target_username}")
                return True
            else:
                print(f"  Ошибка бана {target_username}: {response.status_code}")
                print(f"     Ответ: {response.text}")
                return False

        except Exception as e:
            print(f"  Ошибка при бане {target_username}: {e}")
            return False

    def timeout_user_api(self, target_username, duration=600, reason=""):
        """Тайм-аут пользователя"""
        try:
            target_user_id = self.get_user_id(target_username)

            if not target_user_id:
                print(f"  ✗ Не удалось найти пользователя {target_username}")
                return False

            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Client-Id': self.client_id,
                'Content-Type': 'application/json'
            }

            data = {
                'data': {
                    'user_id': target_user_id,
                    'duration': duration
                }
            }

            if reason:
                data['data']['reason'] = reason

            response = requests.post(
                f'https://api.twitch.tv/helix/moderation/bans?broadcaster_id={self.channel_id}&moderator_id={self.user_id}',
                headers=headers,
                json=data,
                timeout=10
            )

            if response.status_code in [200, 204]:
                print(f"  Таймаут: {target_username} ({duration}с)")
                return True
            else:
                print(f"  Ошибка таймаута {target_username}: {response.status_code}")
                print(f"     Ответ: {response.text}")
                return False

        except Exception as e:
            print(f"  Ошибка при таймауте {target_username}: {e}")
            return False

    def send_file_messages(self, file_path, delay=1.5):
        """Отправка сообщений"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            lines = [line.strip() for line in lines if line.strip()]

            print(f"\nНайдено {len(lines)} непустых строк для отправки")
            print(f"Задержка между сообщениями: {delay} сек")
            print(f"Канал: #{self.channel}\n")

            confirm = input("Начать отправку? (да/нет): ").strip().lower()
            if confirm not in ['да', 'yes', 'y', 'д']:
                print("Отправка отменена")
                return

            print("\n--- Начало отправки ---\n")

            for i, message in enumerate(lines, 1):
                if len(message) > 500:
                    print(f"Строка {i} слишком длинная ({len(message)} символов), обрезаем до 500")
                    message = message[:500]

                print(f"[{i}/{len(lines)}] Отправка: {message[:60]}{'...' if len(message) > 60 else ''}")
                self.send_message(message)

                if i < len(lines):
                    time.sleep(delay)

            print("\n--- Все сообщения отправлены! ---\n")

        except FileNotFoundError:
            print(f"Ошибка: Файл '{file_path}' не найден")
        except Exception as e:
            print(f"Ошибка при чтении файла: {e}")

    def ban_users_from_file(self, file_path, delay=1.5, is_timeout=False, timeout_duration=600):
        """Блокировка пользователей"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            users_to_ban = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                parts = line.split('|')
                username = parts[0].strip().lower()
                reason = parts[1].strip() if len(parts) > 1 else ""
                users_to_ban.append((username, reason))

            action_name = "таймаут" if is_timeout else "бан"
            print(f"\nНайдено {len(users_to_ban)} пользователей для {action_name}а")
            print(f"Задержка между действиями: {delay} сек")
            print(f"Канал: #{self.channel}\n")

            if is_timeout:
                print(f"Длительность таймаута: {timeout_duration} секунд ({timeout_duration // 60} минут)\n")

            print("--- Список пользователей ---")
            for i, (username, reason) in enumerate(users_to_ban, 1):
                reason_text = f" (причина: {reason})" if reason else ""
                print(f"{i}. {username}{reason_text}")
            print("----------------------------\n")

            confirm = input(f"Подтвердите {action_name} этих пользователей (да/нет): ").strip().lower()
            if confirm not in ['да', 'yes', 'y', 'д']:
                print(f"{action_name.capitalize()} отменен")
                return

            print(f"\n--- Начало {action_name}а ---\n")

            success_count = 0
            fail_count = 0

            for i, (username, reason) in enumerate(users_to_ban, 1):
                reason_text = f" (причина: {reason})" if reason else ""
                print(f"[{i}/{len(users_to_ban)}] {action_name.capitalize()}: {username}{reason_text}")

                if is_timeout:
                    result = self.timeout_user_api(username, timeout_duration, reason)
                else:
                    result = self.ban_user_api(username, reason)

                if result:
                    success_count += 1
                else:
                    fail_count += 1

                if i < len(users_to_ban):
                    time.sleep(delay)

            print(f"\n--- Завершено ---")
            print(f"Успешно: {success_count}")
            print(f"Ошибок: {fail_count}\n")

        except FileNotFoundError:
            print(f"Ошибка: Файл '{file_path}' не найден")
        except Exception as e:
            print(f"Ошибка при чтении файла: {e}")

    def disconnect(self):
        if self.sock:
            try:
                self.sock.send(f"PART #{self.channel}\r\n".encode('utf-8'))
                time.sleep(0.5)
                self.sock.close()
                print("Отключено от Twitch\n")
            except:
                pass

    def show_menu(self):
        print("\n" + "=" * 50)
        print("ВЫБЕРИТЕ РЕЖИМ РАБОТЫ:")
        print("=" * 50)
        print("1. Отправка сообщений из файла")
        print("2. Блокировка (Бан) пользователей из файла")
        print("3. Таймаут пользователей из файла")
        print("=" * 50)

        choice = input("\nВведите номер (1-3): ").strip()
        return choice

    def run(self):
        """Основной цикл работы проги"""
        try:
            self.setup_credentials()

            self.channel = input("Введите название канала (без #): ").strip().lower()

            mode = self.show_menu()

            if mode not in ['1', '2', '3']:
                print("Неверный выбор")
                return

            if mode == '1':
                print("\nФормат файла: каждая строка = одно сообщение")
                file_path = input("Введите путь к txt файлу с сообщениями: ").strip().strip('"')
            else:
                print("\nФормат файла:")
                print("  никнейм")
                print("  или")
                print("  никнейм|причина блокировки")
                file_path = input("Введите путь к txt файлу с никнеймами: ").strip().strip('"')

            if not os.path.exists(file_path):
                print(f"\nФайл '{file_path}' не найден!")
                return

            try:
                delay_input = input("Задержка между действиями (сек, по умолчанию 1.5): ").strip()
                delay = float(delay_input) if delay_input else 1.5
                if delay < 1.0:
                    print("Задержка меньше 1 сек может привести к проблемам.")
                    delay = delay
            except ValueError:
                delay = 1.5

            timeout_duration = 600
            if mode == '3':
                try:
                    duration_input = input("Длительность таймаута в секундах (по умолчанию 600 = 10 минут): ").strip()
                    timeout_duration = int(duration_input) if duration_input else 600
                except ValueError:
                    timeout_duration = 600

            if not self.connect():
                print("\nНе удалось подключиться к Twitch")
                return

            if mode == '1':
                self.send_file_messages(file_path, delay)
            elif mode == '2':
                self.ban_users_from_file(file_path, delay, is_timeout=False)
            elif mode == '3':
                self.ban_users_from_file(file_path, delay, is_timeout=True, timeout_duration=timeout_duration)

        except KeyboardInterrupt:
            print("\n\nПрервано пользователем")
        except Exception as e:
            print(f"\nОшибка: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.disconnect()


if __name__ == "__main__":
    print("=" * 50)
    print("  Twitch Bot - Сообщения и Модерация")
    print("=" * 50)

    bot = TwitchBot()
    bot.run()

    input("\nНажмите Enter для выхода...")