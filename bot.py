import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import os
from dotenv import load_dotenv
load_dotenv()


import discord

RECEIPT_THREAD_NAME = 'Receipts'
FINANCE_CHANNEL_HINT = 'finance'
BILLING_TIMEZONE = ZoneInfo('America/Chicago')
BILLING_ANCHOR_DAY = 15

TOTAL_PATTERN = re.compile(r'total\s*:?\s*\$\s?([\d,]+(?:\.\d{1,2})?)', re.IGNORECASE)
AMOUNT_PATTERN = re.compile(r'\$\s?([\d,]+(?:\.\d{1,2})?)')


def parse_amount(content):
    total_match = TOTAL_PATTERN.search(content)
    if total_match:
        return float(total_match.group(1).replace(',', ''))
    amounts = AMOUNT_PATTERN.findall(content)
    if amounts:
        return sum(float(a.replace(',', '')) for a in amounts)
    return None


def current_billing_period(now):
    if now.day >= BILLING_ANCHOR_DAY:
        start = now.replace(day=BILLING_ANCHOR_DAY, hour=0, minute=0, second=0, microsecond=0)
    else:
        prev_month = 12 if now.month == 1 else now.month - 1
        prev_year = now.year - 1 if now.month == 1 else now.year
        start = now.replace(year=prev_year, month=prev_month, day=BILLING_ANCHOR_DAY,
                             hour=0, minute=0, second=0, microsecond=0)
    end_month = 1 if start.month == 12 else start.month + 1
    end_year = start.year + 1 if start.month == 12 else start.year
    end = start.replace(year=end_year, month=end_month, day=BILLING_ANCHOR_DAY)
    return start, end


class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))

    async def on_message(self, message):
        if message.author == self.user:
            return

        if not message.content.startswith('$addreceipt'):
            return

        parent = getattr(message.channel, 'parent', None)
        in_receipt_thread = (
            isinstance(message.channel, discord.Thread)
            and message.channel.name == RECEIPT_THREAD_NAME
            and parent is not None
            and FINANCE_CHANNEL_HINT in parent.name.lower()
        )
        if not in_receipt_thread:
            return

        now = datetime.now(BILLING_TIMEZONE)
        start, end = current_billing_period(now)

        total = 0.0
        count = 0
        async for msg in message.channel.history(limit=None, after=start, before=end, oldest_first=True):
            if msg.author == self.user:
                continue
            amount = parse_amount(msg.content)
            if amount is not None:
                total += amount
                count += 1

        label = f"{start.strftime('%b %-d')}–{(end - timedelta(days=1)).strftime('%b %-d')}"
        noun = 'receipt' if count == 1 else 'receipts'
        await message.channel.send(f'Total for {label}: ${total:,.2f} ({count} {noun})')


intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(os.getenv("DISCORD_TOKEN"))
