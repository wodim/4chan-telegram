import configparser
import datetime
import logging
import os
import random
import re
import subprocess

import telegram
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

from _4chan import _4chan


logging.basicConfig(format='%(asctime)s - %(name)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

FFMPEG_CMD = 'ffmpeg -hide_banner -i \'{source}\' -preset veryfast \'{dest}\''

_4c = _4chan()
rx_greentext = re.compile(r'^(\\>.*)$', re.MULTILINE)


def _config(k: str):
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config['bot'][k]


def _e(text):
    """escapes text with markdown v2 syntax"""
    return telegram.utils.helpers.escape_markdown(text, 2)


def _webm_convert(file: str) -> str:
    """converts a webm to a mp4 file"""
    new_file = file + '.mp4'
    if os.path.exists(new_file):
        return new_file

    logger.info('converting %s to %s', file, new_file)
    subprocess.call(FFMPEG_CMD.format(source=file, dest=new_file), shell=True)
    if not os.path.exists(new_file):
        raise RuntimeError("for some reason, %s wasn't created" % new_file)

    return new_file


def post_thread(chat_id: int, context: CallbackContext, args: list = None) -> None:
    context.bot.send_chat_action(chat_id=chat_id, action=telegram.ChatAction.TYPING)

    board = args[0] if args else random.choice(_config('boards').split(' '))
    threads = _4c.threads_in_board(board)
    thread = _4c.thread_info(board, random.choice(threads))

    text = ''

    # text = '_%s_\n\n' % _e(thread['image_info'])

    thread_text = thread['text']
    if len(thread_text) > 3000:
        thread_text = thread_text + '…'
    thread_text = rx_greentext.sub(r'_\1_', _e(thread_text))
    if thread['subject'] and thread_text:
        text += '*%s*\n%s' % (_e(thread['subject']), thread_text,)
    elif thread['subject']:
        text = _e(thread['subject'])
    else:
        text = thread_text

    text += '\n\n' + _e(thread['url'])

    if thread['image_url'].endswith('.webm'):
        thread['image_file'] = _webm_convert(thread['image_file'])

    if thread['image_url'].endswith('.gif') or thread['image_url'].endswith('.webm'):
        fun = context.bot.send_document
    else:
        fun = context.bot.send_photo

    with open(thread['image_file'], 'rb') as fp:
        fun(chat_id, fp)
    context.bot.send_message(chat_id, '%s' % text,
                             parse_mode=telegram.constants.PARSEMODE_MARKDOWN_V2,
                             disable_web_page_preview=True)


def cron(context: CallbackContext) -> None:
    if 2 < datetime.datetime.now().astimezone().hour < 10:
        return
    post_thread(int(_config('cron_chat_id')), context)


def command_thread(update: Update, context: CallbackContext) -> None:
    try:
        post_thread(update.message.chat_id, context, context.args)
    except Exception as exc:
        context.bot.send_message(update.message.chat_id, repr(exc))
        raise


def command_help(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Use the /thread command instead of writing garbage here')


def main() -> None:
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(_config('token'))

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler('start', command_help))
    dispatcher.add_handler(CommandHandler('help', command_help))
    dispatcher.add_handler(CommandHandler('thread', command_thread))

    # on non command i.e message - echo the message on Telegram
    # dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, command_help))

    # add a "cron" job that posts automatically every even hour
    first_cron = datetime.datetime.now().astimezone()
    if first_cron.hour % 2 == 0:
        first_cron += datetime.timedelta(hours=2)
    else:
        first_cron += datetime.timedelta(hours=1)
    first_cron = first_cron.replace(minute=0, second=0, microsecond=0)
    print('first cron scheduled for %s' % first_cron.isoformat())
    dispatcher.job_queue.run_repeating(cron, first=first_cron,
                                       interval=60 * 60 * 2)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
