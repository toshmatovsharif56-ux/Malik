# 🛒 Malik Shop Bot Rules

Telegram бот для верификации пользователей перед доступом к @Malik_Shop_Bot.

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

```bash
python bot.py
```

## Структура файлов

```
malik_shop_bot/
├── bot.py          # Точка входа
├── config.py       # Токен, ID админов, ссылки
├── database.py     # SQLite через aiosqlite
├── handlers.py     # Все обработчики
├── keyboards.py    # Клавиатуры
└── requirements.txt
```

## Функционал

### Пользователь:
1. `/start` → приветствие + кнопки [Правила] [Я согласен]
2. После согласия → запрос номера телефона
3. После отправки контакта → доступ к @Malik_Shop_Bot

### Админ панель (ID: 8351408424, 8429224001):
- Кнопка **Админ панель** появляется только у админов при `/start`
- **Поиск** по username / имени / Telegram ID
- **Список всех** пользователей с пагинацией
- **Карточка пользователя**: ID, имя, username, телефон, дата регистрации, статус

## База данных (malik_shop.db)

Таблица `users`:
| Поле | Описание |
|------|----------|
| user_id | Telegram ID |
| username | @никнейм |
| first_name | Имя |
| last_name | Фамилия |
| phone | Номер телефона |
| agreed_rules | Согласился с правилами (0/1) |
| access_granted | Получил доступ (0/1) |
| registered_at | Дата регистрации |
