
from telegram.ext import CommandHandler, MessageHandler, filters, ApplicationBuilder, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import random

games = {}
questions = [
    "Кто?",
    "С кем?",
    "Когда?",
    "Где?",
    "Что делали?",
    "Зачем?",
    "Что из этого получилось?"
]

def find_game(player_id):
    for key, game in games.items():
        if player_id in game['players'] and game.get('active'):
            return key
    return None

def make_story(games, key):
    # составляем историю из ответов игроков
    story = ""
    players = games[key]['players']
    for i, question in enumerate(questions):
        player = players[i % len(players)]
        answer = games[key]['answers'][player][i]
        story += f"{question} {answer}\n"
    return story

async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("Создать игру", callback_data="create")],
        [InlineKeyboardButton("Вступить в игру", callback_data="join")],
        [InlineKeyboardButton("Инструкция", callback_data="rules")]
    ]
    await update.message.reply_text(
        "Привет! Добро пожаловать в Чепуху!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update, context):
    data = update.callback_query.data
    if data == 'create':
        key = random.randint(1000, 9999)
        host_id = update.callback_query.from_user.id
        games[key] = {
            'host_id': host_id,
            'players': [host_id],
            'names': {host_id: update.callback_query.from_user.first_name},
            'answers': {},
            'current_question': 0,
        }
        keyboard = [[InlineKeyboardButton("Начать игру", callback_data=f"begin_{key}")]]
        await update.callback_query.message.reply_text(
            f"Ключ игры: {key}\nКогда все вступят — нажми Начать игру!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == 'rules':
        await update.callback_query.message.reply_text(
            "📖 Правила игры Чепуха:\n\n"
            "1. Один игрок создаёт игру и делится ключом\n"
            "2. Остальные вступают по ключу\n"
            "3. Хост нажимает Начать игру\n"
            "4. Все отвечают на вопросы не видя ответов других\n"
            "5. В конце получается смешная история!\n\n"
            "Вопросы: Кто? С кем? Когда? Где? Что делали? Зачем? Что получилось?"
        )   

    elif data == 'join':
        context.user_data['state'] = 'waiting_for_key'
        await update.callback_query.message.reply_text("Введите ключ игры:")

    elif data.startswith("begin_"):
        key = int(data.split("_")[1])
        games[key]['active'] = True
        for player_id in games[key]['players']:
            games[key]['answers'][player_id] = []
            await context.bot.send_message(
                chat_id=player_id,
                text=f"Игра началась! Первый вопрос: {questions[0]}"
            )
            del games[key] 
            
    elif data.startswith("story_"):
        # показываем историю когда нажимают кнопку
        key = int(data.split("_")[1])
        index = int(data.split("_")[2])
        if key in games and 'stories' in games[key]:
            await update.callback_query.message.reply_text(
                f"📖 История {index + 1}:\n\n{games[key]['stories'][index]}"
            )

async def receive_key(update, context):
    state = context.user_data.get('state')

    if state == 'waiting_for_key':
        # проверяем что введено число
        if not update.message.text.isdigit():
            await update.message.reply_text('Введите числовой код!')
            return
        key = int(update.message.text)
        if key in games:
            player_id = update.message.from_user.id
            if player_id not in games[key]['players']:
                name = update.message.from_user.username or update.message.from_user.first_name
                games[key]['players'].append(player_id)
                games[key]['names'][player_id] = name
                context.user_data['state'] = None
                host_id = games[key]['host_id']
                # список всех игроков для хоста
                names_list = "\n".join(games[key]['names'].values())
                await update.message.reply_text('Добро пожаловать в игру!')
                await context.bot.send_message(
                    chat_id=host_id,
                    text=f"Игрок {name} вступил!\n\nИгроки:\n{names_list}"
                )
            else:
                await update.message.reply_text('Ты уже в этой игре!')
        else:
            await update.message.reply_text('Игра не найдена, попробуй ещё раз')

    elif find_game(update.message.from_user.id):
        player_id = update.message.from_user.id
        key = find_game(player_id)
        current_q = games[key]['current_question']

        # проверяем что игрок ещё не ответил на этот вопрос
        if len(games[key]['answers'][player_id]) > current_q:
            await update.message.reply_text('Ты уже ответил на этот вопрос!')
            return

        games[key]['answers'][player_id].append(update.message.text)
        await update.message.reply_text('Ответ принят!')

        answered = sum(1 for p in games[key]['answers'] if len(games[key]['answers'][p]) > current_q)
        total = len(games[key]['players'])

        if answered == total:
            games[key]['current_question'] += 1
            if games[key]['current_question'] < len(questions):
                next_q = games[key]['current_question']
                for player_id in games[key]['players']:
                    await context.bot.send_message(
                        chat_id=player_id,
                        text=f"Следующий вопрос: {questions[next_q]}"
                    )
            else:
                # генерируем 3 разные истории
                stories = []
                for _ in range(3):
                    random.shuffle(games[key]['players'])
                    stories.append(make_story(games, key))
                games[key]['stories'] = stories

                # кнопки для выбора истории
                keyboard = [
                    [InlineKeyboardButton(f"История {i+1}", callback_data=f"story_{key}_{i}")]
                    for i in range(len(stories))
                ]
                for player_id in games[key]['players']:
                    await context.bot.send_message(
                        chat_id=player_id,
                        text="🎉 Игра окончена! Выбери историю:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                
import os
app = ApplicationBuilder().token(os.environ["TOKEN"]).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT, receive_key))

print("Бот запущен")
app.run_polling()





