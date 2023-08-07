import datetime
import logging

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, \
    MessageHandler, filters

from checkers import *

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


class Table:
    reference: str
    name: str
    checkers: List[BaseChecker]

    def __init__(self, ref: str, name: str):
        self.reference = ref
        self.name = name
        self.checkers = []

    def add_checker(self, checker):
        self.checkers.append(checker)

    def del_checker(self, checker):
        self.checkers.remove(checker)

    def update(self) -> None:
        for checker in self.checkers:
            checker.update()

    def news(self) -> str:
        return ''.join(checker.answer for checker in self.checkers)

    def test(self) -> None:
        gc.open_by_url(self.reference)


def get_tables_from_user(context: ContextTypes.DEFAULT_TYPE):
    """:returns two dictionaries with tables by name and tables by references"""
    if "tables_by_name" not in context.user_data:
        context.user_data["tables_by_name"] = dict()
        context.user_data["tables_by_ref"] = dict()
    return context.user_data["tables_by_name"], context.user_data["tables_by_ref"]


NAME_CHOOSING, REF_CHOOSING = range(2)


async def start_creating_table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Давайте создадим таблицу.(Для отмены введите /cancel)")
    await update.effective_message.reply_text("Введите имя для таблицы")
    return NAME_CHOOSING


async def get_table_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    tables_by_name = get_tables_from_user(context)[0]
    if name in tables_by_name:
        await update.effective_message.reply_text(
            "Таблица с таким именем уже есть. Выберете другое имя")
        return NAME_CHOOSING
    context.user_data["current_name"] = name
    await update.effective_message.reply_text("Теперь введите ссылку на таблицу")
    return REF_CHOOSING


async def get_table_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ref = update.message.text
    tables_by_ref = get_tables_from_user(context)[1]
    if ref in tables_by_ref:
        await update.effective_message.reply_text(
            f"Таблица с такой ссылкой уже есть. Её имя {tables_by_ref[ref].name}."
            " Чтобы создать новую, введите другую ссылку")
        return REF_CHOOSING
    context.user_data["current_ref"] = ref
    try:
        await create_new_table(update, context)
    except gspread.SpreadsheetNotFound:
        await update.effective_message.reply_text(
            "Эта ссылка не открывается с помощью гугл таблиц."
            " Проверьте её корректность и введите ссылку")
        return REF_CHOOSING
    return ConversationHandler.END


async def create_new_table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create new table"""
    chat_id = update.effective_message.chat_id
    ref, name = context.user_data["current_ref"], context.user_data["current_name"]
    table = Table(ref, name)
    table.test()

    table_by_name, table_by_ref = get_tables_from_user(context)
    table_by_name[name] = table
    context.job_queue.run_repeating(update_table, interval=datetime.timedelta(minutes=1),
                                    chat_id=chat_id,
                                    data=table)
    await update.effective_message.reply_text("Таблица успешно создана!")


async def update_table(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    # await context.bot.send_message(job.chat_id, f"Job with {job.data} has been executed")
    table: Table = job.data
    table.update()
    news = table.news()
    if news:
        await context.bot.send_message(job.chat_id, f"Изменения в таблице {table.name}:\n\n" +
                                       news)


async def help_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Это бот для наблюдением за гугл таблицами. Чтобы следить за таблицей, нужно"
        " создать таблицу и затем создать на неё чекер Чтобы создать таблицу используй команду"
        "/add_table. Чтобы добавить чекер введите команду /add_checker. Чтобы удалить используй"
        " команды /delete_table и /delete_checker."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Привет, это бот для наблюдением за гугл таблицами. Чтобы следить за таблицей, нужно"
        " создать таблицу и затем создать на неё чекер Чтобы создать таблицу используй команду"
        "/add_table. Чтобы добавить чекер введите команду /add_checker. Чтобы удалить используй"
        " команды /delete_table и /delete_checker."
    )


(HOW_TO_CHOOSE_TABLE, TABLE_CHOOSING_BY_REF, TABLE_CHOOSING_BY_NAME, WORKSHEET_CHOOSING,
 TYPE_CHOOSING, TARGET_CHOOSING, CELL, ROW, COLUMN, ALL) = range(10)


async def add_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [["Имя", "Ссылка"]]
    await update.effective_message.reply_text("Будете выбирать таблицу через имя или ссылку?"
                                              "(Для выхода используйте /cancel)",
                                              reply_markup=ReplyKeyboardMarkup(
                                                  reply_keyboard, one_time_keyboard=True))
    return HOW_TO_CHOOSE_TABLE


async def how_to_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    match text:
        case "Имя":
            table_by_name: dict = get_tables_from_user(context)[0]
            await update.effective_message.reply_text("Ваши таблицы:\n" +
                                                      '\n'.join(table_by_name.keys()) + '\n',
                                                      reply_markup=ReplyKeyboardRemove())
            await update.effective_message.reply_text("Выберете имя")
            return TABLE_CHOOSING_BY_NAME
        case "Ссылка":
            table_by_ref: dict = get_tables_from_user(context)[1]
            await update.effective_message.reply_text("Ваши таблицы:\n" +
                                                      '\n'.join(table_by_ref.keys()) + '\n',
                                                      reply_markup=ReplyKeyboardRemove())
            await update.effective_message.reply_text("Выберете ссылку")
            return TABLE_CHOOSING_BY_REF
        case _:
            await update.effective_message.reply_text("Такого варианта нет. Попробуйте ещё",
                                                      reply_markup=ReplyKeyboardRemove())
            return HOW_TO_CHOOSE_TABLE


async def get_checker_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    try:
        context.user_data["current_table"] = get_tables_from_user(context)[0][name]
        await update.effective_message.reply_text("Отлично! Теперь выберете номер листа")
        return WORKSHEET_CHOOSING
    except KeyError:
        await update.effective_message.reply_text("Такой таблицы нет. Попробуйте ещё раз")
        return TABLE_CHOOSING_BY_NAME


async def get_checker_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ref = update.message.text
    try:
        context.user_data["current_table"] = get_tables_from_user(context)[1][ref]
        await update.effective_message.reply_text("Отлично! Теперь выберете номер листа")
        return WORKSHEET_CHOOSING
    except KeyError:
        await update.effective_message.reply_text("Такой таблицы нет. Попробуйте ещё раз")
        return TABLE_CHOOSING_BY_REF


async def get_checker_worksheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        index = int(update.message.text)
        context.user_data["current_worksheet"] = index
        reply_keyboard = [["Одна ячейка", "Строка"], ["Столбец", "Весь лист"]]
        await update.effective_message.reply_text("Теперь выберете тип чекера",
                                                  reply_markup=
                                                  ReplyKeyboardMarkup(reply_keyboard,
                                                                      one_time_keyboard=True))
        return TYPE_CHOOSING
    except ValueError:
        await update.effective_message.reply_text("Используйте цифры")
        return WORKSHEET_CHOOSING


async def get_checker_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.message.text
    match answer:
        case "Одна ячейка":
            await update.effective_message.reply_text("Напишите номер ячейки",
                                                      reply_markup=ReplyKeyboardRemove())
            return CELL
        case "Строка":
            await update.effective_message.reply_text("Напишите номер строки",
                                                      reply_markup=ReplyKeyboardRemove())
            return ROW
        case "Столбец":
            await update.effective_message.reply_text("Напишите номер столбца",
                                                      reply_markup=ReplyKeyboardRemove())
            return COLUMN
        case "Весь лист":
            return ALL
        case _:
            await update.effective_message.reply_text("Такого варианта нет",
                                                      reply_markup=ReplyKeyboardRemove())
            return TYPE_CHOOSING


async def add_cell_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.message.text
    table = context.user_data["current_table"]
    table.add_checker(
        CellChecker(table.reference, context.user_data["current_worksheet"], answer))
    await update.effective_message.reply_text("Готово!")
    return ConversationHandler.END


async def add_row_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = int(update.message.text)
    table = context.user_data["current_table"]
    table.add_checker(
        RowChecker(table.reference, context.user_data["current_worksheet"], answer))
    await update.effective_message.reply_text("Готово!")
    return ConversationHandler.END


async def add_col_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = int(update.message.text)
    table = context.user_data["current_table"]
    table.add_checker(
        ColChecker(table.reference, context.user_data["current_worksheet"], answer))
    await update.effective_message.reply_text("Готово!")
    return ConversationHandler.END


async def add_worksheet_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    table = context.user_data["current_table"]
    table.add_checker(SheetChecker(table.reference, context.user_data["current_worksheet"]))
    await update.effective_message.reply_text("Готово!", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def cancel(message: str = "Хорошо, в другой раз добавим"):
    async def inner(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.effective_message.reply_text(message)
        return ConversationHandler.END

    return inner


async def start_deleting_table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [["Имя", "Ссылка"]]
    await update.effective_message.reply_text("Удалить по ссылке или по имени?"
                                              "(Для отмены /cancel)",
                                              reply_markup=
                                              ReplyKeyboardMarkup(reply_keyboard,
                                                                  one_time_keyboard=True))
    return HOW_TO_CHOOSE_TABLE


async def del_by_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    tables_by_name = get_tables_from_user(context)[0]
    if name not in tables_by_name:
        await update.effective_message.reply_text("Такой таблицы нет. Попробуйте ещё раз")
        return TABLE_CHOOSING_BY_NAME
    del tables_by_name[name]
    await update.effective_message.reply_text("Таблица успешно удалена")
    return ConversationHandler.END


async def del_by_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ref = update.message.text
    tables_by_ref = get_tables_from_user(context)[1]
    if ref not in tables_by_ref:
        await update.effective_message.reply_text("Такой таблицы нет. Попробуйте ещё раз")
        return TABLE_CHOOSING_BY_REF
    del tables_by_ref[ref]
    await update.effective_message.reply_text("Таблица успешно удалена")
    return ConversationHandler.END


async def del_cell_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.message.text
    table = context.user_data["current_table"]
    try:
        table.del_checker(
            CellChecker(table.reference, context.user_data["current_worksheet"], answer))
    except ValueError:
        await update.effective_message.reply_text(
            "Такого чекера нет. Попробуйте ещё раз. Выберете лист таблицы")
        return WORKSHEET_CHOOSING
    await update.effective_message.reply_text("Готово!")
    return ConversationHandler.END


async def del_row_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = int(update.message.text)
    table = context.user_data["current_table"]
    try:
        table.del_checker(
            RowChecker(table.reference, context.user_data["current_worksheet"], answer))
    except ValueError:
        await update.effective_message.reply_text(
            "Такого чекера нет. Попробуйте ещё раз. Выберете лист таблицы")
        return WORKSHEET_CHOOSING
    await update.effective_message.reply_text("Готово!")
    return ConversationHandler.END


async def del_col_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = int(update.message.text)
    table = context.user_data["current_table"]
    try:
        table.del_checker(
            ColChecker(table.reference, context.user_data["current_worksheet"], answer))
    except ValueError:
        await update.effective_message.reply_text(
            "Такого чекера нет. Попробуйте ещё раз. Выберете лист таблицы")
        return WORKSHEET_CHOOSING
    await update.effective_message.reply_text("Готово!")
    return ConversationHandler.END


async def del_worksheet_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    table = context.user_data["current_table"]
    try:
        table.del_checker(SheetChecker(table.reference, context.user_data["current_worksheet"]))
    except ValueError:
        await update.effective_message.reply_text(
            "Такого чекера нет. Попробуйте ещё раз. Выберете лист таблицы")
        return WORKSHEET_CHOOSING
    await update.effective_message.reply_text("Готово!", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


if __name__ == '__main__':
    with open("token.txt") as f:
        app = Application.builder().token(f.readline()).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add_table", start_creating_table)],
        states={
            NAME_CHOOSING: [MessageHandler(filters.TEXT, get_table_name)],
            REF_CHOOSING: [MessageHandler(filters.TEXT, get_table_ref)]
        },
        fallbacks=[CommandHandler("cancel", cancel())]
    )
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_info))
    app.add_handler(CommandHandler("start", start))
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add_checker", add_checker)],
        states={
            HOW_TO_CHOOSE_TABLE: [MessageHandler(filters.TEXT, how_to_choose)],
            TABLE_CHOOSING_BY_NAME: [MessageHandler(filters.TEXT, get_checker_name)],
            TABLE_CHOOSING_BY_REF: [MessageHandler(filters.TEXT, get_checker_ref)],
            WORKSHEET_CHOOSING: [MessageHandler(filters.TEXT, get_checker_worksheet)],
            TYPE_CHOOSING: [MessageHandler(filters.TEXT, get_checker_type)],
            CELL: [MessageHandler(filters.TEXT, add_cell_checker)],
            ROW: [MessageHandler(filters.TEXT, add_row_checker)],
            COLUMN: [MessageHandler(filters.TEXT, add_col_checker)],
            ALL: [MessageHandler(filters.TEXT, add_worksheet_checker)]
        },
        fallbacks=[CommandHandler("cancel", cancel())]
    )
    app.add_handler(conv_handler)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("delete_table", start_deleting_table)],
        states={
            HOW_TO_CHOOSE_TABLE: [MessageHandler(filters.TEXT, how_to_choose)],
            TABLE_CHOOSING_BY_NAME: [MessageHandler(filters.TEXT, del_by_name)],
            TABLE_CHOOSING_BY_REF: [MessageHandler(filters.TEXT, del_by_ref)],
        },
        fallbacks=[CommandHandler("cancel", cancel("Хорошо, в другой раз удалим"))]
    )
    app.add_handler(conv_handler)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("delete_checker", add_checker)],
        states={
            HOW_TO_CHOOSE_TABLE: [MessageHandler(filters.TEXT, how_to_choose)],
            TABLE_CHOOSING_BY_NAME: [MessageHandler(filters.TEXT, get_checker_name)],
            TABLE_CHOOSING_BY_REF: [MessageHandler(filters.TEXT, get_checker_ref)],
            WORKSHEET_CHOOSING: [MessageHandler(filters.TEXT, get_checker_worksheet)],
            TYPE_CHOOSING: [MessageHandler(filters.TEXT, get_checker_type)],
            CELL: [MessageHandler(filters.TEXT, del_cell_checker)],
            ROW: [MessageHandler(filters.TEXT, del_row_checker)],
            COLUMN: [MessageHandler(filters.TEXT, del_col_checker)],
            ALL: [MessageHandler(filters.TEXT, del_worksheet_checker)]
        },
        fallbacks=[CommandHandler("cancel", cancel("Хорошо, в другой раз удалим"))]
    )
    app.add_handler(conv_handler)

    app.run_polling(allowed_updates=Update.ALL_TYPES)
