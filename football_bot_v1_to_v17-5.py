# -*- coding: utf-8 -*-
"""
ربات مدیریت باشگاه فوتبال - نسخه ۱ تا ۱۷
سازگار با python-telegram-bot نسخه 20 به بالا و Python 3 / Pydroid 3

قبل از اجرا:
1) pip install -U python-telegram-bot
2) BOT_TOKEN و ADMIN_IDS و CHANNEL_ID را پایین فایل تنظیم کنید.
3) فایل را با نام football_bot_v1_v2.py ذخیره و اجرا کنید.
"""

import logging
import sqlite3
import secrets
import string
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# ======================== تنظیمات ========================
BOT_TOKEN = "توکن_جدید_را_اینجا_قرار_بده"
ADMIN_IDS = {7514613825}  # شناسه عددی ادمین
CHANNEL_ID = "@juiogfw"  # کانال اطلاع‌رسانی
DB_NAME = "football_manager.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ======================== دیتابیس ========================
def db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS club_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            club_name TEXT NOT NULL,
            city TEXT NOT NULL,
            country TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            UNIQUE(owner_id)
        );
        CREATE TABLE IF NOT EXISTS clubs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL UNIQUE,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            city TEXT NOT NULL,
            country TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            budget INTEGER NOT NULL DEFAULT 0,
            reputation INTEGER NOT NULL DEFAULT 50,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            position TEXT NOT NULL,
            age INTEGER NOT NULL,
            height INTEGER NOT NULL,
            nationality TEXT NOT NULL,
            price INTEGER NOT NULL,
            contract_months INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'market',
            created_at TEXT NOT NULL,
            UNIQUE(first_name, last_name, position, age, nationality)
        );
        CREATE TABLE IF NOT EXISTS club_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL UNIQUE,
            bought_price INTEGER NOT NULL,
            joined_at TEXT NOT NULL,
            loan_from_club_id INTEGER,
            loan_until TEXT,
            FOREIGN KEY(club_id) REFERENCES clubs(id) ON DELETE CASCADE,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            age INTEGER NOT NULL,
            role TEXT NOT NULL,
            style TEXT NOT NULL,
            price INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'market',
            created_at TEXT NOT NULL,
            UNIQUE(first_name, last_name, role)
        );
        CREATE TABLE IF NOT EXISTS club_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER NOT NULL,
            staff_id INTEGER NOT NULL UNIQUE,
            hired_price INTEGER NOT NULL,
            hired_at TEXT NOT NULL,
            FOREIGN KEY(club_id) REFERENCES clubs(id) ON DELETE CASCADE,
            FOREIGN KEY(staff_id) REFERENCES staff(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            amount INTEGER NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(club_id) REFERENCES clubs(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS gift_codes (
            code TEXT PRIMARY KEY COLLATE NOCASE,
            amount INTEGER NOT NULL,
            max_uses INTEGER NOT NULL DEFAULT 1,
            uses INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gift_redemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            redeemed_at TEXT NOT NULL,
            UNIQUE(code, user_id)
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            club_id INTEGER,
            kind TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS club_settings (
            club_id INTEGER PRIMARY KEY,
            stadium TEXT NOT NULL DEFAULT 'ورزشگاه اختصاصی',
            ticket_price INTEGER NOT NULL DEFAULT 200000,
            capacity INTEGER NOT NULL DEFAULT 30000,
            formation TEXT NOT NULL DEFAULT '4-3-3',
            tactics TEXT NOT NULL DEFAULT 'متعادل',
            captain_id INTEGER,
            captain2_id INTEGER,
            captain3_id INTEGER,
            training_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(club_id) REFERENCES clubs(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS club_lineups (
            club_id INTEGER PRIMARY KEY,
            starters TEXT NOT NULL DEFAULT '',
            bench TEXT NOT NULL DEFAULT '',
            saved_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(club_id) REFERENCES clubs(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS lineup_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER NOT NULL,
            slot_number INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            field_position TEXT NOT NULL,
            UNIQUE(club_id, slot_number),
            UNIQUE(club_id, player_id),
            FOREIGN KEY(club_id) REFERENCES clubs(id) ON DELETE CASCADE,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS loan_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            from_club_id INTEGER NOT NULL,
            to_club_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE,
            FOREIGN KEY(from_club_id) REFERENCES clubs(id) ON DELETE CASCADE,
            FOREIGN KEY(to_club_id) REFERENCES clubs(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS transfer_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            seller_club_id INTEGER NOT NULL,
            asking_price INTEGER NOT NULL,
            original_price INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            listed_at TEXT NOT NULL,
            sold_to_club_id INTEGER,
            sold_at TEXT,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE,
            FOREIGN KEY(seller_club_id) REFERENCES clubs(id) ON DELETE CASCADE,
            FOREIGN KEY(sold_to_club_id) REFERENCES clubs(id) ON DELETE SET NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_transfer_active_player ON transfer_listings(player_id) WHERE status='active';
        CREATE TABLE IF NOT EXISTS transfer_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            seller_club_id INTEGER,
            seller_name TEXT NOT NULL,
            buyer_club_id INTEGER NOT NULL,
            buyer_name TEXT NOT NULL,
            price INTEGER NOT NULL,
            transferred_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home_club_id INTEGER NOT NULL,
            away_club_id INTEGER NOT NULL,
            home_goals INTEGER NOT NULL DEFAULT 0,
            away_goals INTEGER NOT NULL DEFAULT 0,
            match_type TEXT NOT NULL DEFAULT 'friendly',
            report TEXT NOT NULL DEFAULT '',
            played_at TEXT NOT NULL,
            FOREIGN KEY(home_club_id) REFERENCES clubs(id) ON DELETE CASCADE,
            FOREIGN KEY(away_club_id) REFERENCES clubs(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS player_conditions (
            player_id INTEGER PRIMARY KEY,
            fitness INTEGER NOT NULL DEFAULT 100,
            yellow_cards INTEGER NOT NULL DEFAULT 0,
            suspended_matches INTEGER NOT NULL DEFAULT 0,
            injury_until TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS club_sponsors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER NOT NULL,
            sponsor_name TEXT NOT NULL,
            monthly_amount INTEGER NOT NULL,
            months_remaining INTEGER NOT NULL DEFAULT 3,
            active INTEGER NOT NULL DEFAULT 1,
            signed_at TEXT NOT NULL,
            FOREIGN KEY(club_id) REFERENCES clubs(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS finance_periods (
            club_id INTEGER PRIMARY KEY,
            last_settlement TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(club_id) REFERENCES clubs(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS club_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER NOT NULL,
            asset_type TEXT NOT NULL CHECK(asset_type IN ('player','staff')),
            asset_id INTEGER NOT NULL,
            monthly_wage INTEGER NOT NULL DEFAULT 0,
            months_total INTEGER NOT NULL DEFAULT 12,
            months_remaining INTEGER NOT NULL DEFAULT 12,
            signing_bonus INTEGER NOT NULL DEFAULT 0,
            release_clause INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            signed_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(club_id) REFERENCES clubs(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_contract_active ON club_contracts(club_id,status,asset_type);
        CREATE TABLE IF NOT EXISTS league_fixtures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season TEXT NOT NULL,
            round_no INTEGER NOT NULL,
            home_club_id INTEGER NOT NULL,
            away_club_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'scheduled',
            home_goals INTEGER,
            away_goals INTEGER,
            played_at TEXT NOT NULL DEFAULT '',
            UNIQUE(season,round_no,home_club_id,away_club_id),
            FOREIGN KEY(home_club_id) REFERENCES clubs(id) ON DELETE CASCADE,
            FOREIGN KEY(away_club_id) REFERENCES clubs(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS planned_substitutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER NOT NULL,
            player_out_id INTEGER NOT NULL,
            player_in_id INTEGER NOT NULL,
            minute INTEGER NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY(club_id) REFERENCES clubs(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS card_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER NOT NULL,
            asset_type TEXT NOT NULL CHECK(asset_type IN ('player','staff')),
            asset_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            card_number TEXT NOT NULL DEFAULT '',
            requested_at TEXT NOT NULL,
            reviewed_at TEXT NOT NULL DEFAULT '',
            reviewer_id INTEGER,
            rejection_reason TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(club_id) REFERENCES clubs(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS stadium_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER NOT NULL,
            stadium_name TEXT NOT NULL,
            capacity INTEGER NOT NULL,
            ticket_price INTEGER NOT NULL,
            pitch_type TEXT NOT NULL,
            roof INTEGER NOT NULL DEFAULT 0,
            floodlights INTEGER NOT NULL DEFAULT 1,
            cost INTEGER NOT NULL,
            duration_days INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            due_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'awaiting_payment',
            delivered_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(club_id) REFERENCES clubs(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS club_lawyers (
            club_id INTEGER PRIMARY KEY,
            lawyer_name TEXT NOT NULL,
            skill INTEGER NOT NULL DEFAULT 60,
            hired_at TEXT NOT NULL,
            FOREIGN KEY(club_id) REFERENCES clubs(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS discipline_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER NOT NULL,
            player_id INTEGER,
            case_type TEXT NOT NULL CHECK(case_type IN ('suspension','fine')),
            reason TEXT NOT NULL,
            suspension_matches INTEGER NOT NULL DEFAULT 0,
            fine_amount INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            appeal_text TEXT NOT NULL DEFAULT '',
            appeal_result TEXT NOT NULL DEFAULT '',
            appealed_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(club_id) REFERENCES clubs(id) ON DELETE CASCADE,
            FOREIGN KEY(player_id) REFERENCES players(id) ON DELETE SET NULL
        );
        """)
        # Migration امن برای ستون‌های دیتابیس‌های قدیمی؛ ستون موجود دوباره اضافه نمی‌شود.
        migrations = {
            'users': {'username': "TEXT NOT NULL DEFAULT ''", 'full_name': "TEXT NOT NULL DEFAULT 'کاربر'", 'created_at': "TEXT NOT NULL DEFAULT ''"},
            'admins': {'user_id': 'INTEGER', 'added_at': "TEXT NOT NULL DEFAULT ''"},
            'clubs': {'owner_id': 'INTEGER', 'name': "TEXT NOT NULL DEFAULT 'باشگاه'", 'city': "TEXT NOT NULL DEFAULT ''", 'country': "TEXT NOT NULL DEFAULT ''", 'password_hash': "TEXT NOT NULL DEFAULT ''", 'budget': 'INTEGER NOT NULL DEFAULT 0', 'reputation': 'INTEGER NOT NULL DEFAULT 50', 'created_at': "TEXT NOT NULL DEFAULT ''"},
            'players': {'photo_file_id': "TEXT NOT NULL DEFAULT ''", 'first_name': "TEXT NOT NULL DEFAULT ''", 'last_name': "TEXT NOT NULL DEFAULT ''", 'position': "TEXT NOT NULL DEFAULT ''", 'age': 'INTEGER NOT NULL DEFAULT 18', 'height': 'INTEGER NOT NULL DEFAULT 175', 'nationality': "TEXT NOT NULL DEFAULT ''", 'price': 'INTEGER NOT NULL DEFAULT 1', 'contract_months': 'INTEGER NOT NULL DEFAULT 12', 'status': "TEXT NOT NULL DEFAULT 'market'", 'created_at': "TEXT NOT NULL DEFAULT ''"},
            'staff': {'first_name': "TEXT NOT NULL DEFAULT ''", 'last_name': "TEXT NOT NULL DEFAULT ''", 'age': 'INTEGER NOT NULL DEFAULT 30', 'role': "TEXT NOT NULL DEFAULT ''", 'style': "TEXT NOT NULL DEFAULT ''", 'price': 'INTEGER NOT NULL DEFAULT 1', 'status': "TEXT NOT NULL DEFAULT 'market'", 'created_at': "TEXT NOT NULL DEFAULT ''"},
            'club_settings': {'captain2_id': 'INTEGER', 'captain3_id': 'INTEGER', 'capacity': 'INTEGER NOT NULL DEFAULT 30000', 'formation': "TEXT NOT NULL DEFAULT '4-3-3'", 'tactics': "TEXT NOT NULL DEFAULT 'متعادل'"},
            'club_contracts': {'release_clause': 'INTEGER NOT NULL DEFAULT 0'},
        }
        for table, columns in migrations.items():
            existing = {r['name'] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
            for column, definition in columns.items():
                if column not in existing:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        # سازگاری با دیتابیس‌های قدیمی: ستون‌های لازم جدول users را اضافه کن
        user_cols = [r["name"] for r in c.execute("PRAGMA table_info(users)").fetchall()]
        if "username" not in user_cols:
            c.execute("ALTER TABLE users ADD COLUMN username TEXT NOT NULL DEFAULT ''")
        if "full_name" not in user_cols:
            c.execute("ALTER TABLE users ADD COLUMN full_name TEXT NOT NULL DEFAULT 'کاربر'")
        if "created_at" not in user_cols:
            c.execute("ALTER TABLE users ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")

        # سازگاری با دیتابیس‌های قدیمی که جدول admins ستون user_id نداشته‌اند
        cols = [r["name"] for r in c.execute("PRAGMA table_info(admins)").fetchall()]
        if "user_id" not in cols:
            c.execute("DROP TABLE admins")
            c.execute("""CREATE TABLE admins (
                user_id INTEGER PRIMARY KEY,
                added_at TEXT NOT NULL
            )""")
        for admin_id in ADMIN_IDS:
            c.execute(
                "INSERT OR IGNORE INTO admins(user_id, added_at) VALUES (?, ?)",
                (admin_id, now())
            )
        # باشگاه‌های آزمایشی قدیمی که هیچ تراکنشی ندارند، بودجه اولیه‌شان صفر شود.
        # باشگاه‌هایی که سابقه مالی دارند دست‌نخورده می‌مانند.
        c.execute("UPDATE clubs SET budget=0 WHERE NOT EXISTS (SELECT 1 FROM transactions t WHERE t.club_id=clubs.id)")
        c.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES ('transfer_window', 'closed')"
        )


def simulate_match(home_id, away_id, home_name, away_name, match_type='friendly'):
    """موتور مسابقه نسخه ۱۳: قدرت ترکیب، آمادگی، کارت، محرومیت، مصدومیت و تعویض خودکار."""
    import random, math
    from datetime import timedelta

    def team_data(club_id):
        with db() as c:
            club = c.execute("SELECT reputation FROM clubs WHERE id=?", (club_id,)).fetchone()
            settings = c.execute("SELECT formation,tactics FROM club_settings WHERE club_id=?", (club_id,)).fetchone()
            line = c.execute("SELECT starters,bench FROM club_lineups WHERE club_id=?", (club_id,)).fetchone()
            ids = []
            bench_ids = []
            if line:
                ids = [int(x) for x in (line['starters'] or '').split(',') if x.strip().isdigit()]
                bench_ids = [int(x) for x in (line['bench'] or '').split(',') if x.strip().isdigit()]
            all_ids = list(dict.fromkeys(ids + bench_ids))
            players = {}
            if all_ids:
                marks = ','.join('?' for _ in all_ids)
                rows = c.execute(f"SELECT p.*,COALESCE(pc.fitness,100) fitness,COALESCE(pc.yellow_cards,0) yellow_cards,COALESCE(pc.suspended_matches,0) suspended_matches,COALESCE(pc.injury_until,'') injury_until FROM players p LEFT JOIN player_conditions pc ON pc.player_id=p.id WHERE p.id IN ({marks})", all_ids).fetchall()
                players = {r['id']: dict(r) for r in rows}
                for pid in all_ids:
                    c.execute("INSERT OR IGNORE INTO player_conditions(player_id,fitness,yellow_cards,suspended_matches,injury_until,updated_at) VALUES(?,100,0,0,'',?)", (pid, now()))
        planned = []
        with db() as c:
            planned = [dict(r) for r in c.execute("SELECT player_out_id,player_in_id,minute FROM planned_substitutions WHERE club_id=? AND active=1 ORDER BY minute,id", (club_id,)).fetchall()]
        return {
            'reputation': int(club['reputation']) if club else 50,
            'formation': settings['formation'] if settings else '4-3-3',
            'tactics': settings['tactics'] if settings else 'متعادل',
            'starters': [players[x] for x in ids if x in players],
            'bench': [players[x] for x in bench_ids if x in players],
            'planned_subs': planned,
        }

    home, away = team_data(home_id), team_data(away_id)
    events = [f"⚽ {match_type == 'league' and 'مسابقه لیگ' or 'بازی دوستانه'}: {home_name} - {away_name}", "داور سوت آغاز را می‌زند."]
    home_goals = away_goals = 0
    total_subs = {home_id: 0, away_id: 0}
    lineups = {home_id: home, away_id: away}
    names = {home_id: home_name, away_id: away_name}
    active = {}
    match_yellows = {}
    red_players = set()
    suspended_this_match = set()
    player_stats = {}

    def player_name(p):
        return f"{p['first_name']} {p['last_name']}"

    # بازیکن مصدوم/محروم از ترکیب اصلی خارج و با نیمکت جایگزین می‌شود.
    for cid, team in lineups.items():
        active[cid] = []
        bench = list(team['bench'])
        for p in team['starters']:
            unavailable = int(p.get('suspended_matches', 0) or 0) > 0
            injury = p.get('injury_until') or ''
            if injury:
                try:
                    unavailable = unavailable or datetime.strptime(injury, '%Y-%m-%d %H:%M:%S') > datetime.now()
                except Exception:
                    unavailable = True
            if unavailable:
                replacement = next((b for b in bench if int(b.get('suspended_matches',0) or 0)==0 and not b.get('injury_until')), None)
                if replacement:
                    bench.remove(replacement)
                    active[cid].append(replacement)
                    events.append(f"پیش از شروع: {player_name(p)} در دسترس نیست؛ {player_name(replacement)} جایگزین شد.")
                    total_subs[cid] += 1
                else:
                    events.append(f"⚠️ {player_name(p)} در دسترس نیست و جایگزین مناسبی روی نیمکت وجود ندارد.")
            else:
                active[cid].append(p)
        team['bench'] = bench
        if not team['starters']:
            events.append(f"⚠️ ترکیب ذخیره‌شده‌ای برای {names[cid]} پیدا نشد؛ قدرت تیم بر اساس اعتبار باشگاه محاسبه می‌شود.")

    def strength(cid):
        team = lineups[cid]
        ps = active[cid]
        if not ps:
            return max(20, team['reputation'] * 0.6)
        vals = []
        for p in ps:
            price = max(1, int(p.get('price', 1) or 1))
            # توان پایه از ارزش بازار، سن و آمادگی؛ بازیکنان در اوج سنی امتیاز بیشتری می‌گیرند.
            val = 28 + min(48, math.log10(price + 1) * 5.4)
            age = int(p.get('age', 28) or 28)
            val += max(-13, min(7, (27 - age) * 0.55))
            val += (int(p.get('fitness', 100) or 100) - 75) * 0.25
            pos = str(p.get('position','')).lower()
            tactic = str(team['tactics'])
            if any(k in pos for k in ('دروازه','goal','gk')): val += 1.5
            if any(k in pos for k in ('مهاجم','فوروارد','striker','forward')) and tactic in ('هجومی','ضدحمله','ضدحمله سریع','بازی مستقیم'): val += 2.5
            if any(k in pos for k in ('مدافع','دفاع','defender','cb','rb','lb')) and tactic in ('دفاعی','دفاع عمیق','بلاک پایین','دفاع فشرده'): val += 2
            if any(k in pos for k in ('هافبک','midfielder','mid')) and tactic in ('مالکانه','تیکی‌تاکا','پاس کوتاه','کنترل ریتم'): val += 2
            vals.append(max(20, min(100, val)))
        tactical = {'هجومی': 4, 'دفاعی': -2, 'متعادل': 0, 'فشار بالا': 3, 'پرس شدید': 3, 'پرس از جلو': 3, 'پرسینگ گگن‌پرس': 3, 'مالکانه': 2, 'تیکی‌تاکا': 2, 'بازی از کناره‌ها': 1.5, 'ارسال از جناحین': 1, 'ضدحمله': 2, 'ضدحمله سریع': 2.5, 'بازی مستقیم': 1, 'دفاع عمیق': -1, 'بلاک پایین': -1, 'دفاع فشرده': -1, 'حفظ نتیجه': -1.5, 'تمرکز بر ضربات ایستگاهی': .8}
        return sum(vals) / len(vals) + (team['reputation'] - 50) * .12 + tactical.get(team['tactics'], 0)

    powers = {home_id: strength(home_id) + 2.5, away_id: strength(away_id)}
    events.append(f"آرایش‌ها: {home_name} ({home['formation']}، {home['tactics']}) | {away_name} ({away['formation']}، {away['tactics']})")
    events.append(f"قدرت تخمینی ترکیب‌ها: {home_name} {powers[home_id]:.0f} - {powers[away_id]:.0f} {away_name}")

    for minute in range(1, 91):
        for cid in (home_id, away_id):
            # تعویض دستی برنامه‌ریزی‌شده توسط مالک؛ تنها اگر هر دو بازیکن حاضر و تعویض قانونی باشد.
            for planned in list(lineups[cid].get('planned_subs', [])):
                if int(planned['minute']) != minute:
                    continue
                out_player = next((p for p in active[cid] if p['id'] == int(planned['player_out_id'])), None)
                in_player = next((p for p in lineups[cid]['bench'] if p['id'] == int(planned['player_in_id'])), None)
                if out_player and in_player and total_subs[cid] < 6:
                    active[cid].remove(out_player); lineups[cid]['bench'].remove(in_player); active[cid].append(in_player)
                    total_subs[cid] += 1
                    events.append(f"دقیقه {minute}: 🔁 تعویض برنامه‌ریزی‌شده {names[cid]}؛ {player_name(out_player)} بیرون رفت و {player_name(in_player)} وارد شد. دستور تاکتیکی مربی اجرا شد.")
                lineups[cid]['planned_subs'].remove(planned)
        for cid in (home_id, away_id):
            # تعویض خودکار به دلیل افت آمادگی؛ حداکثر ۶ تعویض در هر تیم
            tired = next((p for p in active[cid] if int(p.get('fitness',100) or 100) < 48), None)
            if minute >= 60 and total_subs[cid] < 6 and tired and lineups[cid]['bench']:
                replacement = lineups[cid]['bench'].pop(0)
                active[cid].remove(tired); active[cid].append(replacement)
                total_subs[cid] += 1
                events.append(f"دقیقه {minute}: 🔁 تعویض {names[cid]}؛ {player_name(tired)} بیرون، {player_name(replacement)} وارد زمین شد.")

        # رویدادهای انضباطی و مصدومیت
        for cid in (home_id, away_id):
            candidates = [p for p in active[cid] if p['id'] not in red_players]
            if not candidates:
                continue
            # کارت قرمز مستقیم در خطای شدید؛ بازیکن اخراج و برای بازی بعد محروم می‌شود.
            if random.random() < 0.0006:
                p = random.choice(candidates)
                key = p['id']; red_players.add(key); suspended_this_match.add(key)
                if p in active[cid]: active[cid].remove(p)
                with db() as c:
                    c.execute("UPDATE player_conditions SET suspended_matches=MAX(suspended_matches,1),updated_at=? WHERE player_id=?",(now(),key))
                    c.execute("INSERT INTO discipline_cases(club_id,player_id,case_type,reason,suspension_matches,fine_amount,status,created_at) VALUES(?,?,'suspension','کارت قرمز مستقیم در مسابقه',1,0,'active',?)",(cid,key,now()))
                events.append(f"دقیقه {minute}: 🟥 کارت قرمز مستقیم! {player_name(p)} از {names[cid]} اخراج شد و بازی بعد را از دست می‌دهد.")
                candidates = [x for x in active[cid] if x['id'] not in red_players]
            if candidates and random.random() < 0.026:
                p = random.choice(candidates)
                key = p['id']; match_yellows[key] = match_yellows.get(key, 0) + 1
                with db() as c:
                    row = c.execute("SELECT yellow_cards FROM player_conditions WHERE player_id=?", (key,)).fetchone()
                    accumulated = (int(row['yellow_cards']) if row else 0) + 1
                    if match_yellows[key] >= 2:
                        red_players.add(key)
                        suspended_this_match.add(key)
                        if p in active[cid]:
                            active[cid].remove(p)
                        c.execute("UPDATE player_conditions SET suspended_matches=MAX(suspended_matches,1),updated_at=? WHERE player_id=?", (now(),key))
                        c.execute("INSERT INTO discipline_cases(club_id,player_id,case_type,reason,suspension_matches,fine_amount,status,created_at) VALUES(?,?,'suspension','اخراج با دریافت دو کارت زرد در یک مسابقه',1,0,'active',?)", (cid,key,now()))
                        events.append(f"دقیقه {minute}: 🟥 کارت زرد دوم و اخراج {player_name(p)} از {names[cid]}!")
                    elif accumulated >= 4:
                        suspended_this_match.add(key)
                        c.execute("UPDATE player_conditions SET yellow_cards=0,suspended_matches=MAX(suspended_matches,1),updated_at=? WHERE player_id=?", (now(),key))
                        c.execute("INSERT INTO discipline_cases(club_id,player_id,case_type,reason,suspension_matches,fine_amount,status,created_at) VALUES(?,?,'suspension','دریافت چهارمین کارت زرد فصل',1,0,'active',?)", (cid,key,now()))
                        events.append(f"دقیقه {minute}: 🟨 کارت زرد چهارم فصل برای {player_name(p)}؛ محرومیت یک‌بازی ثبت شد.")
                    else:
                        c.execute("UPDATE player_conditions SET yellow_cards=yellow_cards+1,updated_at=? WHERE player_id=?", (now(),key))
                        events.append(f"دقیقه {minute}: 🟨 کارت زرد برای {player_name(p)} ({names[cid]}).")
            if random.random() < 0.004:
                p = random.choice(candidates)
                if p['id'] not in player_stats or not player_stats[p['id']].get('injured'):
                    days = random.choice([2, 3, 5, 7, 14])
                    until = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
                    with db() as c:
                        c.execute("UPDATE player_conditions SET injury_until=?,fitness=MAX(20,fitness-25),updated_at=? WHERE player_id=?", (until,now(),p['id']))
                    player_stats.setdefault(p['id'], {})['injured'] = True
                    events.append(f"دقیقه {minute}: 🩹 مصدومیت {player_name(p)} از {names[cid]}؛ برآورد دوری {days} روز.")
                    if total_subs[cid] < 6 and lineups[cid]['bench']:
                        replacement = lineups[cid]['bench'].pop(0)
                        active[cid].remove(p); active[cid].append(replacement)
                        total_subs[cid] += 1
                        events.append(f"دقیقه {minute}: 🔁 تعویض اجباری؛ {player_name(replacement)} وارد زمین شد.")

        # شانس گل تابع قدرت نسبی، نه صرفاً عدد تصادفی ثابت
        for cid, other in ((home_id, away_id), (away_id, home_id)):
            if len(active[cid]) < 7:
                continue
            diff = max(-20, min(20, powers[cid] - powers[other]))
            chance = max(0.006, min(0.055, 0.021 + diff * 0.00085))
            if random.random() < chance:
                if cid == home_id:
                    home_goals += 1
                else:
                    away_goals += 1
                scorer = None
                if active[cid]:
                    # گلزن با وزن بالاتر برای مهاجمان و بازیکنان با ارزش/توان بیشتر انتخاب می‌شود.
                    weighted=[]
                    for candidate in active[cid]:
                        pos=str(candidate.get('position','')).lower()
                        weight=1.0 + min(2.5, max(0, int(candidate.get('price',1) or 1).bit_length() / 12))
                        if any(k in pos for k in ('مهاجم','فوروارد','striker','forward','wing','وینگر')): weight *= 2.8
                        elif any(k in pos for k in ('هافبک','mid')): weight *= 1.4
                        weighted.extend([candidate] * max(1,int(weight*3)))
                    scorer=random.choice(weighted)
                    player_stats.setdefault(scorer['id'],{})['goals']=player_stats.setdefault(scorer['id'],{}).get('goals',0)+1
                events.append(f"دقیقه {minute}: ⚽ گل برای {names[cid]}" + (f"؛ گلزن: {player_name(scorer)}!" if scorer else "!"))
        # گزارش رویدادمحور هر دقیقه؛ متن بر اساس جریان فرضی بازی و قدرت نسبی دو تیم ساخته می‌شود.
        import random as _rnd
        for cid, other in ((home_id, away_id), (away_id, home_id)):
            side = names[cid]
            attack_power = powers[cid] - powers[other]
            roll = _rnd.random()
            if roll < 0.10:
                events.append(f"دقیقه {minute}: {side} از عقب بازی‌سازی می‌کند؛ هافبک‌ها برای دریافت پاس کوتاه می‌شوند.")
            elif roll < 0.19:
                events.append(f"دقیقه {minute}: {side} توپ را به کناره می‌برد؛ مدافع حریف مسیر ارسال را می‌بندد.")
            elif roll < 0.25:
                events.append(f"دقیقه {minute}: پرس شدید {side} باعث اشتباه در پاس حریف می‌شود و توپ در میانه میدان عوض می‌شود.")
            elif roll < 0.29:
                events.append(f"دقیقه {minute}: حمله سریع {side}؛ مدافعان حریف با برگشت به‌موقع موقعیت را جمع می‌کنند.")
            elif roll < 0.32:
                events.append(f"دقیقه {minute}: ضربه ایستگاهی برای {side}؛ ارسال به محوطه جریمه با ضربه سر دفاع دفع می‌شود.")
            elif roll < 0.34:
                events.append(f"دقیقه {minute}: {side} شوت از پشت محوطه می‌زند؛ توپ از کنار دروازه بیرون می‌رود.")
        if minute in (15, 30, 45, 60, 75, 90):
            events.append(f"دقیقه {minute}: ⏱ گزارش فنی و نتیجه زنده: {home_name} {home_goals}-{away_goals} {away_name}. مربیان در حال ارزیابی فضای پشت مدافعان و افت آمادگی هستند.")

    # کاهش یک مسابقه از محرومیت بازیکنانی که محروم بوده‌اند، بعد از پایان مسابقه
    with db() as c:
        for cid, team in lineups.items():
            # آمادگی بازیکنان حاضر در مسابقه کمی کم می‌شود
            for p in team['starters'] + team['bench'] + active[cid]:
                c.execute("INSERT OR IGNORE INTO player_conditions(player_id,fitness,yellow_cards,suspended_matches,injury_until,updated_at) VALUES(?,100,0,0,'',?)", (p['id'],now()))
                c.execute("UPDATE player_conditions SET fitness=MAX(25,fitness-8),updated_at=? WHERE player_id=?", (now(),p['id']))
            c.execute("UPDATE player_conditions SET suspended_matches=MAX(0,suspended_matches-1),updated_at=? WHERE player_id IN (SELECT cp.player_id FROM club_players cp WHERE cp.club_id=?) AND suspended_matches>0", (now(),cid))
            c.execute("UPDATE planned_substitutions SET active=0 WHERE club_id=? AND active=1", (cid,))
            # محرومیت تازه‌ای که در همین بازی ثبت شده نباید فوراً کم شود.
            if suspended_this_match:
                marks = ','.join('?' for _ in suspended_this_match)
                c.execute(f"UPDATE player_conditions SET suspended_matches=MAX(1,suspended_matches),updated_at=? WHERE player_id IN ({marks})", [now(), *suspended_this_match])
    # امتیاز عملکرد پس از بازی؛ بر پایه ارزش/سن/آمادگی و اثر مستقیم گلزنی
    rating_lines=[]
    for cid in (home_id, away_id):
        roster=[]
        unique_players={}
        for p in (lineups[cid]['starters'] + lineups[cid]['bench'] + active[cid]): unique_players[p['id']]=p
        for p in unique_players.values():
            base=6.0 + min(1.5, math.log10(max(1,int(p.get('price',1) or 1))) / 5)
            base += (int(p.get('fitness',100) or 100)-75)/100
            base += min(2.0, player_stats.get(p['id'],{}).get('goals',0)*1.2)
            if p['id'] in red_players: base-=2.0
            rating=max(3.5,min(10.0,base+random.uniform(-0.8,0.8)))
            roster.append((rating,player_name(p),player_stats.get(p['id'],{}).get('goals',0)))
        if roster:
            roster.sort(reverse=True)
            rating_lines.append(f"⭐ بهترین عملکرد {names[cid]}: " + "، ".join(f"{nm} {rt:.1f}"+(f" ({g} گل)" if g else "") for rt,nm,g in roster[:5]))
    if rating_lines:
        events.append("📊 ارزیابی عملکرد بازیکنان:\n" + "\n".join(rating_lines))
    events.append(f"🔁 تعویض‌های انجام‌شده: {home_name} {total_subs[home_id]} | {away_name} {total_subs[away_id]} (سقف هر تیم: ۶)")
    events.append(f"🏁 پایان مسابقه: {home_name} {home_goals}-{away_goals} {away_name}")
    return home_goals, away_goals, "\n".join(events)


CITY_COORDS = {
    "تهران": (35.6892, 51.3890), "tehran": (35.6892, 51.3890),
    "زنجان": (36.6736, 48.4787), "zanjan": (36.6736, 48.4787),
    "تبریز": (38.0962, 46.2738), "tabriz": (38.0962, 46.2738),
    "قزوین": (36.2688, 50.0041), "qazvin": (36.2688, 50.0041),
    "کرج": (35.8400, 50.9391), "karaj": (35.8400, 50.9391),
    "اصفهان": (32.6546, 51.6680), "isfahan": (32.6546, 51.6680),
    "شیراز": (29.5918, 52.5837), "shiraz": (29.5918, 52.5837),
    "مشهد": (36.2972, 59.6067), "mashhad": (36.2972, 59.6067),
    "اهواز": (31.3183, 48.6706), "ahvaz": (31.3183, 48.6706),
    "رشت": (37.2808, 49.5832), "rasht": (37.2808, 49.5832),
    "ارومیه": (37.5527, 45.0761), "urmia": (37.5527, 45.0761),
    "کرمانشاه": (34.3142, 47.0650), "kermanshah": (34.3142, 47.0650),
    "سنندج": (35.3149, 46.9988), "sanandaj": (35.3149, 46.9988),
    "همدان": (34.7992, 48.5146), "hamedan": (34.7992, 48.5146),
    "اراک": (34.0917, 49.6892), "arak": (34.0917, 49.6892),
    "یزد": (31.8974, 54.3569), "yazd": (31.8974, 54.3569),
    "کرمان": (30.2839, 57.0834), "kerman": (30.2839, 57.0834),
    "بندرعباس": (27.1832, 56.2666), "bandar abbas": (27.1832, 56.2666),
    "ساری": (36.5659, 53.0586), "sari": (36.5659, 53.0586),
    "گرگان": (36.8456, 54.4393), "gorgan": (36.8456, 54.4393),
    "بوشهر": (28.9234, 50.8203), "bushehr": (28.9234, 50.8203),
    "زاهدان": (29.4963, 60.8629), "zahedan": (29.4963, 60.8629),
    "اردبیل": (38.2498, 48.2933), "ardabil": (38.2498, 48.2933),
    "خرم آباد": (33.4878, 48.3558), "khorramabad": (33.4878, 48.3558),
    "بیرجند": (32.8663, 59.2211), "birjand": (32.8663, 59.2211),
    "سمنان": (35.5769, 53.3921), "semnan": (35.5769, 53.3921),
    "کاشان": (33.9850, 51.4100), "kashan": (33.9850, 51.4100),
    "شهرکرد": (32.3256, 50.8644), "shahrekord": (32.3256, 50.8644),
}

def estimate_travel(home_city, home_country, away_city, away_country):
    """برآورد مسافت با مختصات شهرهای شناخته‌شده؛ برای شهر ناشناخته تخمین کشوری."""
    import math
    hc = str(home_city or '').strip().casefold()
    ac = str(away_city or '').strip().casefold()
    hcountry = str(home_country or '').strip().casefold()
    acountry = str(away_country or '').strip().casefold()
    if hc == ac and hcountry == acountry:
        return 0, 'مسیر محلی', 2_000_000, 'فاصله ثبت‌شده: همان شهر'
    hcoord = CITY_COORDS.get(hc)
    acoord = CITY_COORDS.get(ac)
    if hcoord and acoord and hcountry == acountry:
        lat1, lon1 = map(math.radians, hcoord); lat2, lon2 = map(math.radians, acoord)
        dlat, dlon = lat2-lat1, lon2-lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        air_km = 6371 * 2 * math.asin(min(1, math.sqrt(a)))
        road_km = int(air_km * 1.25)
        if road_km <= 450:
            return road_km, 'اتوبوس', int(2_000_000 + road_km*12_000), f'فاصله جاده‌ای تخمینی: {road_km:,} کیلومتر'
        return int(air_km), 'هواپیما', int(12_000_000 + air_km*8_000), f'فاصله هوایی تخمینی: {int(air_km):,} کیلومتر'
    if hcountry == acountry:
        return None, 'اتوبوس/هواپیما (شهر نامشخص)', 8_000_000, 'فاصله دقیق قابل محاسبه نیست؛ شهر در فهرست مختصات نیست'
    return None, 'سفر بین‌المللی/هوایی', 35_000_000, 'مسافت بین‌المللی به دلیل نبود مختصات شهرها تخمینی است'


def match_financials(home_id, away_id):
    """درآمد بلیت میزبان و هزینه سفر مهمان را ثبت می‌کند."""
    notes = []
    with db() as c:
        home = c.execute("SELECT * FROM clubs WHERE id=?", (home_id,)).fetchone()
        away = c.execute("SELECT * FROM clubs WHERE id=?", (away_id,)).fetchone()
        if not home or not away:
            return notes
        st = c.execute("SELECT ticket_price,stadium,capacity FROM club_settings WHERE club_id=?", (home_id,)).fetchone()
        ticket = max(0, int(st['ticket_price'])) if st else 200000
        capacity = max(500, int(st['capacity'] if st and st['capacity'] else 30000))
        attendance = max(500, min(capacity, int(capacity * (0.25 + int(home['reputation']) / 140))))
        income = ticket * attendance
        if income:
            c.execute("UPDATE clubs SET budget=budget+? WHERE id=?", (income, home_id))
            c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)", (home_id, 'درآمد بلیت', income, f"درآمد تخمینی تماشاگران بازی در {st['stadium'] if st else 'ورزشگاه اختصاصی'}؛ {attendance} تماشاگر", now()))
        notes.append(f"🎟 درآمد تخمینی بلیت میزبان: {money(income)} ({attendance:,} تماشاگر)")
        distance_km, mode, travel_cost, distance_note = estimate_travel(home['city'], home['country'], away['city'], away['country'])
        budget = int(away['budget'])
        if budget >= travel_cost:
            c.execute("UPDATE clubs SET budget=budget-? WHERE id=?", (travel_cost, away_id))
            c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)", (away_id, 'هزینه سفر', -travel_cost, f"سفر با {mode} به شهر {home['city']}، {home['country']}؛ {distance_note}", now()))
            notes.append(f"🧳 سفر تیم مهمان: {mode} | {distance_note} | هزینه {money(travel_cost)}")
        else:
            notes.append(f"⚠️ بودجه مهمان برای هزینه سفر {money(travel_cost)} با مسیر {mode} کافی نبود؛ هزینه سفر ثبت نشد. ({distance_note})")
    return notes


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def money(value):
    return f"{int(value):,} تومان"


def is_admin(user_id):
    with db() as c:
        row = c.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,)).fetchone()
        return row is not None or user_id in ADMIN_IDS


def register_user(user):
    full_name = " ".join(x for x in [user.first_name, user.last_name] if x) or "کاربر"
    with db() as c:
        c.execute("""
            INSERT INTO users(user_id, username, full_name, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,
            full_name=excluded.full_name
        """, (user.id, user.username or "", full_name, now()))


def get_club_by_owner(owner_id):
    with db() as c:
        return c.execute("SELECT * FROM clubs WHERE owner_id=?", (owner_id,)).fetchone()


def get_club(club_id):
    with db() as c:
        return c.execute("SELECT * FROM clubs WHERE id=?", (club_id,)).fetchone()


def log_transaction(club_id, kind, amount, description):
    with db() as c:
        c.execute("""
            INSERT INTO transactions(club_id, kind, amount, description, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (club_id, kind, int(amount), description, now()))


def change_budget(club_id, amount, kind, description):
    """هزینه فقط در صورت موجودی کافی؛ مبلغ مثبت درآمد و منفی هزینه است."""
    with db() as c:
        club = c.execute("SELECT budget FROM clubs WHERE id=?", (club_id,)).fetchone()
        if not club:
            return False, "باشگاه پیدا نشد."
        current = int(club["budget"])
        if amount < 0 and current < abs(amount):
            return False, f"💰 موجودی: {money(current)}\n💸 هزینه: {money(abs(amount))}\n❌ بودجه کافی نیست."
        c.execute("UPDATE clubs SET budget=budget+? WHERE id=?", (int(amount), club_id))
        c.execute("""
            INSERT INTO transactions(club_id, kind, amount, description, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (club_id, kind, int(amount), description, now()))
        return True, f"انجام شد.\n💰 موجودی جدید: {money(current + amount)}"


def transfer_window_open():
    with db() as c:
        row = c.execute("SELECT value FROM settings WHERE key='transfer_window'").fetchone()
        return bool(row and row["value"] == "open")


def set_state(context, state, data=None):
    context.user_data["state"] = state
    if data is not None:
        context.user_data["form"] = data
    else:
        context.user_data.pop("form", None)


def main_keyboard(user_id):
    rows = [
        [InlineKeyboardButton("⚽ پنل مالک باشگاه", callback_data="owner")],
        [InlineKeyboardButton("📝 درخواست ثبت باشگاه", callback_data="club_request"),
         InlineKeyboardButton("🎁 کد هدیه", callback_data="gift")],
        [InlineKeyboardButton("✉️ نامه / شکایت / پیشنهاد", callback_data="message_menu")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data="help")]
    ]
    if is_admin(user_id):
        rows.insert(0, [InlineKeyboardButton("🛠 پنل ادمین", callback_data="admin")])
    return InlineKeyboardMarkup(rows)


def back_keyboard(destination="home"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ برگشت", callback_data=destination),
         InlineKeyboardButton("🏠 منوی اصلی", callback_data="home")]
    ])


def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 درخواست‌های باشگاه", callback_data="admin_requests")],
        [InlineKeyboardButton("🏟 باشگاه‌ها / بودجه / جریمه", callback_data="admin_clubs")],
        [InlineKeyboardButton("🔐 رمز باشگاه", callback_data="admin_password")],
        [InlineKeyboardButton("👤 ثبت بازیکن", callback_data="admin_add_player"),
         InlineKeyboardButton("🧑‍💼 ثبت کادر", callback_data="admin_add_staff")],
        [InlineKeyboardButton("🗑 حذف بازیکن/کادر از بازار", callback_data="admin_delete_assets")],
        [InlineKeyboardButton("⚽ بازار بازیکنان", callback_data="market_players"),
         InlineKeyboardButton("🧑‍💼 بازار کادر", callback_data="market_staff")],
        [InlineKeyboardButton("🔄 پنجره نقل‌وانتقالات", callback_data="admin_window")],
        [InlineKeyboardButton("🎁 ساخت کد هدیه", callback_data="admin_gift")],
        [InlineKeyboardButton("📣 ارسال اطلاعیه به کانال", callback_data="admin_announce")],
        [InlineKeyboardButton("📢 پیام همگانی به کاربران", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📨 پیام‌های کاربران", callback_data="admin_messages")],
        [InlineKeyboardButton("🏆 نسخه ۱۰: برگزاری بازی لیگ", callback_data="admin_league_match")],
        [InlineKeyboardButton("🗓 ساخت خودکار برنامه فصل", callback_data="admin_schedule_create")],
        [InlineKeyboardButton("▶️ اجرای بازی بعدی فصل", callback_data="admin_schedule_next")],
        [InlineKeyboardButton("🪪 درخواست‌های کارت بازی", callback_data="admin_cards")],
        [InlineKeyboardButton("⚖️ انضباط و محرومیت بازیکنان", callback_data="admin_discipline")],
        [InlineKeyboardButton("↩️ برگشت", callback_data="home")]
    ])


def owner_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 وضعیت باشگاه", callback_data="club_info"),
         InlineKeyboardButton("💰 بودجه و دفتر مالی", callback_data="club_finance")],
        [InlineKeyboardButton("👥 بازیکنان من", callback_data="my_players"),
         InlineKeyboardButton("🧑‍💼 کادر من", callback_data="my_staff")],
        [InlineKeyboardButton("⚽ بازار بازیکنان", callback_data="market_players"),
         InlineKeyboardButton("🧑‍💼 بازار کادر", callback_data="market_staff")],
        [InlineKeyboardButton("💸 فروش بازیکن", callback_data="sell_player"),
         InlineKeyboardButton("📤 قرض رسمی بازیکن (نسخه ۵)", callback_data="loan_player")],
        [InlineKeyboardButton("🏷 بازیکنان در لیست فروش (نسخه ۷)", callback_data="sale_listings"),
         InlineKeyboardButton("📚 تاریخچه نقل‌وانتقالات (نسخه ۸)", callback_data="transfer_history")],
        [InlineKeyboardButton("↩️ بازگشت بازیکن قرضی", callback_data="loan_return")],
        [InlineKeyboardButton("🔑 تغییر رمز باشگاه", callback_data="change_password")],
        [InlineKeyboardButton("📋 ترکیب و تاکتیک (نسخه ۳)", callback_data="v3_lineup")],
        [InlineKeyboardButton("🏟 ورزشگاه و قیمت بلیت", callback_data="v3_stadium")],
        [InlineKeyboardButton("🏗 ساخت ورزشگاه جدید", callback_data="stadium_build")],
        [InlineKeyboardButton("🪪 درخواست کارت بازی بازیکنان/کادر", callback_data="owner_cards")],
        [InlineKeyboardButton("⚖️ وکیل و اعتراض به محرومیت/جریمه", callback_data="owner_appeals")],
        [InlineKeyboardButton("🏃 تمرین روزانه", callback_data="v3_training")],
        [InlineKeyboardButton("🤝 بازی دوستانه (نسخه ۴)", callback_data="v4_friendly")],
        [InlineKeyboardButton("📜 نتایج بازی‌ها", callback_data="v4_results")],
        [InlineKeyboardButton("🔁 تعویض‌ها، کارت‌ها و مصدومیت (نسخه ۱۳)", callback_data="v13_rules")],
        [InlineKeyboardButton("🧠 مرکز مسابقه و رویدادها (نسخه ۶)", callback_data="v6_match_center")],
        [InlineKeyboardButton("🩺 آمادگی و وضعیت بازیکنان (نسخه ۹)", callback_data="v9_conditions")],
        [InlineKeyboardButton("🏆 جدول لیگ (نسخه ۱۰)", callback_data="v10_standings")],
        [InlineKeyboardButton("🩹 مرکز پزشکی و محرومیت (نسخه ۱۱)", callback_data="v11_medical")],
        [InlineKeyboardButton("📈 گزارش مالی باشگاه (نسخه ۱۲)", callback_data="v12_finance_report")],
        [InlineKeyboardButton("🤝 اسپانسر و درآمد باشگاه (نسخه ۱۴)", callback_data="v14_sponsors")],
        [InlineKeyboardButton("💼 تسویه ماهانه حقوق و اسپانسر", callback_data="v14_settle")],
        [InlineKeyboardButton("📰 کنفرانس خبری پس از آخرین بازی", callback_data="v14_press")],
        [InlineKeyboardButton("🎙 کنفرانس تعاملی و گفت‌وگو با تیم", callback_data="v16_dialogue")],
        [InlineKeyboardButton("📝 قرارداد و مذاکره هوشمند (نسخه ۱۵)", callback_data="v15_contracts")],
        [InlineKeyboardButton("🗓 برنامه کامل فصل لیگ", callback_data="v15_schedule")],
        [InlineKeyboardButton("🔁 برنامه‌ریزی تعویض دستی", callback_data="v15_subs")],
        [InlineKeyboardButton("↩️ برگشت", callback_data="home")]
    ])


async def safe_edit(query, text, markup=None):
    try:
        await query.edit_message_text(text, reply_markup=markup)
    except Exception:
        await query.message.reply_text(text, reply_markup=markup)


async def send_channel(context, text):
    if not CHANNEL_ID or CHANNEL_ID == "@YourChannel":
        return
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text)
    except Exception as e:
        logger.warning("Channel announcement failed: %s", e)


# ======================== دستورات ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    await update.message.reply_text(
        "⚽ به ربات مدیریت فوتبال خوش آمدید.\n"
        "نسخه‌های ۱ تا ۱۷ فعال است: مدیریت باشگاه، مذاکره قراردادی، کارت بازی با تأیید ادمین، ساخت ورزشگاه، انضباط و اعتراض هوشمند، و شبیه‌سازی جزئی مسابقه.",
        reply_markup=main_keyboard(update.effective_user.id)
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_state(context, None)
    await update.message.reply_text("عملیات لغو شد.", reply_markup=main_keyboard(update.effective_user.id))


# ======================== کلیک دکمه‌ها ========================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data
    register_user(q.from_user)

    if data == "home":
        set_state(context, None)
        await safe_edit(q, "🏠 منوی اصلی", main_keyboard(uid))
        return
    if data == "help":
        await safe_edit(q,
            "راهنما:\n"
            "• ابتدا درخواست باشگاه ثبت کنید و منتظر تأیید ادمین بمانید.\n"
            "• بعد از تأیید، از پنل مالک برای خرید بازیکن و کادر استفاده کنید.\n"
            "• خرید، فروش و استخدام فقط در زمان باز بودن پنجره نقل‌وانتقالات ممکن است.\n"
            "• هر هزینه فقط با موجودی کافی انجام می‌شود.\n"
            "• /cancel برای لغو عملیات جاری است.",
            back_keyboard())
        return
    if data == "admin":
        if not is_admin(uid):
            await q.answer("دسترسی ندارید.", show_alert=True); return
        await safe_edit(q, "🛠 پنل مدیریت ادمین", admin_keyboard()); return
    if data == "owner":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "هنوز باشگاهی برای حساب شما تأیید نشده است.\nدرخواست ثبت باشگاه بدهید.",
                            InlineKeyboardMarkup([
                                [InlineKeyboardButton("📝 درخواست باشگاه", callback_data="club_request")],
                                [InlineKeyboardButton("↩️ برگشت", callback_data="home")]
                            ]))
        else:
            await safe_edit(q, f"⚽ پنل مالک: {club['name']}\n💰 بودجه: {money(club['budget'])}", owner_keyboard())
        return

    # ثبت درخواست باشگاه
    if data == "club_request":
        with db() as c:
            existing = c.execute("SELECT status FROM club_requests WHERE owner_id=?", (uid,)).fetchone()
            club = c.execute("SELECT id FROM clubs WHERE owner_id=?", (uid,)).fetchone()
        if club:
            await safe_edit(q, "شما از قبل باشگاه تأییدشده دارید.", back_keyboard()); return
        if existing and existing["status"] == "pending":
            await safe_edit(q, "درخواست شما در انتظار بررسی ادمین است.", back_keyboard()); return
        set_state(context, "club_name", {})
        await safe_edit(q, "نام باشگاه را بفرستید:", back_keyboard())
        return

    if data == "message_menu":
        await safe_edit(q, "نوع پیام را انتخاب کنید:", InlineKeyboardMarkup([
            [InlineKeyboardButton("✉️ نامه", callback_data="msg_letter"),
             InlineKeyboardButton("🚨 شکایت", callback_data="msg_complaint")],
            [InlineKeyboardButton("💡 پیشنهاد", callback_data="msg_suggestion")],
            [InlineKeyboardButton("↩️ برگشت", callback_data="home")]
        ])); return
    if data in ("msg_letter", "msg_complaint", "msg_suggestion"):
        set_state(context, "user_message", {"kind": data[4:]})
        await safe_edit(q, "متن پیام خود را بفرستید:", back_keyboard("message_menu")); return

    if data == "gift":
        set_state(context, "redeem_gift")
        await safe_edit(q, "کد هدیه را وارد کنید:", back_keyboard()); return

    # نسخه ۱۷: کارت بازی رسمی با تأیید ادمین
    if data == "owner_cards":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        with db() as c:
            players = c.execute("SELECT p.id,p.first_name,p.last_name,p.position,p.age,p.nationality,p.photo_file_id FROM club_players cp JOIN players p ON p.id=cp.player_id WHERE cp.club_id=? ORDER BY p.id", (club['id'],)).fetchall()
            staff = c.execute("SELECT s.id,s.first_name,s.last_name,s.role,s.age FROM club_staff cs JOIN staff s ON s.id=cs.staff_id WHERE cs.club_id=? ORDER BY s.id", (club['id'],)).fetchall()
            existing = {(r['asset_type'],r['asset_id']):r['status'] for r in c.execute("SELECT asset_type,asset_id,status FROM card_requests WHERE club_id=?", (club['id'],)).fetchall()}
        kb=[]; lines=["🪪 درخواست صدور کارت رسمی باشگاه", "اطلاعات از همان بازیکن/عضو کادر ثبت‌شده در باشگاه گرفته می‌شود. ادمین درخواست را بررسی و تأیید می‌کند.", ""]
        for x in players:
            st=existing.get(('player',x['id']))
            label = "در انتظار" if st=='pending' else ("صادر شده" if st=='approved' else "درخواست کارت")
            lines.append(f"⚽ #{x['id']} {x['first_name']} {x['last_name']} | {x['position']} | {label}")
            if st not in ('pending','approved'):
                kb.append([InlineKeyboardButton(f"🪪 کارت بازیکن {x['first_name']} {x['last_name']}", callback_data=f"request_card_player_{x['id']}")])
        for x in staff:
            st=existing.get(('staff',x['id']))
            label = "در انتظار" if st=='pending' else ("صادر شده" if st=='approved' else "درخواست کارت")
            lines.append(f"🧑‍💼 #{x['id']} {x['first_name']} {x['last_name']} | {x['role']} | {label}")
            if st not in ('pending','approved'):
                kb.append([InlineKeyboardButton(f"🪪 کارت کادر {x['first_name']} {x['last_name']}", callback_data=f"request_card_staff_{x['id']}")])
        if not players and not staff: lines.append("هنوز بازیکن یا عضو کادری در باشگاه ندارید.")
        kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="owner")])
        await safe_edit(q,"\n".join(lines)[:3900],InlineKeyboardMarkup(kb)); return

    if data.startswith("request_card_player_") or data.startswith("request_card_staff_"):
        club=get_club_by_owner(uid)
        if not club: await safe_edit(q,"باشگاه پیدا نشد.",back_keyboard("home")); return
        typ='player' if data.startswith('request_card_player_') else 'staff'
        aid=int(data.rsplit('_',1)[1]); table='players' if typ=='player' else 'staff'; link='club_players' if typ=='player' else 'club_staff'; key='player_id' if typ=='player' else 'staff_id'
        with db() as c:
            asset=c.execute(f"SELECT a.* FROM {table} a JOIN {link} x ON x.{key}=a.id WHERE a.id=? AND x.club_id=?",(aid,club['id'])).fetchone()
            prior=c.execute("SELECT status FROM card_requests WHERE club_id=? AND asset_type=? AND asset_id=? ORDER BY id DESC LIMIT 1",(club['id'],typ,aid)).fetchone()
            if asset and (not prior or prior['status']=='rejected'):
                c.execute("INSERT INTO card_requests(club_id,asset_type,asset_id,status,requested_at) VALUES(?,?,?,'pending',?)",(club['id'],typ,aid,now()))
                reqid=c.execute("SELECT last_insert_rowid() id").fetchone()['id']
            else: reqid=None
        if not asset: await safe_edit(q,"این بازیکن/عضو کادر در باشگاه شما نیست.",back_keyboard("owner_cards")); return
        if not reqid: await safe_edit(q,"برای این فرد قبلاً درخواست فعال یا کارت صادرشده وجود دارد.",back_keyboard("owner_cards")); return
        for aid_admin in ADMIN_IDS:
            try: await context.bot.send_message(aid_admin,f"🪪 درخواست صدور کارت بازی جدید\nباشگاه: {club['name']} (#{club['id']})\nنوع: {'بازیکن' if typ=='player' else 'کادر فنی'}\nنام: {asset['first_name']} {asset['last_name']}\nشناسه پرونده: {reqid}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تأیید و صدور کارت",callback_data=f"card_approve_{reqid}"),InlineKeyboardButton("❌ رد درخواست",callback_data=f"card_reject_{reqid}")]]))
            except Exception: pass
        await safe_edit(q,"✅ درخواست کارت ارسال شد. پس از بررسی ادمین، کارت با شماره رسمی و مشخصات ثبت‌شده صادر می‌شود.",back_keyboard("owner_cards")); return

    if data == "admin_cards":
        if not is_admin(uid): await q.answer("فقط ادمین.",show_alert=True); return
        with db() as c:
            rows=c.execute("SELECT cr.*,cl.name club_name,cl.owner_id,p.first_name pfirst,p.last_name plast,p.position,p.age,p.height,p.nationality,p.photo_file_id,s.first_name sfirst,s.last_name slast,s.role,s.age sage FROM card_requests cr JOIN clubs cl ON cl.id=cr.club_id LEFT JOIN players p ON cr.asset_type='player' AND p.id=cr.asset_id LEFT JOIN staff s ON cr.asset_type='staff' AND s.id=cr.asset_id WHERE cr.status='pending' ORDER BY cr.id").fetchall()
        kb=[]; lines=["🪪 درخواست‌های کارت بازی در انتظار تأیید",""]
        for r in rows:
            nm=(f"{r['pfirst']} {r['plast']}" if r['asset_type']=='player' else f"{r['sfirst']} {r['slast']}")
            lines.append(f"#{r['id']} | {r['club_name']} | {nm} | {'بازیکن' if r['asset_type']=='player' else 'کادر'}")
            kb.append([InlineKeyboardButton(f"✅ صدور #{r['id']}",callback_data=f"card_approve_{r['id']}"),InlineKeyboardButton(f"❌ رد #{r['id']}",callback_data=f"card_reject_{r['id']}")])
        if not rows: lines.append("درخواستی در انتظار نیست.")
        kb.append([InlineKeyboardButton("↩️ برگشت",callback_data="admin")])
        await safe_edit(q,"\n".join(lines)[:3900],InlineKeyboardMarkup(kb)); return

    if data.startswith("card_approve_") or data.startswith("card_reject_"):
        if not is_admin(uid): await q.answer("فقط ادمین.",show_alert=True); return
        rid=int(data.rsplit('_',1)[1]); approve=data.startswith('card_approve_')
        with db() as c:
            r=c.execute("SELECT cr.*,cl.name club_name,cl.owner_id,p.first_name pfirst,p.last_name plast,p.position,p.age,p.height,p.nationality,p.photo_file_id,s.first_name sfirst,s.last_name slast,s.role,s.age sage FROM card_requests cr JOIN clubs cl ON cl.id=cr.club_id LEFT JOIN players p ON cr.asset_type='player' AND p.id=cr.asset_id LEFT JOIN staff s ON cr.asset_type='staff' AND s.id=cr.asset_id WHERE cr.id=? AND cr.status='pending'",(rid,)).fetchone()
            if not r: await safe_edit(q,"درخواست پیدا نشد یا قبلاً بررسی شده است.",back_keyboard('admin_cards')); return
            if approve:
                cardno=f"FM-{datetime.now().year}-{r['club_id']:04d}-{'P' if r['asset_type']=='player' else 'S'}-{r['asset_id']:05d}"
                c.execute("UPDATE card_requests SET status='approved',card_number=?,reviewed_at=?,reviewer_id=? WHERE id=?",(cardno,now(),uid,rid))
            else:
                cardno=''; c.execute("UPDATE card_requests SET status='rejected',reviewed_at=?,reviewer_id=?,rejection_reason='رد توسط ادمین' WHERE id=?",(now(),uid,rid))
        if approve:
            if r['asset_type']=='player':
                nm=f"{r['pfirst']} {r['plast']}"; detail=f"🪪 کارت رسمی بازیکن\nنام کامل: {nm}\nباشگاه: {r['club_name']}\nپست: {r['position']}\nسن: {r['age']}\nقد: {r['height']} سانتی‌متر\nملیت: {r['nationality']}\nشماره کارت: {cardno}\nوضعیت: معتبر"; photo=r['photo_file_id']
            else:
                nm=f"{r['sfirst']} {r['slast']}"; detail=f"🪪 کارت رسمی کادر فنی\nنام کامل: {nm}\nباشگاه: {r['club_name']}\nسمت: {r['role']}\nسن: {r['sage']}\nشماره کارت: {cardno}\nوضعیت: معتبر"; photo=''
            try:
                if photo: await context.bot.send_photo(r['owner_id'],photo=photo,caption=detail[:1000])
                else: await context.bot.send_message(r['owner_id'],detail)
            except Exception: pass
            await safe_edit(q,f"✅ کارت صادر شد: {nm} | {cardno}",back_keyboard('admin_cards'))
        else:
            try: await context.bot.send_message(r['owner_id'],f"❌ درخواست کارت {r['asset_type']} برای باشگاه {r['club_name']} رد شد. می‌توانید مشخصات را اصلاح و دوباره درخواست بدهید.")
            except Exception: pass
            await safe_edit(q,"❌ درخواست کارت رد شد.",back_keyboard('admin_cards'))
        return

    # ساخت ورزشگاه با برآورد هزینه و مدت و تحویل پس از موعد
    if data == "stadium_build":
        club=get_club_by_owner(uid)
        if not club: await safe_edit(q,"باشگاه تأییدشده ندارید.",back_keyboard('home')); return
        project=finish_stadium_if_due(club['id'])
        if project and project['status']=='under_construction':
            await safe_edit(q,f"🏗 ورزشگاه در حال ساخت: {project['stadium_name']}\nظرفیت: {project['capacity']:,} نفر\nتحویل برنامه‌ریزی‌شده: {project['due_at']}\nپس از پایان زمان، دوباره همین بخش را باز کنید تا تحویل ثبت شود.",back_keyboard('owner')); return
        set_state(context,'stadium_build_form',{'club_id':club['id']})
        await safe_edit(q,"🏗 فرم ساخت ورزشگاه\nیک خط با این قالب بفرستید:\nنام ورزشگاه | ظرفیت (۵۰۰ تا ۱۵۰۰۰۰) | قیمت بلیت | نوع چمن (طبیعی/مصنوعی/هیبریدی) | سقف (بله/خیر) | نورافکن (بله/خیر) | مدت ساخت به روز (۱ تا ۹۰)\nمثال: ورزشگاه آفتاب | 30000 | 350000 | چمن طبیعی | بله | بله | 4\nهزینه برآوردی بازی محاسبه می‌شود؛ قبل از شروع از شما تأیید می‌گیرد.",back_keyboard('owner')); return
    if data == "stadium_build_confirm":
        club=get_club_by_owner(uid); form=context.user_data.get('pending_stadium')
        if not club or not form or int(form.get('club_id',-1))!=club['id']:
            await safe_edit(q,"فرم ساخت منقضی شده؛ دوباره شروع کنید.",back_keyboard('owner')); return
        cost=int(form['cost'])
        with db() as c:
            current=c.execute("SELECT budget FROM clubs WHERE id=?",(club['id'],)).fetchone()['budget']
            if int(current)<cost:
                await safe_edit(q,f"❌ بودجه کافی نیست. هزینه ساخت {money(cost)} و بودجه فعلی {money(current)} است.",back_keyboard('stadium_build')); return
            c.execute("UPDATE clubs SET budget=budget-? WHERE id=?",(cost,club['id']))
            c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)",(club['id'],'ساخت ورزشگاه',-cost,f"ساخت {form['stadium_name']}، ظرفیت {form['capacity']}",now()))
            from datetime import timedelta
            due=(datetime.now()+timedelta(days=int(form['duration_days']))).strftime('%Y-%m-%d %H:%M:%S')
            c.execute("UPDATE stadium_projects SET status='cancelled' WHERE club_id=? AND status='under_construction'",(club['id'],))
            c.execute("INSERT INTO stadium_projects(club_id,stadium_name,capacity,ticket_price,pitch_type,roof,floodlights,cost,duration_days,started_at,due_at,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,'under_construction')",(club['id'],form['stadium_name'],form['capacity'],form['ticket_price'],form['pitch_type'],form['roof'],form['floodlights'],cost,form['duration_days'],now(),due))
        context.user_data.pop('pending_stadium',None); set_state(context,None)
        await safe_edit(q,f"🏗 ساخت ورزشگاه شروع شد!\nنام: {form['stadium_name']}\nهزینه پرداخت‌شده: {money(cost)}\nمدت ساخت: {form['duration_days']} روز\nتحویل برنامه‌ریزی‌شده: {due}\nبرای تحویل پس از موعد، دوباره بخش «ساخت ورزشگاه» را باز کنید.",back_keyboard('owner')); return

    # انضباط و محرومیت‌های صادرشده توسط ادمین
    if data == "admin_discipline":
        if not is_admin(uid): await q.answer("فقط ادمین.",show_alert=True); return
        with db() as c:
            rows=c.execute("SELECT p.id,p.first_name,p.last_name,cl.id club_id,cl.name club_name FROM players p JOIN club_players cp ON cp.player_id=p.id JOIN clubs cl ON cl.id=cp.club_id ORDER BY cl.id,p.id").fetchall()
        kb=[[InlineKeyboardButton(f"🚫 {r['club_name']}: {r['first_name']} {r['last_name']} (#{r['id']})",callback_data=f"admin_suspend_player_{r['id']}")] for r in rows]
        kb.append([InlineKeyboardButton("↩️ برگشت",callback_data='admin')])
        await safe_edit(q,"⚖️ انتخاب بازیکن برای محرومیت\nبعد از انتخاب، علت و تعداد بازی محرومیت را وارد می‌کنید.",InlineKeyboardMarkup(kb)); return
    if data.startswith('admin_suspend_player_'):
        if not is_admin(uid): await q.answer("فقط ادمین.",show_alert=True); return
        pid=int(data.rsplit('_',1)[1])
        with db() as c:
            r=c.execute("SELECT p.first_name,p.last_name,cp.club_id,cl.owner_id,cl.name club_name FROM players p JOIN club_players cp ON cp.player_id=p.id JOIN clubs cl ON cl.id=cp.club_id WHERE p.id=?",(pid,)).fetchone()
        if not r: await safe_edit(q,"بازیکن در باشگاهی پیدا نشد.",back_keyboard('admin_discipline')); return
        set_state(context,'admin_suspend_details',{'player_id':pid,'club_id':r['club_id'],'owner_id':r['owner_id'],'club_name':r['club_name'],'player_name':r['first_name']+' '+r['last_name']})
        await safe_edit(q,f"محرومیت برای {r['first_name']} {r['last_name']}\nعلت و تعداد بازی را به شکل زیر بفرستید:\nعلت | تعداد بازی\nمثال: رفتار خشونت‌آمیز | 2",back_keyboard('admin_discipline')); return

    if data == "owner_appeals":
        club=get_club_by_owner(uid)
        if not club: await safe_edit(q,"باشگاه تأییدشده ندارید.",back_keyboard('home')); return
        with db() as c:
            lawyer=c.execute("SELECT * FROM club_lawyers WHERE club_id=?",(club['id'],)).fetchone()
            cases=c.execute("SELECT dc.*,p.first_name,p.last_name FROM discipline_cases dc LEFT JOIN players p ON p.id=dc.player_id WHERE dc.club_id=? ORDER BY dc.id DESC LIMIT 15",(club['id'],)).fetchall()
        kb=[]
        if not lawyer:
            kb += [[InlineKeyboardButton("⚖️ استخدام وکیل هوشمند (۵۰ میلیون تومان)",callback_data='lawyer_hire')]]
        else:
            kb += [[InlineKeyboardButton(f"⚖️ وکیل باشگاه: {lawyer['lawyer_name']} | مهارت {lawyer['skill']}/100",callback_data='lawyer_info')]]
        lines=[f"⚖️ مرکز حقوقی {club['name']}",f"وکیل: {lawyer['lawyer_name']+' (مهارت '+str(lawyer['skill'])+'/100)' if lawyer else 'ندارید'}",""]
        for r in cases:
            subject=(r['first_name']+' '+r['last_name']) if r['player_id'] and r['first_name'] else 'باشگاه'
            desc=f"محرومیت {r['suspension_matches']} بازی" if r['case_type']=='suspension' else f"جریمه {money(r['fine_amount'])}"
            lines.append(f"پرونده #{r['id']} | {subject} | {desc} | علت: {r['reason']} | وضعیت: {r['status']}")
            if r['status']=='active': kb.append([InlineKeyboardButton(f"📝 اعتراض به پرونده #{r['id']}",callback_data=f"appeal_case_{r['id']}")])
        kb.append([InlineKeyboardButton("↩️ برگشت",callback_data='owner')])
        await safe_edit(q,"\n".join(lines)[:3900],InlineKeyboardMarkup(kb)); return
    if data == 'lawyer_hire':
        club=get_club_by_owner(uid)
        if not club: await safe_edit(q,"باشگاه پیدا نشد.",back_keyboard('home')); return
        with db() as c:
            existing=c.execute("SELECT 1 FROM club_lawyers WHERE club_id=?",(club['id'],)).fetchone()
            current=c.execute("SELECT budget FROM clubs WHERE id=?",(club['id'],)).fetchone()['budget']
            if existing: await safe_edit(q,"باشگاه از قبل وکیل دارد.",back_keyboard('owner_appeals')); return
            if current<50_000_000: await safe_edit(q,f"بودجه برای استخدام وکیل کافی نیست. هزینه {money(50_000_000)}؛ موجودی {money(current)}.",back_keyboard('owner_appeals')); return
            c.execute("UPDATE clubs SET budget=budget-50000000 WHERE id=?",(club['id'],))
            c.execute("INSERT INTO club_lawyers(club_id,lawyer_name,skill,hired_at) VALUES(?,?,?,?)",(club['id'],'وکیل هوشمند باشگاه',72,now()))
            c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)",(club['id'],'استخدام وکیل',-50_000_000,'استخدام وکیل هوشمند برای اعتراضات انضباطی',now()))
        await safe_edit(q,"✅ وکیل هوشمند استخدام شد. در اعتراض‌های بعدی پرونده‌ها را بررسی می‌کند و شانس موفقیت را افزایش می‌دهد.",back_keyboard('owner_appeals')); return
    if data == 'lawyer_info':
        await safe_edit(q,"وکیل هوشمند باشگاه آماده بررسی پرونده‌های محرومیت و جریمه است. نتیجه بر اساس شدت تخلف، مستندات و مهارت وکیل محاسبه می‌شود.",back_keyboard('owner_appeals')); return
    if data.startswith('appeal_case_'):
        club=get_club_by_owner(uid)
        if not club: await safe_edit(q,"باشگاه پیدا نشد.",back_keyboard('home')); return
        cid=int(data.rsplit('_',1)[1])
        with db() as c:
            case=c.execute("SELECT * FROM discipline_cases WHERE id=? AND club_id=? AND status='active'",(cid,club['id'])).fetchone()
        if not case: await safe_edit(q,"پرونده فعال پیدا نشد.",back_keyboard('owner_appeals')); return
        set_state(context,'appeal_text',{'case_id':cid,'club_id':club['id']})
        await safe_edit(q,f"اعتراض به پرونده #{cid}\nلایحه دفاعیه را بنویسید. وکیل هوشمند آن را بررسی می‌کند و نتیجه شبیه‌سازی‌شده اعلام می‌شود.",back_keyboard('owner_appeals')); return

    # پیام همگانی: پیش‌نمایش، تأیید و ارسال به کاربران ثبت‌شده
    if data == "broadcast_send":
        if not is_admin(uid):
            await q.answer("فقط ادمین.", show_alert=True); return
        pending = context.user_data.get("pending_broadcast")
        if not pending:
            await safe_edit(q, "پیام همگانی منقضی شده است؛ دوباره شروع کنید.", back_keyboard("admin")); return
        with db() as c:
            recipients = [int(r["user_id"]) for r in c.execute("SELECT user_id FROM users ORDER BY user_id").fetchall()]
        import asyncio
        sent = failed = 0
        for target_id in recipients:
            try:
                await context.bot.send_message(chat_id=target_id, text=pending)
                sent += 1
            except Exception as exc:
                failed += 1
                logger.info("Broadcast delivery failed for user %s: %s", target_id, exc)
            await asyncio.sleep(0.04)
        context.user_data.pop("pending_broadcast", None)
        set_state(context, None)
        await safe_edit(q, f"📢 ارسال پیام همگانی تمام شد.\n✅ ارسال موفق: {sent}\n⚠️ ارسال ناموفق: {failed}\n👥 تعداد حساب‌های ثبت‌شده: {len(recipients)}", back_keyboard("admin")); return
    if data == "broadcast_cancel":
        if not is_admin(uid):
            await q.answer("فقط ادمین.", show_alert=True); return
        context.user_data.pop("pending_broadcast", None)
        set_state(context, None)
        await safe_edit(q, "ارسال پیام همگانی لغو شد.", back_keyboard("admin")); return

    # همه دکمه‌های ادمین
    if data.startswith("admin_") or data in ("admin_clubs", "admin_password"):
        if not is_admin(uid):
            await q.answer("فقط ادمین.", show_alert=True); return
        if data == "admin_schedule_create":
            with db() as c:
                clubs = [dict(r) for r in c.execute("SELECT id,name FROM clubs ORDER BY id").fetchall()]
                season = str(datetime.now().year) + "-" + str(datetime.now().month).zfill(2)
                already = c.execute("SELECT COUNT(*) n FROM league_fixtures WHERE season=?", (season,)).fetchone()["n"]
                if already:
                    await safe_edit(q, f"برای فصل {season} از قبل برنامه ثبت شده است ({already} بازی). برای جلوگیری از بازی تکراری، برنامه جدید ساخته نشد.", back_keyboard("admin")); return
                if len(clubs) < 2:
                    await safe_edit(q, "برای ساخت برنامه فصل حداقل دو باشگاه لازم است.", back_keyboard("admin")); return
                # قرعه‌کشی رفت‌وبرگشت به روش چرخشی
                ids = [r['id'] for r in clubs]
                if len(ids) % 2: ids.append(None)
                n = len(ids); rounds = n - 1; fixtures = []
                ring = ids[:]
                for rnd in range(rounds):
                    for j in range(n // 2):
                        a, b = ring[j], ring[n-1-j]
                        if a is not None and b is not None:
                            home_id, away_id = (a,b) if rnd % 2 == 0 else (b,a)
                            fixtures.append((season, rnd+1, home_id, away_id, 'scheduled', None, None, ''))
                            fixtures.append((season, rounds+rnd+1, away_id, home_id, 'scheduled', None, None, ''))
                    ring = [ring[0]] + [ring[-1]] + ring[1:-1]
                c.executemany("INSERT INTO league_fixtures(season,round_no,home_club_id,away_club_id,status,home_goals,away_goals,played_at) VALUES(?,?,?,?,?,?,?,?)", fixtures)
            await safe_edit(q, f"✅ برنامه فصل {season} ساخته شد. تعداد تیم‌ها: {len(clubs)}؛ تعداد مسابقات رفت‌وبرگشت: {len(fixtures)}؛ تعداد هفته‌ها: {rounds*2}.", back_keyboard("admin")); return
        if data == "admin_schedule_next":
            with db() as c:
                fixture = c.execute("SELECT f.*,h.name home_name,a.name away_name FROM league_fixtures f JOIN clubs h ON h.id=f.home_club_id JOIN clubs a ON a.id=f.away_club_id WHERE f.status='scheduled' ORDER BY f.season,f.round_no,f.id LIMIT 1").fetchone()
            if not fixture:
                await safe_edit(q, "مسابقه برنامه‌ریزی‌شده‌ای باقی نمانده است. ابتدا برنامه فصل بسازید.", back_keyboard("admin")); return
            with db() as c:
                home_line = c.execute("SELECT starters FROM club_lineups WHERE club_id=?", (fixture['home_club_id'],)).fetchone()
                away_line = c.execute("SELECT starters FROM club_lineups WHERE club_id=?", (fixture['away_club_id'],)).fetchone()
            if not home_line or len([x for x in (home_line['starters'] or '').split(',') if x.strip()]) != 11 or not away_line or len([x for x in (away_line['starters'] or '').split(',') if x.strip()]) != 11:
                await safe_edit(q, f"⛔ بازی هفته {fixture['round_no']} اجرا نشد؛ هر دو باشگاه باید ترکیب ۱۱ نفره ذخیره کنند.\n{fixture['home_name']} - {fixture['away_name']}", back_keyboard("admin")); return
            hg, ag, report = simulate_match(fixture['home_club_id'], fixture['away_club_id'], fixture['home_name'], fixture['away_name'], 'league')
            with db() as c:
                c.execute("UPDATE league_fixtures SET status='played',home_goals=?,away_goals=?,played_at=? WHERE id=? AND status='scheduled'", (hg,ag,now(),fixture['id']))
                c.execute("INSERT INTO matches(home_club_id,away_club_id,home_goals,away_goals,match_type,report,played_at) VALUES(?,?,?,?,?,?,?)", (fixture['home_club_id'],fixture['away_club_id'],hg,ag,'league',report,now()))
            notes = match_financials(fixture['home_club_id'], fixture['away_club_id'])
            if notes: report += "\n\n💰 امور مالی بازی\n" + "\n".join(notes)
            await safe_edit(q, report[:3900], back_keyboard("admin"))
            for chunk_start in range(3900, len(report), 3500):
                await q.message.reply_text(report[chunk_start:chunk_start+3500])
            await send_channel(context, f"🏆 هفته {fixture['round_no']} | {fixture['home_name']} {hg}-{ag} {fixture['away_name']}")
            return
        if data == "admin_league_match":
            with db() as c:
                clubs = c.execute("SELECT id,name FROM clubs ORDER BY name").fetchall()
            if len(clubs) < 2:
                await safe_edit(q, "برای برگزاری بازی لیگ حداقل دو باشگاه تأییدشده لازم است.", back_keyboard("admin")); return
            kb = [[InlineKeyboardButton(f"🏠 میزبان: {r['name']} (#{r['id']})", callback_data=f"admin_league_home_{r['id']}")] for r in clubs]
            kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="admin")])
            await safe_edit(q, "🏆 نسخه ۱۰ — ابتدا تیم میزبان را انتخاب کنید:", InlineKeyboardMarkup(kb)); return
        if data.startswith("admin_league_home_"):
            home_id = int(data.rsplit("_", 1)[1])
            with db() as c:
                clubs = c.execute("SELECT id,name FROM clubs WHERE id<>? ORDER BY name", (home_id,)).fetchall()
                home = c.execute("SELECT name FROM clubs WHERE id=?", (home_id,)).fetchone()
            if not home or not clubs:
                await safe_edit(q, "باشگاه معتبر پیدا نشد.", back_keyboard("admin")); return
            kb = [[InlineKeyboardButton(f"✈️ میهمان: {r['name']} (#{r['id']})", callback_data=f"admin_league_away_{home_id}_{r['id']}")] for r in clubs]
            kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="admin_league_match")])
            await safe_edit(q, f"میزبان: {home['name']}\nحالا تیم میهمان را انتخاب کنید:", InlineKeyboardMarkup(kb)); return
        if data.startswith("admin_league_away_"):
            parts = data.split("_")
            try:
                home_id, away_id = int(parts[-2]), int(parts[-1])
            except (ValueError, IndexError):
                await safe_edit(q, "شناسه تیم نامعتبر است.", back_keyboard("admin")); return
            if home_id == away_id:
                await safe_edit(q, "یک باشگاه نمی‌تواند حریف خودش باشد.", back_keyboard("admin_league_match")); return
            with db() as c:
                home = c.execute("SELECT * FROM clubs WHERE id=?", (home_id,)).fetchone()
                away = c.execute("SELECT * FROM clubs WHERE id=?", (away_id,)).fetchone()
            if not home or not away:
                await safe_edit(q, "یکی از باشگاه‌ها پیدا نشد.", back_keyboard("admin")); return
            hg, ag, report = simulate_match(home_id, away_id, home['name'], away['name'], 'league')
            with db() as c:
                c.execute("INSERT INTO matches(home_club_id,away_club_id,home_goals,away_goals,match_type,report,played_at) VALUES(?,?,?,?,?,?,?)", (home_id, away_id, hg, ag, 'league', report, now()))
            finance_notes = match_financials(home_id, away_id)
            if finance_notes:
                report += "\n\n💰 گزارش مالی مسابقه\n" + "\n".join(finance_notes)
            await safe_edit(q, report[:3900], back_keyboard("admin"))
            for chunk_start in range(3900, len(report), 3500):
                await q.message.reply_text(report[chunk_start:chunk_start+3500])
            await send_channel(context, f"🏆 نتیجه لیگ: {home['name']} {hg}-{ag} {away['name']}")
            return
        if data == "admin_requests":
            with db() as c:
                rows = c.execute("SELECT * FROM club_requests WHERE status='pending' ORDER BY id").fetchall()
            if not rows:
                await safe_edit(q, "درخواست در انتظار وجود ندارد.", back_keyboard("admin")); return
            buttons_list = []
            text = "📋 درخواست‌های در انتظار:\n\n"
            for r in rows:
                text += f"#{r['id']} — {r['club_name']} | {r['city']}، {r['country']} | مالک: {r['owner_id']}\n"
                buttons_list.append([
                    InlineKeyboardButton(f"✅ تأیید #{r['id']}", callback_data=f"approve_{r['id']}"),
                    InlineKeyboardButton(f"❌ رد #{r['id']}", callback_data=f"reject_{r['id']}")
                ])
            buttons_list.append([InlineKeyboardButton("↩️ برگشت", callback_data="admin")])
            await safe_edit(q, text, InlineKeyboardMarkup(buttons_list)); return
        if data == "admin_clubs":
            with db() as c:
                rows = c.execute("SELECT id,name,budget,owner_id FROM clubs ORDER BY id").fetchall()
            if not rows:
                await safe_edit(q, "هنوز باشگاهی ثبت نشده است.", back_keyboard("admin")); return
            text = "🏟 باشگاه‌ها:\n\n" + "\n".join(
                f"#{r['id']} {r['name']} | مالک {r['owner_id']} | {money(r['budget'])}" for r in rows
            )
            await safe_edit(q, text, InlineKeyboardMarkup([
                [InlineKeyboardButton("💸 جریمه باشگاه", callback_data="admin_fine")],
                [InlineKeyboardButton("💰 تغییر بودجه", callback_data="admin_budget")],
                [InlineKeyboardButton("🗑 حذف باشگاه", callback_data="admin_delete_club")],
                [InlineKeyboardButton("↩️ برگشت", callback_data="admin")]
            ])); return
        if data == "admin_password":
            set_state(context, "admin_password", {})
            await safe_edit(q, "شناسه عددی مالک را بفرستید تا رمز جدید باشگاه برایش ثبت شود:", back_keyboard("admin")); return
        if data == "admin_fine":
            set_state(context, "admin_fine", {})
            await safe_edit(q, "شناسه باشگاه و مبلغ جریمه را با فاصله بفرستید.\nمثال: 2 5000000", back_keyboard("admin_clubs")); return
        if data == "admin_budget":
            set_state(context, "admin_budget", {})
            await safe_edit(q, "شناسه باشگاه و مبلغ تغییر بودجه را با فاصله بفرستید.\nبرای کم کردن، عدد منفی بنویسید.\nمثال: 2 10000000", back_keyboard("admin_clubs")); return
        if data == "admin_delete_club":
            set_state(context, "admin_delete_club")
            await safe_edit(q, "شناسه باشگاه برای حذف را بفرستید:", back_keyboard("admin_clubs")); return
        if data == "admin_add_player":
            set_state(context, "player_first", {})
            await safe_edit(q, "ثبت بازیکن جدید.\nنام بازیکن را بفرستید:", back_keyboard("admin")); return
        if data == "admin_add_staff":
            set_state(context, "staff_first", {})
            await safe_edit(q, "ثبت عضو کادر فنی.\nنام را بفرستید:", back_keyboard("admin")); return
        if data == "admin_delete_assets":
            with db() as c:
                ps = c.execute("SELECT id,first_name,last_name,position FROM players WHERE status='market' ORDER BY id LIMIT 30").fetchall()
                ss = c.execute("SELECT id,first_name,last_name,role FROM staff WHERE status='market' ORDER BY id LIMIT 30").fetchall()
            kb = []
            for x in ps:
                kb.append([InlineKeyboardButton(f"🗑 بازیکن #{x['id']} {x['first_name']} {x['last_name']}", callback_data=f"admin_del_player_{x['id']}")])
            for x in ss:
                kb.append([InlineKeyboardButton(f"🗑 کادر #{x['id']} {x['first_name']} {x['last_name']}", callback_data=f"admin_del_staff_{x['id']}")])
            kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="admin")])
            msg = "🗑 حذف فقط برای موارد موجود در بازار انجام می‌شود.\nبازیکنان و کادرهای دارای باشگاه، ابتدا باید از باشگاه آزاد شوند."
            if not ps and not ss: msg += "\nبازار خالی است."
            await safe_edit(q, msg, InlineKeyboardMarkup(kb)); return
        if data == "admin_window":
            opened = transfer_window_open()
            new_val = "closed" if opened else "open"
            with db() as c:
                c.execute("UPDATE settings SET value=? WHERE key='transfer_window'", (new_val,))
            status = "باز" if new_val == "open" else "بسته"
            await safe_edit(q, f"پنجره نقل‌وانتقالات اکنون {status} است.", admin_keyboard())
            await send_channel(context, f"📣 پنجره نقل‌وانتقالات فوتبال اکنون {status} شد.")
            return
        if data == "admin_gift":
            set_state(context, "admin_gift_amount", {})
            await safe_edit(q, "مبلغ کد هدیه را به تومان بفرستید:", back_keyboard("admin")); return
        if data == "admin_announce":
            set_state(context, "admin_announce")
            await safe_edit(q, "متن اطلاعیه را بفرستید تا در کانال ارسال شود:", back_keyboard("admin")); return
        if data == "admin_broadcast":
            set_state(context, "admin_broadcast")
            await safe_edit(q, "📢 متن پیام همگانی را بفرستید. قبل از ارسال، پیش‌نمایش و تأیید نهایی نمایش داده می‌شود.", back_keyboard("admin")); return
        if data == "admin_messages":
            with db() as c:
                rows = c.execute("SELECT * FROM messages WHERE status='new' ORDER BY id DESC LIMIT 20").fetchall()
            if not rows:
                await safe_edit(q, "پیام جدیدی وجود ندارد.", back_keyboard("admin")); return
            text = "📨 پیام‌های جدید:\n\n"
            for r in rows:
                text += f"#{r['id']} | {r['kind']} | کاربر {r['user_id']}\n{r['body'][:500]}\n\n"
            await safe_edit(q, text, back_keyboard("admin")); return

    # حذف بازیکن/کادر از بازار فقط توسط ادمین
    if data.startswith("admin_del_player_") or data.startswith("admin_del_staff_"):
        if not is_admin(uid):
            await q.answer("فقط ادمین.", show_alert=True); return
        asset_id = int(data.rsplit("_", 1)[1])
        is_player = data.startswith("admin_del_player_")
        table = "players" if is_player else "staff"
        with db() as c:
            row = c.execute(f"SELECT * FROM {table} WHERE id=? AND status='market'", (asset_id,)).fetchone()
            if row:
                c.execute(f"DELETE FROM {table} WHERE id=? AND status='market'", (asset_id,))
        await safe_edit(q, ("✅ بازیکن از بازار حذف شد." if is_player else "✅ عضو کادر از بازار حذف شد.") if row else "مورد پیدا نشد یا قبلاً از بازار خارج شده است.", back_keyboard("admin_delete_assets"))
        return

    # تأیید/رد درخواست
    if data.startswith("approve_") or data.startswith("reject_"):
        if not is_admin(uid):
            await q.answer("فقط ادمین.", show_alert=True); return
        req_id = int(data.split("_")[1])
        with db() as c:
            req = c.execute("SELECT * FROM club_requests WHERE id=? AND status='pending'", (req_id,)).fetchone()
            if not req:
                await safe_edit(q, "درخواست پیدا نشد یا قبلاً بررسی شده است.", back_keyboard("admin")); return
            if data.startswith("reject_"):
                c.execute("UPDATE club_requests SET status='rejected' WHERE id=?", (req_id,))
                result = f"درخواست باشگاه «{req['club_name']}» رد شد."
            else:
                if c.execute("SELECT 1 FROM clubs WHERE owner_id=?", (req["owner_id"],)).fetchone():
                    c.execute("UPDATE club_requests SET status='rejected' WHERE id=?", (req_id,))
                    result = "این مالک از قبل باشگاه دارد؛ درخواست رد شد."
                elif c.execute("SELECT 1 FROM clubs WHERE name=? COLLATE NOCASE", (req["club_name"],)).fetchone():
                    c.execute("UPDATE club_requests SET status='rejected' WHERE id=?", (req_id,))
                    result = "نام باشگاه تکراری است؛ درخواست رد شد."
                else:
                    password = secrets.token_urlsafe(6)
                    c.execute("""
                        INSERT INTO clubs(owner_id,name,city,country,password_hash,budget,reputation,created_at)
                        VALUES(?,?,?,?,?,?,?,?)
                    """, (req["owner_id"], req["club_name"], req["city"], req["country"], password,
                          0, 50, now()))
                    c.execute("UPDATE club_requests SET status='approved' WHERE id=?", (req_id,))
                    club_id = c.execute("SELECT id FROM clubs WHERE owner_id=?", (req["owner_id"],)).fetchone()["id"]
                    c.execute("INSERT OR IGNORE INTO club_settings(club_id) VALUES(?)", (club_id,))
                    c.execute("INSERT OR IGNORE INTO club_lineups(club_id) VALUES(?)", (club_id,))
                    result = f"باشگاه «{req['club_name']}» تأیید شد.\nرمز ورود/مدیریت باشگاه: {password}\nبودجه اولیه: {money(0)}"
        try:
            await context.bot.send_message(req["owner_id"], result)
        except Exception:
            pass
        await safe_edit(q, result, back_keyboard("admin_requests"))
        await send_channel(context, f"🏟 درخواست باشگاه {req['club_name']} بررسی شد.")
        return

    # نسخه ۳: ترکیب، تاکتیک، ورزشگاه و تمرین
    if data in ("v3_lineup", "v3_set_lineup", "v3_tactics", "v3_stadium", "v3_training", "v4_friendly", "v4_results"):
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        if data == "v3_lineup":
            with db() as c:
                owned = c.execute("SELECT p.id,p.first_name,p.last_name,p.position FROM club_players cp JOIN players p ON p.id=cp.player_id WHERE cp.club_id=? ORDER BY p.id", (club['id'],)).fetchall()
                line = c.execute("SELECT * FROM club_lineups WHERE club_id=?", (club['id'],)).fetchone()
                setting = c.execute("SELECT * FROM club_settings WHERE club_id=?", (club['id'],)).fetchone()
            names = "\n".join(f"#{p['id']} {p['first_name']} {p['last_name']} — {p['position']}" for p in owned) or "هنوز بازیکنی ندارید؛ ابتدا از بازار خرید کنید."
            saved = f"\n\nترکیب ذخیره‌شده: {line['starters'] if line else 'ندارد'}\nنیمکت: {line['bench'] if line else 'ندارد'}\nکاپیتان اول: {setting['captain_id'] if setting and setting['captain_id'] else 'تعیین نشده'} | دوم: {setting['captain2_id'] if setting and setting['captain2_id'] else 'تعیین نشده'} | سوم: {setting['captain3_id'] if setting and setting['captain3_id'] else 'تعیین نشده'}\nآرایش: {setting['formation'] if setting else '4-3-3'} | تاکتیک: {setting['tactics'] if setting else 'متعادل'}"
            kb = [[InlineKeyboardButton("💾 ثبت/ویرایش ترکیب", callback_data="v3_set_lineup")], [InlineKeyboardButton("🎯 تغییر آرایش و تاکتیک", callback_data="v3_tactics")], [InlineKeyboardButton("↩️ برگشت", callback_data="owner")]]
            await safe_edit(q, "📋 فهرست بازیکنان و شناسه‌ها:\n"+names+saved+"\n\nبرای ثبت ترکیب دکمه «ثبت/ویرایش ترکیب» را بزنید؛ بازیکنان را یکی‌یکی انتخاب و پست هرکدام را مشخص کنید.", InlineKeyboardMarkup(kb)); return
        if data == "v3_set_lineup":
            with db() as c:
                owned = c.execute("SELECT p.id,p.first_name,p.last_name,p.position FROM club_players cp JOIN players p ON p.id=cp.player_id WHERE cp.club_id=? AND cp.loan_from_club_id IS NULL ORDER BY p.id", (club['id'],)).fetchall()
            if len(owned) < 11:
                await safe_edit(q, f"برای ثبت ترکیب اصلی حداقل ۱۱ بازیکن غیرقرضی لازم دارید؛ اکنون {len(owned)} نفر دارید.", back_keyboard("v3_lineup")); return
            form = {"club_id": club['id'], "starters": [], "positions": {}, "bench": []}
            set_state(context, "lineup_interactive", form)
            kb = [[InlineKeyboardButton(f"{p['first_name']} {p['last_name']} (#{p['id']})", callback_data=f"lineup_pick_{p['id']}")] for p in owned]
            kb.append([InlineKeyboardButton("↩️ لغو", callback_data="v3_lineup")])
            await safe_edit(q, "نسخه ۶ — بازیکن اول ترکیب اصلی را انتخاب کنید؛ سپس پست او را تعیین می‌کنید.", InlineKeyboardMarkup(kb)); return
        if data == "v3_tactics":
            formations = ["4-4-2","4-3-3","4-2-3-1","4-1-4-1","4-3-2-1","4-2-2-2","4-3-1-2","4-1-2-1-2","4-5-1","4-4-1-1","3-5-2","3-4-3","3-4-2-1","3-4-1-2","3-1-4-2","3-2-4-1","5-3-2","5-4-1","5-2-3","5-2-1-2"]
            kb = [[InlineKeyboardButton(f"📐 {f}", callback_data=f"formation_set_{f}")] for f in formations]
            kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="v3_lineup")])
            await safe_edit(q, "📐 چیدمان دلخواه را انتخاب کنید. آرایش انتخابی برای شبیه‌سازی مسابقه ذخیره می‌شود:", InlineKeyboardMarkup(kb)); return
        if data == "v3_stadium":
            with db() as c:
                st = c.execute("SELECT * FROM club_settings WHERE club_id=?", (club['id'],)).fetchone()
            set_state(context, "v3_stadium", {"club_id": club['id']})
            await safe_edit(q, f"ورزشگاه فعلی: {st['stadium'] if st else 'ورزشگاه اختصاصی'}\nقیمت بلیت فعلی: {money(st['ticket_price'] if st else 200000)}\nنام ورزشگاه، قیمت بلیت و ظرفیت را با | جدا کنید. مثال: آزادی | 250000 | 45000", back_keyboard("owner")); return
        if data == "v3_training":
            with db() as c:
                st = c.execute("SELECT training_at FROM club_settings WHERE club_id=?", (club['id'],)).fetchone()
            last = st['training_at'] if st else ''
            if last:
                try:
                    elapsed = (datetime.now() - datetime.strptime(last, "%Y-%m-%d %H:%M:%S")).total_seconds()
                except Exception: elapsed = 86400
                if elapsed < 86400:
                    await safe_edit(q, f"⏳ تمرین روزانه قبلاً انجام شده است. {int((86400-elapsed)//3600)} ساعت دیگر دوباره امتحان کنید.", back_keyboard("owner")); return
            with db() as c:
                c.execute("INSERT OR IGNORE INTO club_settings(club_id) VALUES(?)", (club['id'],))
                c.execute("UPDATE club_settings SET training_at=? WHERE club_id=?", (now(), club['id']))
                c.execute("UPDATE clubs SET reputation=MIN(100,reputation+1) WHERE id=?", (club['id'],))
            await safe_edit(q, "🏃 تمرین روزانه انجام شد! آمادگی تیم بهتر شد و اعتبار باشگاه ۱ واحد افزایش یافت. تمرین بعدی پس از ۲۴ ساعت.", back_keyboard("owner")); return
        if data == "v4_friendly":
            with db() as c:
                lineup = c.execute("SELECT starters FROM club_lineups WHERE club_id=?", (club['id'],)).fetchone()
                opponents = c.execute("SELECT id,name,city,country FROM clubs WHERE id<>? ORDER BY id", (club['id'],)).fetchall()
            if not lineup or len([x for x in lineup['starters'].split(',') if x.strip()]) != 11:
                await safe_edit(q, "❌ قبل از بازی باید ترکیب ۱۱ نفره را در بخش ترکیب و تاکتیک ذخیره کنید.", back_keyboard("v3_lineup")); return
            if not opponents:
                await safe_edit(q, "برای بازی دوستانه حداقل یک باشگاه دیگر باید تأیید شده باشد.", back_keyboard("owner")); return
            kb = [[InlineKeyboardButton(f"🤝 {o['name']} (شناسه {o['id']})", callback_data=f"v4_play_{o['id']}")] for o in opponents]
            kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="owner")])
            await safe_edit(q, "حریف بازی دوستانه را انتخاب کنید:", InlineKeyboardMarkup(kb)); return
        if data == "v4_results":
            with db() as c:
                rows = c.execute("SELECT m.*,h.name home_name,a.name away_name FROM matches m JOIN clubs h ON h.id=m.home_club_id JOIN clubs a ON a.id=m.away_club_id WHERE m.home_club_id=? OR m.away_club_id=? ORDER BY m.id DESC LIMIT 10", (club['id'],club['id'])).fetchall()
            text = "📜 آخرین نتایج\n\n" + ("\n\n".join(f"{r['home_name']} {r['home_goals']} - {r['away_goals']} {r['away_name']}\n{r['played_at']}" for r in rows) if rows else "هنوز بازی‌ای ثبت نشده است.")
            await safe_edit(q, text[:3900], back_keyboard("owner")); return

    if data.startswith("v4_play_"):
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        away_id = int(data.rsplit("_", 1)[1])
        with db() as c:
            lineup = c.execute("SELECT starters FROM club_lineups WHERE club_id=?", (club['id'],)).fetchone()
            away = c.execute("SELECT * FROM clubs WHERE id=?", (away_id,)).fetchone()
            away_lineup = c.execute("SELECT starters FROM club_lineups WHERE club_id=?", (away_id,)).fetchone()
        if not lineup or len([x for x in lineup['starters'].split(',') if x.strip()]) != 11:
            await safe_edit(q, "ابتدا ترکیب ۱۱ نفره را ذخیره کنید.", back_keyboard("v3_lineup")); return
        home_goals, away_goals, report = simulate_match(club['id'], away_id, club['name'], away['name'], 'friendly')
        with db() as c:
            c.execute("INSERT INTO matches(home_club_id,away_club_id,home_goals,away_goals,match_type,report,played_at) VALUES(?,?,?,?,?,?,?)", (club['id'],away_id,home_goals,away_goals,'friendly',report,now()))
        finance_notes = match_financials(club['id'], away_id)
        if finance_notes:
            report += "\n\n💰 گزارش مالی مسابقه\n" + "\n".join(finance_notes)
        await safe_edit(q, report[:3900], back_keyboard("owner"))
        for chunk_start in range(3900, len(report), 3500):
            await q.message.reply_text(report[chunk_start:chunk_start+3500])
        await send_channel(context, f"⚽ بازی دوستانه: {club['name']} {home_goals}-{away_goals} {away['name']}")
        return

    if data == "v13_rules":
        await safe_edit(q, "⚽ نسخه ۱۳ — قوانین مسابقه فعال شد\n\n• قدرت تیم بر اساس ارزش تقریبی بازیکنان، آمادگی، اعتبار باشگاه و تاکتیک محاسبه می‌شود.\n• گزارش مسابقه دقیقه‌به‌دقیقه است.\n• کارت زرد و اخراج با دو زرد در یک بازی ثبت می‌شود.\n• چهارمین کارت زرد انباشته باعث محرومیت یک مسابقه‌ای می‌شود.\n• مصدومیت با زمان بهبودی ثبت می‌شود و از مرکز پزشکی قابل پیگیری است.\n• تعویض خودکار در صورت مصدومیت/افت آمادگی انجام می‌شود؛ حداکثر ۶ تعویض برای هر تیم.\n• آمادگی بازیکنان پس از مسابقه کاهش می‌یابد.\n\nدر نسخه ۱۵ امکان برنامه‌ریزی تعویض دستی پیش از مسابقه، مذاکره قرارداد، تمدید و فسخ اضافه شده است. برنامه تعویض فقط در صورت حضور بازیکنان و رعایت سقف ۶ تعویض اجرا می‌شود. سفر و درآمد بلیت همچنان تخمینی هستند.", back_keyboard("owner")); return

    if data == "v9_conditions":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        with db() as c:
            rows = c.execute("""SELECT p.id,p.first_name,p.last_name,p.position,
                COALESCE(pc.fitness,100) fitness, COALESCE(pc.yellow_cards,0) yellow_cards,
                COALESCE(pc.suspended_matches,0) suspended_matches, COALESCE(pc.injury_until,'') injury_until
                FROM club_players cp JOIN players p ON p.id=cp.player_id
                LEFT JOIN player_conditions pc ON pc.player_id=p.id
                WHERE cp.club_id=? ORDER BY p.id""", (club['id'],)).fetchall()
            setting = c.execute("SELECT training_at FROM club_settings WHERE club_id=?", (club['id'],)).fetchone()
        out = [f"🩺 آمادگی و وضعیت بازیکنان — نسخه ۹\nباشگاه: {club['name']}\n"]
        for r in rows:
            status = "⛔ محروم" if r['suspended_matches'] > 0 else ("🩹 مصدوم" if r['injury_until'] else "✅ آماده")
            out.append(f"#{r['id']} {r['first_name']} {r['last_name']} ({r['position']}) | آمادگی {r['fitness']}٪ | کارت زرد: {r['yellow_cards']} | محرومیت: {r['suspended_matches']} بازی | {status}")
        if not rows: out.append("هنوز بازیکنی در باشگاه ندارید.")
        kb = [[InlineKeyboardButton("🧘 ریکاوری تیم", callback_data="v9_recovery")], [InlineKeyboardButton("↩️ برگشت", callback_data="owner")]]
        await safe_edit(q, "\n".join(out)[:3900], InlineKeyboardMarkup(kb)); return

    if data == "v9_recovery":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        with db() as c:
            setting = c.execute("SELECT training_at FROM club_settings WHERE club_id=?", (club['id'],)).fetchone()
            last = setting['training_at'] if setting else ''
            if last:
                try:
                    elapsed = (datetime.now() - datetime.strptime(last, "%Y-%m-%d %H:%M:%S")).total_seconds()
                except Exception:
                    elapsed = 86401
            else:
                elapsed = 86401
            if elapsed < 86400:
                remain = int((86400-elapsed)/3600)+1
                await safe_edit(q, f"⏳ ریکاوری فقط هر ۲۴ ساعت یک‌بار ممکن است. حدود {remain} ساعت دیگر دوباره تلاش کنید.", back_keyboard("v9_conditions")); return
            pids = [r['player_id'] for r in c.execute("SELECT player_id FROM club_players WHERE club_id=?", (club['id'],)).fetchall()]
            for pid in pids:
                c.execute("INSERT INTO player_conditions(player_id,fitness,updated_at) VALUES(?,100,?) ON CONFLICT(player_id) DO UPDATE SET fitness=MIN(100,player_conditions.fitness+15), updated_at=excluded.updated_at", (pid, now()))
            c.execute("UPDATE club_settings SET training_at=? WHERE club_id=?", (now(), club['id']))
        await safe_edit(q, f"🧘 ریکاوری تیم انجام شد. آمادگی بازیکنان تا ۱۵٪ افزایش یافت (حداکثر ۱۰۰٪). تعداد بازیکنان: {len(pids)}", back_keyboard("v9_conditions")); return

    if data == "v10_standings":
        with db() as c:
            clubs = c.execute("SELECT id,name FROM clubs ORDER BY name").fetchall()
            matches = c.execute("SELECT home_club_id,away_club_id,home_goals,away_goals FROM matches WHERE match_type='league' ORDER BY id").fetchall()
        stats = {int(r['id']): {'name':r['name'],'P':0,'W':0,'D':0,'L':0,'GF':0,'GA':0,'Pts':0} for r in clubs}
        for m in matches:
            h, a = int(m['home_club_id']), int(m['away_club_id'])
            if h not in stats or a not in stats: continue
            hg, ag = int(m['home_goals']), int(m['away_goals'])
            for cid in (h,a): stats[cid]['P'] += 1
            stats[h]['GF'] += hg; stats[h]['GA'] += ag
            stats[a]['GF'] += ag; stats[a]['GA'] += hg
            if hg > ag: stats[h]['W'] += 1; stats[h]['Pts'] += 3; stats[a]['L'] += 1
            elif ag > hg: stats[a]['W'] += 1; stats[a]['Pts'] += 3; stats[h]['L'] += 1
            else: stats[h]['D'] += 1; stats[a]['D'] += 1; stats[h]['Pts'] += 1; stats[a]['Pts'] += 1
        ordered = sorted(stats.values(), key=lambda x:(-x['Pts'],-(x['GF']-x['GA']),-x['GF'],x['name']))
        lines = ["🏆 جدول لیگ — نسخه ۱۰", "رتبه | باشگاه | بازی | برد-مساوی-باخت | گل زده:خورده | امتیاز", ""]
        for i,r in enumerate(ordered,1):
            lines.append(f"{i}. {r['name']} | {r['P']} | {r['W']}-{r['D']}-{r['L']} | {r['GF']}:{r['GA']} | {r['Pts']}")
        if not ordered: lines.append("هنوز باشگاهی ثبت نشده است.")
        if not matches: lines.append("\nهنوز بازی لیگی ثبت نشده؛ ادمین می‌تواند از پنل مدیریت بازی لیگ برگزار کند.")
        await safe_edit(q, "\n".join(lines)[:3900], back_keyboard("owner")); return

    # نسخه ۱۱: مرکز پزشکی، مصدومیت و محرومیت
    if data == "v11_medical":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        with db() as c:
            rows = c.execute("""SELECT p.id,p.first_name,p.last_name,
                COALESCE(pc.fitness,100) fitness, COALESCE(pc.yellow_cards,0) yellow_cards,
                COALESCE(pc.suspended_matches,0) suspended_matches, COALESCE(pc.injury_until,'') injury_until
                FROM club_players cp JOIN players p ON p.id=cp.player_id
                LEFT JOIN player_conditions pc ON pc.player_id=p.id
                WHERE cp.club_id=? ORDER BY p.id""", (club["id"],)).fetchall()
        lines = [f"🩹 مرکز پزشکی و محرومیت — نسخه ۱۱\nباشگاه: {club['name']}", ""]
        injured = 0
        suspended = 0
        for r in rows:
            injury = r["injury_until"] or "ندارد"
            if r["injury_until"]:
                injured += 1
            if int(r["suspended_matches"] or 0) > 0:
                suspended += 1
            lines.append(f"#{r['id']} {r['first_name']} {r['last_name']} | آمادگی {r['fitness']}٪ | کارت زرد {r['yellow_cards']} | محرومیت {r['suspended_matches']} بازی | مصدومیت تا: {injury}")
        if not rows:
            lines.append("فهرست بازیکنان خالی است.")
        lines.append(f"\nمصدوم: {injured} نفر | محروم: {suspended} نفر")
        kb = [[InlineKeyboardButton("🩺 درمان بازیکن (هزینه ۵ میلیون تومان)", callback_data="v11_treat_player")], [InlineKeyboardButton("↩️ برگشت", callback_data="owner")]]
        await safe_edit(q, "\n".join(lines)[:3900], InlineKeyboardMarkup(kb)); return

    if data == "v11_treat_player":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        with db() as c:
            rows = c.execute("""SELECT p.id,p.first_name,p.last_name,COALESCE(pc.injury_until,'') injury_until
                FROM club_players cp JOIN players p ON p.id=cp.player_id
                LEFT JOIN player_conditions pc ON pc.player_id=p.id
                WHERE cp.club_id=? AND (COALESCE(pc.injury_until,'')<>'' OR COALESCE(pc.fitness,100)<100) ORDER BY p.id""", (club["id"],)).fetchall()
        if not rows:
            await safe_edit(q, "بازیکن مصدوم یا دارای آمادگی کمتر از ۱۰۰٪ ندارید؛ هزینه‌ای کسر نشد.", back_keyboard("v11_medical")); return
        kb = [[InlineKeyboardButton(f"🩺 {r['first_name']} {r['last_name']} (#{r['id']})", callback_data=f"v11_treat_{r['id']}")] for r in rows]
        kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="v11_medical")])
        await safe_edit(q, "بازیکن مصدوم یا نیازمند ریکاوری را انتخاب کنید. هزینه مراقبت پزشکی ۵ میلیون تومان است و فقط در صورت بودجه کافی کسر می‌شود.", InlineKeyboardMarkup(kb)); return

    if data.startswith("v11_treat_"):
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        try: pid = int(data.rsplit("_", 1)[1])
        except ValueError:
            await safe_edit(q, "شناسه بازیکن نامعتبر است.", back_keyboard("v11_medical")); return
        with db() as c:
            player = c.execute("""SELECT p.first_name,p.last_name,pc.injury_until FROM players p
                JOIN club_players cp ON cp.player_id=p.id LEFT JOIN player_conditions pc ON pc.player_id=p.id
                WHERE p.id=? AND cp.club_id=? AND (COALESCE(pc.injury_until,'')<>'' OR COALESCE(pc.fitness,100)<100)""", (pid, club["id"])).fetchone()
        if not player:
            await safe_edit(q, "این بازیکن مصدومِ باشگاه شما نیست یا قبلاً درمان شده است.", back_keyboard("v11_medical")); return
        ok, answer = change_budget(club["id"], -5_000_000, "درمان بازیکن", f"درمان {player['first_name']} {player['last_name']} (#{pid})")
        if not ok:
            await safe_edit(q, answer, back_keyboard("v11_medical")); return
        with db() as c:
            c.execute("INSERT INTO player_conditions(player_id,fitness,yellow_cards,suspended_matches,injury_until,updated_at) VALUES(?,100,0,0,'',?) ON CONFLICT(player_id) DO UPDATE SET injury_until='', fitness=100, updated_at=excluded.updated_at", (pid, now()))
        await safe_edit(q, f"✅ {player['first_name']} {player['last_name']} درمان/ریکاوری شد.\n{answer}", back_keyboard("v11_medical")); return

    # نسخه ۱۵: قراردادهای هوشمند با مذاکره قاعده‌محور و قابل رد/قبول
    if data.startswith("formation_set_"):
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        formation = data[len("formation_set_"):]
        allowed = {"4-4-2","4-3-3","4-2-3-1","4-1-4-1","4-3-2-1","4-2-2-2","4-3-1-2","4-1-2-1-2","4-5-1","4-4-1-1","3-5-2","3-4-3","3-4-2-1","3-4-1-2","3-1-4-2","3-2-4-1","5-3-2","5-4-1","5-2-3","5-2-1-2"}
        if formation not in allowed:
            await safe_edit(q, "آرایش نامعتبر است.", back_keyboard("v3_tactics")); return
        with db() as c:
            c.execute("INSERT OR IGNORE INTO club_settings(club_id) VALUES(?)", (club['id'],))
            c.execute("UPDATE club_settings SET formation=? WHERE club_id=?", (formation, club['id']))
        tactics = ["متعادل","هجومی","دفاعی","پرس شدید","ضدحمله","مالکانه","بازی از کناره‌ها","پاس کوتاه","توپ بلند","فشار پس از ازدست‌دادن توپ","دفاع عمیق","پرس از جلو","تیکی‌تاکا","پرسینگ گگن‌پرس","بلاک پایین","خط دفاعی بالا","بازی مستقیم","ارسال از جناحین","بازی ترکیبی","ضدحمله سریع","پرس میانه","دفاع فشرده","تمرکز بر ضربات ایستگاهی","کنترل ریتم","حفظ نتیجه","فوتبال عمودی"]
        kb = [[InlineKeyboardButton(t, callback_data="tactic_set_" + t)] for t in tactics]
        kb.append([InlineKeyboardButton("↩️ انتخاب آرایش", callback_data="v3_tactics")])
        await safe_edit(q, f"آرایش {formation} ذخیره شد. حالا تاکتیک تیم را انتخاب کنید:", InlineKeyboardMarkup(kb)); return
    if data.startswith("tactic_set_"):
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        tactic = data[len("tactic_set_"):]
        allowed_tactics = {"متعادل","هجومی","دفاعی","پرس شدید","ضدحمله","مالکانه","بازی از کناره‌ها","پاس کوتاه","توپ بلند","فشار پس از ازدست‌دادن توپ","دفاع عمیق","پرس از جلو"}
        if tactic not in allowed_tactics:
            await safe_edit(q, "تاکتیک نامعتبر است.", back_keyboard("v3_tactics")); return
        with db() as c:
            c.execute("INSERT OR IGNORE INTO club_settings(club_id) VALUES(?)", (club['id'],))
            c.execute("UPDATE club_settings SET tactics=? WHERE club_id=?", (tactic, club['id']))
            row = c.execute("SELECT formation FROM club_settings WHERE club_id=?", (club['id'],)).fetchone()
        await safe_edit(q, f"✅ تاکتیک ذخیره شد.\nچیدمان: {row['formation']}\nتاکتیک: {tactic}", back_keyboard("v3_lineup")); return

    if data == "v15_contracts":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        kb = [
            [InlineKeyboardButton("📝 مذاکره با بازیکنان بازار", callback_data="v15_market_players")],
            [InlineKeyboardButton("🧑‍💼 مذاکره با کادر بازار", callback_data="v15_market_staff")],
            [InlineKeyboardButton("📋 قراردادهای فعال باشگاه", callback_data="v15_active_contracts")],
            [InlineKeyboardButton("↩️ برگشت", callback_data="owner")]
        ]
        await safe_edit(q, "📝 مرکز قرارداد و مذاکره\nمدیر باشگاه می‌تواند پیش‌نویس دستمزد و مدت را پیشنهاد کند؛ شخصیت شبیه‌سازی‌شده بازیکن/عضو کادر بر اساس ارزش، سن و نقش مذاکره می‌کند. این هوش مصنوعی محلی و قاعده‌محور است و به مدل آنلاین متصل نیست. خرید و استخدام فقط در پنجره نقل‌وانتقالات انجام می‌شود.", InlineKeyboardMarkup(kb)); return
    if data == "v15_market_players":
        if not get_club_by_owner(uid):
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        with db() as c: rows = c.execute("SELECT id,first_name,last_name,position,age,nationality,price,photo_file_id FROM players WHERE status='market' ORDER BY price LIMIT 12").fetchall()
        kb = [[InlineKeyboardButton(f"⚽ #{r['id']} {r['first_name']} {r['last_name']} | {r['position']} | {money(r['price'])}", callback_data=f"v15_negotiate_player_{r['id']}")] for r in rows]
        kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="v15_contracts")])
        await safe_edit(q, "بازیکن بازار را برای مذاکره انتخاب کنید. عکس ثبت‌شده و مشخصات هر بازیکن نیز نمایش داده می‌شود:", InlineKeyboardMarkup(kb))
        for r in rows:
            if r['photo_file_id']:
                try: await q.message.reply_photo(photo=r['photo_file_id'],caption=f"⚽ {r['first_name']} {r['last_name']}\nپست: {r['position']} | سن: {r['age']} | ملیت: {r['nationality']}\nارزش بازار: {money(r['price'])}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤝 شروع مذاکره",callback_data=f"v15_negotiate_player_{r['id']}")]]))
                except Exception: pass
        return
    if data == "v15_market_staff":
        if not get_club_by_owner(uid):
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        with db() as c: rows = c.execute("SELECT id,first_name,last_name,role,age,price FROM staff WHERE status='market' ORDER BY price LIMIT 20").fetchall()
        kb = [[InlineKeyboardButton(f"🧑‍💼 #{r['id']} {r['first_name']} {r['last_name']} | {r['role']} | {money(r['price'])}", callback_data=f"v15_negotiate_staff_{r['id']}")] for r in rows]
        kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="v15_contracts")])
        await safe_edit(q, "عضو کادر را برای مذاکره انتخاب کنید:", InlineKeyboardMarkup(kb)); return
    if data.startswith("v15_negotiate_player_") or data.startswith("v15_negotiate_staff_"):
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        if not transfer_window_open():
            await safe_edit(q, "پنجره نقل‌وانتقالات بسته است؛ مذاکره برای ثبت قرارداد جدید فعلاً متوقف است.", back_keyboard("v15_contracts")); return
        typ = 'player' if data.startswith('v15_negotiate_player_') else 'staff'
        asset_id = int(data.rsplit('_',1)[1]); table = 'players' if typ=='player' else 'staff'
        with db() as c: asset = c.execute(f"SELECT * FROM {table} WHERE id=? AND status='market'", (asset_id,)).fetchone()
        if not asset:
            await safe_edit(q, "این بازیکن/عضو کادر دیگر در بازار نیست.", back_keyboard("v15_contracts")); return
        price = int(asset['price']); listing_id = None; seller_club_id = None
        if typ == 'player':
            with db() as c:
                listing = c.execute("SELECT * FROM transfer_listings WHERE player_id=? AND status='active'", (asset_id,)).fetchone()
            if listing:
                price = int(listing['asking_price']); listing_id = int(listing['id']); seller_club_id = int(listing['seller_club_id'])
                if seller_club_id == int(club['id']):
                    await safe_edit(q, "باشگاه شما نمی‌تواند با خودش مذاکره کند.", back_keyboard("v15_market_players")); return
        age = int(asset['age'])
        base_wage = max(500_000, min(100_000_000, price * (10 if typ=='player' else 6) // 1000))
        set_state(context, 'v15_contract_offer', {'asset_type':typ,'asset_id':asset_id,'club_id':club['id'],'asset_name':f"{asset['first_name']} {asset['last_name']}",'asset_price':price,'base_wage':base_wage,'age':age,'role':asset['position'] if typ=='player' else asset['role'],'listing_id':listing_id,'seller_club_id':seller_club_id})
        if typ=='player' and asset['photo_file_id']:
            try: await q.message.reply_photo(photo=asset['photo_file_id'],caption=f"⚽ {asset['first_name']} {asset['last_name']} | {asset['position']} | {asset['age']} سال | {asset['nationality']}\nارزش بازار: {money(price)}")
            except Exception: pass
        await safe_edit(q, f"🤝 مذاکره با {asset['first_name']} {asset['last_name']} آغاز شد.\nنقش: {asset['position'] if typ=='player' else asset['role']} | سن: {age}\n💵 مبلغ انتقال/استخدام: {money(price)}\n\nپیشنهاد اولیه را با این قالب بفرستید:\nدستمزد ماهانه مدت‌ماه پاداش‌امضا بند‌فسخ\nمثال: 12000000 24 5000000 600000000\nبند فسخ سخت اجباری است؛ اگر مقدار را صفر بگذارید، سامانه حداقل بند پیشنهادی را محاسبه می‌کند. مذاکره‌کننده ممکن است پیشنهاد متقابل بدهد.", back_keyboard("v15_contracts")); return
    if data == "v15_contract_accept":
        if not get_club_by_owner(uid):
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        offer = context.user_data.get('v15_pending_contract')
        if not offer:
            await safe_edit(q, "پیشنهاد منقضی شده؛ مذاکره را دوباره شروع کنید.", back_keyboard("v15_contracts")); return
        club = get_club_by_owner(uid)
        if not transfer_window_open():
            await safe_edit(q, "پنجره نقل‌وانتقالات بسته شد؛ قرارداد ثبت نشد.", back_keyboard("v15_contracts")); return
        typ=offer['asset_type']; asset_id=int(offer['asset_id']); table='players' if typ=='player' else 'staff'; own_table='club_players' if typ=='player' else 'club_staff'
        with db() as c:
            asset=c.execute(f"SELECT * FROM {table} WHERE id=? AND status='market'",(asset_id,)).fetchone()
            if not asset:
                await safe_edit(q,"این مورد دیگر در بازار موجود نیست.",back_keyboard("v15_contracts")); return
            cost=int(offer.get('asset_price', asset['price']))+int(offer['bonus']); budget=int(c.execute("SELECT budget FROM clubs WHERE id=?",(club['id'],)).fetchone()['budget'])
            if budget < cost:
                await safe_edit(q,f"❌ بودجه کافی نیست. هزینه اولیه انتقال و پاداش: {money(cost)}؛ موجودی: {money(budget)}",back_keyboard("v15_contracts")); return
            c.execute("UPDATE clubs SET budget=budget-? WHERE id=?",(cost,club['id']))
            c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)",(club['id'],'قرارداد جدید',-cost,f"انتقال/استخدام {asset['first_name']} {asset['last_name']} و پاداش امضا",now()))
            c.execute(f"UPDATE {table} SET status='owned' WHERE id=?",(asset_id,))
            if typ=='player':
                c.execute("INSERT INTO club_players(club_id,player_id,bought_price,joined_at) VALUES(?,?,?,?)",(club['id'],asset_id,int(offer['asset_price']),now()))
                listing = c.execute("SELECT * FROM transfer_listings WHERE player_id=? AND status='active'", (asset_id,)).fetchone()
                if listing:
                    seller = c.execute("SELECT * FROM clubs WHERE id=?", (listing['seller_club_id'],)).fetchone()
                    if seller:
                        c.execute("UPDATE clubs SET budget=budget+? WHERE id=?", (int(offer['asset_price']), seller['id']))
                        c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)", (seller['id'],'فروش بازیکن',int(offer['asset_price']),f"فروش {asset['first_name']} {asset['last_name']} به {club['name']}",now()))
                        c.execute("INSERT INTO transfer_history(player_id,player_name,seller_club_id,seller_name,buyer_club_id,buyer_name,price,transferred_at) VALUES(?,?,?,?,?,?,?,?)",(asset_id,f"{asset['first_name']} {asset['last_name']}",seller['id'],seller['name'],club['id'],club['name'],int(offer['asset_price']),now()))
                    c.execute("UPDATE transfer_listings SET status='sold',sold_to_club_id=?,sold_at=? WHERE player_id=? AND status='active'",(club['id'],now(),asset_id))
                c.execute("INSERT OR IGNORE INTO player_conditions(player_id,fitness,yellow_cards,suspended_matches,injury_until,updated_at) VALUES(?,100,0,0,'',?)", (asset_id,now()))
            else: c.execute("INSERT INTO club_staff(club_id,staff_id,hired_price,hired_at) VALUES(?,?,?,?)",(club['id'],asset_id,int(offer['asset_price']),now()))
            c.execute("INSERT INTO club_contracts(club_id,asset_type,asset_id,monthly_wage,months_total,months_remaining,signing_bonus,release_clause,status,signed_at,updated_at) VALUES(?,?,?,?,?,?,?,?, 'active',?,?)",(club['id'],typ,asset_id,int(offer['wage']),int(offer['months']),int(offer['months']),int(offer['bonus']),int(offer['release_clause']),now(),now()))
        context.user_data.pop('v15_pending_contract',None); set_state(context,None)
        await safe_edit(q,f"✅ قرارداد ثبت شد.\n{offer['asset_name']}\nنوع: {'بازیکن' if typ=='player' else 'کادر فنی'}\nدستمزد ماهانه: {money(offer['wage'])}\nمدت: {offer['months']} ماه\nپاداش امضا: {money(offer['bonus'])}\n🔒 بند فسخ سخت: {money(offer['release_clause'])}\nهزینه اولیه: {money(cost)}\n\nقرارداد و پرداخت اولیه در دفتر مالی ثبت شد.",back_keyboard("v15_contracts")); return
    if data == "v15_contract_reject":
        context.user_data.pop('v15_pending_contract',None); set_state(context,None)
        await safe_edit(q,"❌ پیشنهاد متقابل رد شد؛ بازیکن/عضو کادر به بازار برمی‌گردد و پولی کسر نشده است.",back_keyboard("v15_contracts")); return
    if data == "v15_active_contracts":
        club=get_club_by_owner(uid)
        if not club: await safe_edit(q,"باشگاه تأییدشده ندارید.",back_keyboard("home")); return
        with db() as c: rows=c.execute("SELECT cc.*,CASE WHEN cc.asset_type='player' THEN (SELECT first_name||' '||last_name FROM players WHERE id=cc.asset_id) ELSE (SELECT first_name||' '||last_name FROM staff WHERE id=cc.asset_id) END asset_name FROM club_contracts cc WHERE club_id=? AND status='active' ORDER BY id DESC",(club['id'],)).fetchall()
        if not rows: await safe_edit(q,"قرارداد فعالی ثبت نشده است.",back_keyboard("v15_contracts")); return
        lines=["📋 قراردادهای فعال:"]
        for r in rows: lines.append(f"• {r['asset_name']} ({'بازیکن' if r['asset_type']=='player' else 'کادر'}) | {money(r['monthly_wage'])}/ماه | {r['months_remaining']} ماه باقی‌مانده | 🔒 بند فسخ: {money(r['release_clause'])}")
        lines.append("\nبرای فسخ از گزینه‌های زیر استفاده کنید. بند فسخ سخت قرارداد الزام‌آور است و در فسخ زودهنگام باید مبلغ درج‌شده پرداخت شود.")
        kb=[]
        for r in rows[:15]:
            kb.append([InlineKeyboardButton(f"🔄 تمدید {r['asset_name']}",callback_data=f"v15_renew_{r['id']}"), InlineKeyboardButton(f"فسخ {r['asset_name']}",callback_data=f"v15_terminate_{r['id']}")])
        kb.append([InlineKeyboardButton("↩️ برگشت",callback_data="v15_contracts")])
        await safe_edit(q,"\n".join(lines),InlineKeyboardMarkup(kb)); return
    if data.startswith("v15_renew_") and data not in ("v15_renew_accept", "v15_renew_reject"):
        club=get_club_by_owner(uid); contract_id=int(data.rsplit('_',1)[1])
        if not club: await safe_edit(q,"باشگاه تأییدشده ندارید.",back_keyboard("home")); return
        with db() as c:
            row=c.execute("SELECT * FROM club_contracts WHERE id=? AND club_id=? AND status='active'",(contract_id,club['id'])).fetchone()
            if row:
                asset_table='players' if row['asset_type']=='player' else 'staff'
                asset=c.execute(f"SELECT first_name,last_name FROM {asset_table} WHERE id=?",(row['asset_id'],)).fetchone()
            else: asset=None
        if not row or not asset: await safe_edit(q,"قرارداد فعال پیدا نشد.",back_keyboard("v15_active_contracts")); return
        set_state(context,'v15_renew_offer',{'contract_id':contract_id,'club_id':club['id'],'asset_type':row['asset_type'],'asset_id':row['asset_id'],'asset_name':f"{asset['first_name']} {asset['last_name']}",'current_wage':int(row['monthly_wage']),'remaining':int(row['months_remaining'])})
        await safe_edit(q,f"🔄 مذاکره تمدید قرارداد با {asset['first_name']} {asset['last_name']}\nدستمزد فعلی: {money(row['monthly_wage'])} در ماه | مدت باقی‌مانده: {row['months_remaining']} ماه\n\nپیشنهاد خود را به شکل «دستمزد ماهانه مدت تمدید» بفرستید. مثال: 18000000 24\nطرف قرارداد بر اساس دستمزد فعلی و مدت پیشنهادی پاسخ می‌دهد.",back_keyboard("v15_active_contracts")); return
    if data == "v15_renew_accept":
        pending=context.user_data.get('v15_pending_renewal'); club=get_club_by_owner(uid)
        if not pending or not club: await safe_edit(q,"مذاکره تمدید منقضی شده است.",back_keyboard("v15_contracts")); return
        with db() as c:
            row=c.execute("SELECT id FROM club_contracts WHERE id=? AND club_id=? AND status='active'",(pending['contract_id'],club['id'])).fetchone()
            if not row: await safe_edit(q,"قرارداد دیگر فعال نیست.",back_keyboard("v15_contracts")); return
            c.execute("UPDATE club_contracts SET monthly_wage=?,months_total=months_total+?,months_remaining=months_remaining+?,updated_at=? WHERE id=?",(pending['wage'],pending['months'],pending['months'],now(),pending['contract_id']))
            c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)",(club['id'],'تمدید قرارداد',0,f"تمدید قرارداد {pending['asset_name']} به مدت {pending['months']} ماه؛ دستمزد ماهانه {pending['wage']}",now()))
        context.user_data.pop('v15_pending_renewal',None)
        await safe_edit(q,f"✅ تمدید قرارداد ثبت شد.\n{pending['asset_name']}\nدستمزد جدید ماهانه: {money(pending['wage'])}\nمدت اضافه‌شده: {pending['months']} ماه",back_keyboard("v15_active_contracts")); return
    if data == "v15_renew_reject":
        context.user_data.pop('v15_pending_renewal',None)
        await safe_edit(q,"مذاکره تمدید رد شد؛ قرارداد قبلی بدون تغییر باقی ماند.",back_keyboard("v15_active_contracts")); return
    if data.startswith("v15_terminate_") and not data.startswith("v15_terminate_confirm_"):
        club=get_club_by_owner(uid); contract_id=int(data.rsplit('_',1)[1])
        if not club: await safe_edit(q,"باشگاه تأییدشده ندارید.",back_keyboard("home")); return
        with db() as c: row=c.execute("SELECT * FROM club_contracts WHERE id=? AND club_id=? AND status='active'",(contract_id,club['id'])).fetchone()
        if not row: await safe_edit(q,"قرارداد فعال پیدا نشد.",back_keyboard("v15_active_contracts")); return
        compensation=max(int(row['release_clause'] or 0), int(row['monthly_wage']));
        await safe_edit(q,f"🤝 مذاکره فسخ قرارداد\nطرف قرارداد برای فسخ زودهنگام، غرامت بند فسخ سخت {money(compensation)} درخواست می‌کند.\nاگر تأیید کنید، قرارداد فسخ و بازیکن/عضو کادر آزاد می‌شود.",InlineKeyboardMarkup([[InlineKeyboardButton("✅ پذیرش فسخ و پرداخت غرامت",callback_data=f"v15_terminate_confirm_{contract_id}")],[InlineKeyboardButton("❌ ادامه همکاری",callback_data="v15_active_contracts")]])); return
    if data.startswith("v15_terminate_confirm_"):
        club=get_club_by_owner(uid); contract_id=int(data.rsplit('_',1)[1])
        if not club: await safe_edit(q,"باشگاه تأییدشده ندارید.",back_keyboard("home")); return
        with db() as c:
            row=c.execute("SELECT * FROM club_contracts WHERE id=? AND club_id=? AND status='active'",(contract_id,club['id'])).fetchone()
            if not row: await safe_edit(q,"قرارداد فعال پیدا نشد.",back_keyboard("v15_active_contracts")); return
            fee=max(int(row['release_clause'] or 0), int(row['monthly_wage'])); budget=int(c.execute("SELECT budget FROM clubs WHERE id=?",(club['id'],)).fetchone()['budget'])
            if budget<fee: await safe_edit(q,f"بودجه برای غرامت فسخ کافی نیست: {money(fee)}",back_keyboard("v15_active_contracts")); return
            c.execute("UPDATE clubs SET budget=budget-? WHERE id=?",(fee,club['id']))
            c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)",(club['id'],'غرامت فسخ قرارداد',-fee,f"فسخ قرارداد شماره {contract_id}",now()))
            c.execute("UPDATE club_contracts SET status='terminated',updated_at=? WHERE id=?",(now(),contract_id))
            if row['asset_type']=='player':
                c.execute("DELETE FROM club_players WHERE club_id=? AND player_id=?",(club['id'],row['asset_id']))
                c.execute("UPDATE players SET status='market' WHERE id=?",(row['asset_id'],))
            else:
                c.execute("DELETE FROM club_staff WHERE club_id=? AND staff_id=?",(club['id'],row['asset_id']))
                c.execute("UPDATE staff SET status='market' WHERE id=?",(row['asset_id'],))
        await safe_edit(q,f"قرارداد فسخ شد. غرامت پرداختی: {money(fee)}. فرد آزادشده به بازار برگشت.",back_keyboard("v15_contracts")); return
    if data == "v15_subs":
        club=get_club_by_owner(uid)
        if not club: await safe_edit(q,"باشگاه تأییدشده ندارید.",back_keyboard("home")); return
        with db() as c:
            line=c.execute("SELECT starters,bench FROM club_lineups WHERE club_id=?",(club['id'],)).fetchone()
            if not line or not line['starters'] or not line['bench']:
                await safe_edit(q,"ابتدا ترکیب اصلی و نیمکت را ذخیره کنید.",back_keyboard("v3_lineup")); return
            ids=[int(x) for x in line['starters'].split(',') if x.strip().isdigit()]+[int(x) for x in line['bench'].split(',') if x.strip().isdigit()]
            marks=','.join('?' for _ in ids)
            names={r['id']:f"{r['first_name']} {r['last_name']}" for r in c.execute(f"SELECT id,first_name,last_name FROM players WHERE id IN ({marks})",ids).fetchall()} if ids else {}
            plans=c.execute("SELECT * FROM planned_substitutions WHERE club_id=? AND active=1 ORDER BY minute",(club['id'],)).fetchall()
        lines=["🔁 برنامه تعویض دستی برای مسابقه بعدی", "ابتدا بازیکن خروجی را انتخاب کنید؛ سپس بازیکن ورودی و دقیقه را تعیین کنید.", "حداکثر ۶ تعویض در هر مسابقه."]
        if plans:
            lines.append("\nبرنامه‌های فعلی:")
            lines.extend([f"دقیقه {r['minute']}: {names.get(r['player_out_id'],'بازیکن')} ← {names.get(r['player_in_id'],'بازیکن')}" for r in plans])
        kb=[[InlineKeyboardButton(f"خروجی: {names.get(pid,'بازیکن')} (#{pid})",callback_data=f"v15_sub_out_{pid}")] for pid in [int(x) for x in line['starters'].split(',') if x.strip().isdigit()] if pid in names]
        kb.append([InlineKeyboardButton("🗑 پاک‌کردن برنامه تعویض‌ها",callback_data="v15_sub_clear")])
        kb.append([InlineKeyboardButton("↩️ برگشت",callback_data="owner")])
        await safe_edit(q,"\n".join(lines),InlineKeyboardMarkup(kb)); return
    if data.startswith("v15_sub_out_"):
        club=get_club_by_owner(uid); out_id=int(data.rsplit('_',1)[1])
        if not club: await safe_edit(q,"باشگاه تأییدشده ندارید.",back_keyboard("home")); return
        with db() as c:
            line=c.execute("SELECT bench FROM club_lineups WHERE club_id=?",(club['id'],)).fetchone()
            ids=[int(x) for x in (line['bench'] or '').split(',') if x.strip().isdigit()] if line else []
            marks=','.join('?' for _ in ids)
            rows=c.execute(f"SELECT id,first_name,last_name FROM players WHERE id IN ({marks})",ids).fetchall() if ids else []
        if not rows: await safe_edit(q,"نیمکت خالی است.",back_keyboard("v15_subs")); return
        context.user_data['v15_sub_out']=out_id
        kb=[[InlineKeyboardButton(f"ورودی: {r['first_name']} {r['last_name']}",callback_data=f"v15_sub_in_{r['id']}")] for r in rows]
        kb.append([InlineKeyboardButton("↩️ برگشت",callback_data="v15_subs")])
        await safe_edit(q,"بازیکن ورودی را انتخاب کنید:",InlineKeyboardMarkup(kb)); return
    if data.startswith("v15_sub_in_"):
        club=get_club_by_owner(uid); in_id=int(data.rsplit('_',1)[1]); out_id=context.user_data.get('v15_sub_out')
        if not club or not out_id: await safe_edit(q,"انتخاب خروجی منقضی شده؛ دوباره شروع کنید.",back_keyboard("v15_subs")); return
        with db() as c:
            count=c.execute("SELECT COUNT(*) n FROM planned_substitutions WHERE club_id=? AND active=1",(club['id'],)).fetchone()['n']
            if count>=6: await safe_edit(q,"برای مسابقه بعدی حداکثر ۶ تعویض برنامه‌ریزی می‌شود.",back_keyboard("v15_subs")); return
            valid=c.execute("SELECT 1 FROM club_lineups WHERE club_id=? AND (','||starters||',') LIKE ? AND (','||bench||',') LIKE ?",(club['id'],f"%,{out_id},%",f"%,{in_id},%")).fetchone()
        if not valid: await safe_edit(q,"بازیکن خروجی باید در ترکیب اصلی و ورودی در نیمکت باشد.",back_keyboard("v15_subs")); return
        context.user_data['v15_sub_in']=in_id
        set_state(context,'v15_sub_minute',{'club_id':club['id'],'out_id':out_id,'in_id':in_id})
        await safe_edit(q,"دقیقه تعویض را بفرستید (از ۱ تا ۸۹)، مثلاً ۶۵:",back_keyboard("v15_subs")); return
    if data == "v15_sub_clear":
        club=get_club_by_owner(uid)
        if not club: await safe_edit(q,"باشگاه تأییدشده ندارید.",back_keyboard("home")); return
        with db() as c: c.execute("UPDATE planned_substitutions SET active=0 WHERE club_id=? AND active=1",(club['id'],))
        await safe_edit(q,"برنامه تعویض‌های مسابقه بعدی پاک شد.",back_keyboard("v15_subs")); return
    if data == "v15_schedule":
        club=get_club_by_owner(uid)
        if not club: await safe_edit(q,"باشگاه تأییدشده ندارید.",back_keyboard("home")); return
        with db() as c: rows=c.execute("SELECT f.*,h.name home_name,a.name away_name FROM league_fixtures f JOIN clubs h ON h.id=f.home_club_id JOIN clubs a ON a.id=f.away_club_id WHERE (f.home_club_id=? OR f.away_club_id=?) ORDER BY f.season,f.round_no LIMIT 40",(club['id'],club['id'])).fetchall()
        if not rows: await safe_edit(q,"برنامه‌ای برای فصل ساخته نشده است؛ از ادمین بخواهید برنامه فصل را ایجاد کند.",back_keyboard("owner")); return
        lines=["🗓 برنامه فصل لیگ:"]
        for r in rows:
            status=f"{r['home_goals']}-{r['away_goals']}" if r['status']=='played' else 'در انتظار برگزاری'
            lines.append(f"هفته {r['round_no']}: {r['home_name']} - {r['away_name']} | {status}")
        await safe_edit(q,"\n".join(lines)[:3900],back_keyboard("owner")); return

    # نسخه ۱۴: اسپانسر، تسویه مالی و کنفرانس خبری
    if data == "v14_sponsors":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        with db() as c:
            active = c.execute("SELECT * FROM club_sponsors WHERE club_id=? AND active=1 AND months_remaining>0 ORDER BY id DESC", (club['id'],)).fetchall()
        lines = [f"🤝 اسپانسرهای {club['name']}", f"💰 بودجه: {money(club['budget'])}", ""]
        if active:
            lines.extend([f"• {r['sponsor_name']} | ماهانه {money(r['monthly_amount'])} | {r['months_remaining']} ماه باقی‌مانده" for r in active])
            lines.append("\nبرای دریافت درآمد اسپانسر، تسویه ماهانه را از پنل مالک اجرا کنید.")
            kb = [[InlineKeyboardButton("↩️ برگشت", callback_data="owner")]]
        else:
            lines.append("هنوز اسپانسری ندارید. یک پیشنهاد انتخاب کنید؛ هر باشگاه هم‌زمان فقط یک قرارداد فعال می‌تواند داشته باشد.")
            kb = [
                [InlineKeyboardButton("🥉 اسپانسر محلی — ماهانه ۱۰ میلیون، ۳ ماه", callback_data="v14_sign_sponsor_local")],
                [InlineKeyboardButton("🥈 اسپانسر ملی — ماهانه ۳۰ میلیون، ۳ ماه", callback_data="v14_sign_sponsor_national")],
                [InlineKeyboardButton("🥇 اسپانسر ویژه — ماهانه ۷۵ میلیون، ۳ ماه", callback_data="v14_sign_sponsor_premium")],
                [InlineKeyboardButton("↩️ برگشت", callback_data="owner")]
            ]
        await safe_edit(q, "\n".join(lines), InlineKeyboardMarkup(kb)); return

    if data.startswith("v14_sign_sponsor_"):
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        offers = {
            'v14_sign_sponsor_local': ('اسپانسر محلی', 10_000_000),
            'v14_sign_sponsor_national': ('اسپانسر ملی', 30_000_000),
            'v14_sign_sponsor_premium': ('اسپانسر ویژه', 75_000_000),
        }
        offer = offers.get(data)
        if not offer:
            await safe_edit(q, "پیشنهاد اسپانسر نامعتبر است.", back_keyboard("v14_sponsors")); return
        with db() as c:
            exists = c.execute("SELECT 1 FROM club_sponsors WHERE club_id=? AND active=1 AND months_remaining>0", (club['id'],)).fetchone()
            if exists:
                await safe_edit(q, "باشگاه شما قرارداد اسپانسر فعال دارد.", back_keyboard("v14_sponsors")); return
            c.execute("INSERT INTO club_sponsors(club_id,sponsor_name,monthly_amount,months_remaining,active,signed_at) VALUES(?,?,?,3,1,?)", (club['id'], offer[0], offer[1], now()))
        await safe_edit(q, f"✅ قرارداد سه‌ماهه با {offer[0]} ثبت شد.\nدرآمد ماهانه: {money(offer[1])}\nبرای ثبت درآمد، بخش تسویه ماهانه را اجرا کنید.", back_keyboard("v14_sponsors")); return

    if data == "v14_settle":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        with db() as c:
            period = c.execute("SELECT last_settlement FROM finance_periods WHERE club_id=?", (club['id'],)).fetchone()
            last = period['last_settlement'] if period else ''
        if last:
            try:
                elapsed = (datetime.now() - datetime.strptime(last, '%Y-%m-%d %H:%M:%S')).total_seconds()
            except Exception:
                elapsed = 2_592_001
            if elapsed < 2_592_000:
                days = max(1, int((2_592_000-elapsed)//86400))
                await safe_edit(q, f"⏳ تسویه ماهانه قبلاً انجام شده است؛ حدود {days} روز دیگر دوباره امکان تسویه دارید.", back_keyboard("owner")); return
        with db() as c:
            players = c.execute("SELECT p.id,p.price FROM club_players cp JOIN players p ON p.id=cp.player_id WHERE cp.club_id=?", (club['id'],)).fetchall()
            staff = c.execute("SELECT s.id,s.price FROM club_staff cs JOIN staff s ON s.id=cs.staff_id WHERE cs.club_id=?", (club['id'],)).fetchall()
            contracts = c.execute("SELECT * FROM club_contracts WHERE club_id=? AND status='active' AND months_remaining>0", (club['id'],)).fetchall()
            sponsor = c.execute("SELECT * FROM club_sponsors WHERE club_id=? AND active=1 AND months_remaining>0 ORDER BY id DESC LIMIT 1", (club['id'],)).fetchone()
        contract_wages = {(r['asset_type'], int(r['asset_id'])): int(r['monthly_wage']) for r in contracts}
        player_wages = sum(contract_wages.get(('player', int(r['id'])), max(500_000, min(100_000_000, int(r['price'])*12//1000))) for r in players)
        staff_wages = sum(contract_wages.get(('staff', int(r['id'])), max(300_000, min(30_000_000, int(r['price'])*5//1000))) for r in staff)
        wages = player_wages + staff_wages
        sponsor_income = int(sponsor['monthly_amount']) if sponsor else 0
        # تسویه اتمیک: اگر پول برای کل حقوق کافی نیست، حقوق پرداخت نمی‌شود اما درآمد اسپانسر همچنان دریافت می‌شود.
        with db() as c:
            current = int(c.execute("SELECT budget FROM clubs WHERE id=?", (club['id'],)).fetchone()['budget'])
            wages_paid = current >= wages
            if wages_paid and wages:
                c.execute("UPDATE clubs SET budget=budget-? WHERE id=?", (wages, club['id']))
                c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)", (club['id'], 'حقوق ماهانه', -wages, f'حقوق ماهانه {len(players)} بازیکن و {len(staff)} عضو کادر', now()))
            if sponsor_income:
                c.execute("UPDATE clubs SET budget=budget+? WHERE id=?", (sponsor_income, club['id']))
                c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)", (club['id'], 'درآمد اسپانسر', sponsor_income, f"پرداخت ماهانه {sponsor['sponsor_name']}", now()))
                c.execute("UPDATE club_sponsors SET months_remaining=months_remaining-1,active=CASE WHEN months_remaining-1<=0 THEN 0 ELSE 1 END WHERE id=?", (sponsor['id'],))
            c.execute("UPDATE club_contracts SET months_remaining=months_remaining-1,updated_at=? WHERE club_id=? AND status='active' AND months_remaining>0", (now(), club['id']))
            expired = c.execute("SELECT asset_type,asset_id FROM club_contracts WHERE club_id=? AND status='active' AND months_remaining<=0", (club['id'],)).fetchall()
            for ex in expired:
                if ex['asset_type']=='player':
                    c.execute("DELETE FROM club_players WHERE club_id=? AND player_id=?", (club['id'], ex['asset_id']))
                    c.execute("UPDATE players SET status='market' WHERE id=?", (ex['asset_id'],))
                else:
                    c.execute("DELETE FROM club_staff WHERE club_id=? AND staff_id=?", (club['id'], ex['asset_id']))
                    c.execute("UPDATE staff SET status='market' WHERE id=?", (ex['asset_id'],))
                c.execute("UPDATE club_contracts SET status='expired',updated_at=? WHERE club_id=? AND asset_type=? AND asset_id=? AND status='active'", (now(), club['id'], ex['asset_type'], ex['asset_id']))
            c.execute("INSERT INTO finance_periods(club_id,last_settlement) VALUES(?,?) ON CONFLICT(club_id) DO UPDATE SET last_settlement=excluded.last_settlement", (club['id'], now()))
            new_budget = int(c.execute("SELECT budget FROM clubs WHERE id=?", (club['id'],)).fetchone()['budget'])
        result = ["💼 تسویه ماهانه انجام شد.", f"👥 حقوق بازیکنان: {money(player_wages)}", f"🧑‍💼 حقوق کادر: {money(staff_wages)}"]
        result.append(f"{'✅ حقوق پرداخت شد' if wages_paid else '⚠️ بودجه کافی نبود؛ حقوق این دوره پرداخت نشد'}: {money(wages)}")
        result.append(f"🤝 درآمد اسپانسر: {money(sponsor_income)}")
        if expired: result.append("⌛ قراردادهای پایان‌یافته به بازار برگشتند: " + "، ".join(str(x["asset_id"]) for x in expired))
        result.append(f"💰 موجودی جدید: {money(new_budget)}")
        await safe_edit(q, "\n".join(result), back_keyboard("owner")); return

    if data == "v16_dialogue":
        if not get_club_by_owner(uid):
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        kb = [[InlineKeyboardButton("🧠 گفت‌وگو با کادر فنی", callback_data="v16_talk_coach")],
              [InlineKeyboardButton("⚽ صحبت با بازیکنان", callback_data="v16_talk_player")],
              [InlineKeyboardButton("📣 گفت‌وگو با هواداران", callback_data="v16_talk_fans")],
              [InlineKeyboardButton("🎤 پرسش‌های کنفرانس خبری", callback_data="v16_press_questions")],
              [InlineKeyboardButton("↩️ برگشت", callback_data="owner")]]
        await safe_edit(q, "🎙 مرکز ارتباطات باشگاه\nاین نسخه از هوش مصنوعی محلی و قواعد شبیه‌سازی استفاده می‌کند؛ پاسخ‌ها بر اساس وضعیت باشگاه تولید می‌شوند.", InlineKeyboardMarkup(kb)); return
    if data in ("v16_talk_coach", "v16_talk_player", "v16_talk_fans", "v16_press_questions"):
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        with db() as c:
            recent = c.execute("SELECT m.*,h.name home_name,a.name away_name FROM matches m JOIN clubs h ON h.id=m.home_club_id JOIN clubs a ON a.id=m.away_club_id WHERE m.home_club_id=? OR m.away_club_id=? ORDER BY m.id DESC LIMIT 1", (club['id'],club['id'])).fetchone()
            players_n = c.execute("SELECT COUNT(*) n FROM club_players WHERE club_id=?", (club['id'],)).fetchone()['n']
            staff_n = c.execute("SELECT COUNT(*) n FROM club_staff WHERE club_id=?", (club['id'],)).fetchone()['n']
        if data == "v16_talk_coach":
            msg = f"🧠 جلسه کادر فنی\nسرمربی: «برای موفقیت، باید ترکیب و تاکتیک را با آمادگی بازیکنان هماهنگ کنیم. فعلاً {players_n} بازیکن و {staff_n} عضو کادر داریم.»\nدستیار: «پیشنهاد من بررسی آمادگی، محرومیت‌ها و برنامه تعویض قبل از هر مسابقه است.»"
        elif data == "v16_talk_player":
            msg = f"⚽ جلسه با بازیکنان\nکاپیتان: «بازیکنان می‌خواهند نقش‌شان در تیم روشن باشد و قراردادها منصفانه باشد.»\nمربی: «برای انتخاب ترکیب، آمادگی و محرومیت را بررسی کنید. تعداد بازیکنان ثبت‌شده: {players_n}. قراردادهای دستمزدی در بخش قراردادها مدیریت می‌شوند.»"
        elif data == "v16_talk_fans":
            reputation = int(club['reputation'])
            mood = "هواداران امیدوارند و خواهان فوتبال تهاجمی هستند." if reputation >= 70 else ("هواداران حمایت می‌کنند، اما نتیجه بهتر می‌خواهند." if reputation >= 45 else "هواداران نگران نتایج‌اند و خواهان واکنش فوری هستند.")
            msg = f"📣 صدای هواداران\n{mood}\nاعتبار فعلی باشگاه: {reputation}/100. نتایج بهتر و مدیریت مالی منظم به افزایش اعتماد کمک می‌کند."
        else:
            if not recent:
                msg = "🎤 خبرنگار: «هنوز بازی ثبت‌شده‌ای وجود ندارد. پس از انجام مسابقه می‌توانید به پرسش‌های مربوط به نتیجه و عملکرد پاسخ دهید.»"
            else:
                gf,ga = (recent['home_goals'],recent['away_goals']) if recent['home_club_id']==club['id'] else (recent['away_goals'],recent['home_goals'])
                opponent = recent['away_name'] if recent['home_club_id']==club['id'] else recent['home_name']
                if gf>ga: answer = f"«از نتیجه برابر {opponent} خوشحالیم، اما باید همین تمرکز را حفظ کنیم.»"
                elif gf==ga: answer = f"«مقابل {opponent} امتیاز گرفتیم؛ با این حال، موقعیت‌هایی داشتیم که باید بهتر استفاده می‌کردیم.»"
                else: answer = f"«شکست برابر {opponent} مسئولیت ماست. باید اشتباهات را بررسی کنیم و در بازی بعد واکنش نشان دهیم.»"
                msg = f"🎤 کنفرانس خبری تعاملی\nخبرنگار: «آیا از عملکرد تیم راضی هستید؟»\nسرمربی: {answer}\nخبرنگار: «برنامه بازی بعد چیست؟»\nسرمربی: «بر اساس آمادگی، محرومیت‌ها، ترکیب و آرایش تیم تصمیم می‌گیریم.»"
        await safe_edit(q, msg, InlineKeyboardMarkup([[InlineKeyboardButton("↩️ مرکز ارتباطات", callback_data="v16_dialogue")],[InlineKeyboardButton("🏠 منوی باشگاه", callback_data="owner")]])); return

    if data == "v14_press":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        with db() as c:
            match = c.execute("SELECT m.*,h.name home_name,a.name away_name FROM matches m JOIN clubs h ON h.id=m.home_club_id JOIN clubs a ON a.id=m.away_club_id WHERE m.home_club_id=? OR m.away_club_id=? ORDER BY m.id DESC LIMIT 1", (club['id'], club['id'])).fetchone()
        if not match:
            await safe_edit(q, "هنوز مسابقه‌ای ندارید؛ بعد از اولین بازی می‌توانید کنفرانس خبری را ببینید.", back_keyboard("owner")); return
        if match['home_club_id'] == club['id']:
            gf, ga, opponent = match['home_goals'], match['away_goals'], match['away_name']
        else:
            gf, ga, opponent = match['away_goals'], match['home_goals'], match['home_name']
        if gf > ga:
            quote = f"سرمربی {club['name']}: از تلاش بازیکنان راضی هستم؛ این برد مقابل {opponent} نتیجه کار تیمی بود، اما باید روی بازی بعد تمرکز کنیم."
            mood = "هواداران خوشحال‌اند و انتظار دارند روند پیروزی ادامه پیدا کند."
        elif gf == ga:
            quote = f"سرمربی {club['name']}: مقابل {opponent} امتیاز گرفتیم، اما فرصت‌هایی برای بهتر شدن داشتیم."
            mood = "هواداران از نتیجه راضیِ کامل نیستند و انتظار پیشرفت دارند."
        else:
            quote = f"سرمربی {club['name']}: شکست برابر {opponent} قابل قبول نیست؛ مسئولیت نتیجه را می‌پذیرم و برای اصلاح اشتباهات کار می‌کنیم."
            mood = "هواداران ناراحت‌اند و خواهان واکنش در مسابقه بعدی هستند."
        await safe_edit(q, f"📰 کنفرانس خبری پس از مسابقه\nنتیجه: {match['home_name']} {match['home_goals']}-{match['away_goals']} {match['away_name']}\n\n🎙 {quote}\n\n📣 فضای هواداران: {mood}", back_keyboard("owner")); return

    # نسخه ۱۲: گزارش مالی تفصیلی بر پایه دفتر تراکنش‌ها
    if data == "v12_finance_report":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        with db() as c:
            totals = c.execute("""SELECT COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) income,
                COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) expense, COUNT(*) count
                FROM transactions WHERE club_id=?""", (club["id"],)).fetchone()
            by_kind = c.execute("""SELECT kind, SUM(amount) net, COUNT(*) count FROM transactions
                WHERE club_id=? GROUP BY kind ORDER BY COUNT(*) DESC LIMIT 10""", (club["id"],)).fetchall()
            recent = c.execute("SELECT kind,amount,description,created_at FROM transactions WHERE club_id=? ORDER BY id DESC LIMIT 8", (club["id"],)).fetchall()
        lines = [f"📈 گزارش مالی باشگاه — نسخه ۱۲\nباشگاه: {club['name']}", f"💰 موجودی فعلی: {money(club['budget'])}", f"📥 مجموع درآمدهای ثبت‌شده: {money(totals['income'])}", f"📤 مجموع هزینه‌های ثبت‌شده: {money(totals['expense'])}", f"🧾 تعداد تراکنش‌ها: {totals['count']}", "", "📂 دسته‌بندی تراکنش‌ها:"]
        lines.extend(f"• {r['kind']}: خالص {money(r['net'])} | {r['count']} مورد" for r in by_kind)
        lines.extend(["", "🕘 آخرین تراکنش‌ها:"])
        lines.extend(f"• {r['created_at']} | {r['kind']} | {money(r['amount'])}\n  {r['description'][:100]}" for r in recent)
        if not recent: lines.append("هنوز تراکنشی ثبت نشده است.")
        await safe_edit(q, "\n".join(lines)[:3900], back_keyboard("owner")); return

    if data == "v6_match_center":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("home")); return
        with db() as c:
            line = c.execute("SELECT starters FROM club_lineups WHERE club_id=?", (club["id"],)).fetchone()
            slots = c.execute("SELECT ls.slot_number,ls.field_position,p.first_name,p.last_name FROM lineup_slots ls JOIN players p ON p.id=ls.player_id WHERE ls.club_id=? ORDER BY ls.slot_number", (club["id"],)).fetchall()
            active_loans = c.execute("SELECT COUNT(*) n FROM loan_records WHERE from_club_id=? AND active=1", (club["id"],)).fetchone()["n"]
        pos_text = "\n".join(f"{r['slot_number']}. {r['field_position']} — {r['first_name']} {r['last_name']}" for r in slots) or "هنوز پست‌های ترکیب ذخیره نشده‌اند."
        await safe_edit(q, f"🧠 مرکز مدیریت تیم — نسخه ۶\nباشگاه: {club['name']}\nترکیب: {'ذخیره شده' if line and line['starters'] else 'ثبت نشده'}\nقرض‌های فعال از باشگاه شما: {active_loans}\n\nپست‌های ثبت‌شده:\n{pos_text}", back_keyboard("owner")); return

    # انتخاب تعاملی بازیکن و پست برای ترکیب نسخه ۶
    if data.startswith("lineup_pick_"):
        form = context.user_data.get("form", {})
        if context.user_data.get("state") != "lineup_interactive" or not form:
            await safe_edit(q, "فرآیند ترکیب منقضی شده؛ دوباره شروع کنید.", back_keyboard("v3_lineup")); return
        pid = int(data.rsplit("_", 1)[1])
        if pid in form.get("starters", []) or pid in form.get("bench", []):
            await q.answer("این بازیکن قبلاً انتخاب شده است.", show_alert=True); return
        with db() as c:
            player = c.execute("SELECT p.id,p.first_name,p.last_name FROM players p JOIN club_players cp ON cp.player_id=p.id WHERE p.id=? AND cp.club_id=? AND cp.loan_from_club_id IS NULL", (pid, form["club_id"])).fetchone()
        if not player:
            await safe_edit(q, "این بازیکن متعلق به تیم شما نیست.", back_keyboard("v3_lineup")); return
        form["selected_player"] = pid
        context.user_data["form"] = form
        positions = ["دروازه‌بان", "دفاع راست", "دفاع وسط", "دفاع چپ", "هافبک دفاعی", "هافبک مرکزی", "هافبک هجومی", "وینگر راست", "وینگر چپ", "مهاجم"]
        kb = [[InlineKeyboardButton(pos, callback_data="lineup_pos_" + str(i)) for i,pos in enumerate(positions[j:j+2], start=j)] for j in range(0,len(positions),2)]
        kb.append([InlineKeyboardButton("↩️ لغو ترکیب", callback_data="v3_lineup")])
        await safe_edit(q, f"پست بازیکن {player['first_name']} {player['last_name']} را انتخاب کنید:", InlineKeyboardMarkup(kb)); return

    if data.startswith("lineup_pos_"):
        form = context.user_data.get("form", {})
        if context.user_data.get("state") != "lineup_interactive" or "selected_player" not in form:
            await safe_edit(q, "انتخاب بازیکن منقضی شده؛ دوباره شروع کنید.", back_keyboard("v3_lineup")); return
        positions = ["دروازه‌بان", "دفاع راست", "دفاع وسط", "دفاع چپ", "هافبک دفاعی", "هافبک مرکزی", "هافبک هجومی", "وینگر راست", "وینگر چپ", "مهاجم"]
        try: pos = positions[int(data.rsplit("_",1)[1])]
        except Exception:
            await safe_edit(q, "پست نامعتبر است.", back_keyboard("v3_lineup")); return
        pid = form.pop("selected_player")
        if len(form["starters"]) < 11:
            form["starters"].append(pid)
            form["positions"][str(pid)] = pos
        context.user_data["form"] = form
        with db() as c:
            owned = c.execute("SELECT p.id,p.first_name,p.last_name FROM club_players cp JOIN players p ON p.id=cp.player_id WHERE cp.club_id=? AND cp.loan_from_club_id IS NULL ORDER BY p.id", (form["club_id"],)).fetchall()
        if len(form["starters"]) < 11:
            selected = set(form["starters"])
            kb = [[InlineKeyboardButton(f"{r['first_name']} {r['last_name']} (#{r['id']})", callback_data=f"lineup_pick_{r['id']}")] for r in owned if r["id"] not in selected]
            kb.append([InlineKeyboardButton("↩️ لغو", callback_data="v3_lineup")])
            await safe_edit(q, f"✅ {len(form['starters'])}/۱۱ بازیکن ثبت شد.\nپست انتخاب‌شده: {pos}\nحالا بازیکن بعدی را انتخاب کنید:", InlineKeyboardMarkup(kb)); return
        kb = [[InlineKeyboardButton(f"نیمکت: {r['first_name']} {r['last_name']} (#{r['id']})", callback_data=f"lineup_benchpick_{r['id']}")] for r in owned if r["id"] not in set(form["starters"])]
        kb.append([InlineKeyboardButton("✅ پایان انتخاب نیمکت", callback_data="lineup_bench_done")])
        await safe_edit(q, "ترکیب اصلی ۱۱ نفره تکمیل شد. بازیکنان نیمکت را یکی‌یکی انتخاب کنید یا پایان انتخاب نیمکت را بزنید (حداکثر ۱۱ نفر).", InlineKeyboardMarkup(kb)); return

    if data.startswith("lineup_benchpick_"):
        form = context.user_data.get("form", {})
        if context.user_data.get("state") != "lineup_interactive":
            await safe_edit(q, "فرآیند ترکیب منقضی شده است.", back_keyboard("v3_lineup")); return
        pid = int(data.rsplit("_",1)[1])
        if pid in form["starters"] or pid in form["bench"] or len(form["bench"]) >= 11:
            await q.answer("این انتخاب تکراری است یا نیمکت پر شده.", show_alert=True); return
        form["bench"].append(pid); context.user_data["form"] = form
        with db() as c:
            owned = c.execute("SELECT p.id,p.first_name,p.last_name FROM club_players cp JOIN players p ON p.id=cp.player_id WHERE cp.club_id=? AND cp.loan_from_club_id IS NULL ORDER BY p.id", (form["club_id"],)).fetchall()
        kb = [[InlineKeyboardButton(f"نیمکت: {r['first_name']} {r['last_name']} (#{r['id']})", callback_data=f"lineup_benchpick_{r['id']}")] for r in owned if r["id"] not in set(form["starters"] + form["bench"])]
        kb.append([InlineKeyboardButton("✅ پایان انتخاب نیمکت", callback_data="lineup_bench_done")])
        await safe_edit(q, f"بازیکن نیمکت اضافه شد ({len(form['bench'])}/۱۱). نفر بعدی را انتخاب کنید یا پایان را بزنید.", InlineKeyboardMarkup(kb)); return

    if data == "lineup_bench_done":
        form = context.user_data.get("form", {})
        if context.user_data.get("state") != "lineup_interactive" or len(form.get("starters", [])) != 11:
            await safe_edit(q, "ابتدا ۱۱ بازیکن اصلی را تکمیل کنید.", back_keyboard("v3_lineup")); return
        context.user_data["form"] = form
        with db() as c:
            rows = c.execute("SELECT p.id,p.first_name,p.last_name FROM players p JOIN club_players cp ON cp.player_id=p.id WHERE cp.club_id=? ORDER BY p.id", (form["club_id"],)).fetchall()
        kb = [[InlineKeyboardButton(f"کاپیتان: {r['first_name']} {r['last_name']} (#{r['id']})", callback_data=f"lineup_captainpick_{r['id']}")] for r in rows if r["id"] in form["starters"]]
        kb.append([InlineKeyboardButton("↩️ لغو", callback_data="v3_lineup")])
        await safe_edit(q, "کاپیتان اول را از بین ۱۱ بازیکن اصلی انتخاب کنید؛ سپس نفر دوم و سوم را تعیین می‌کنید:", InlineKeyboardMarkup(kb)); return

    if data.startswith("lineup_captainpick_") or data.startswith("lineup_captain2pick_") or data.startswith("lineup_captain3pick_"):
        form = context.user_data.get("form", {})
        if context.user_data.get("state") != "lineup_interactive" or not form:
            await safe_edit(q, "فرآیند ترکیب منقضی شده؛ دوباره شروع کنید.", back_keyboard("v3_lineup")); return
        pid = int(data.rsplit("_", 1)[1])
        starters = form.get("starters", [])
        if pid not in starters:
            await safe_edit(q, "هر سه کاپیتان باید از بین ۱۱ بازیکن اصلی باشند.", back_keyboard("v3_lineup")); return
        if data.startswith("lineup_captainpick_"):
            form["captain1"] = pid
            context.user_data["form"] = form
            with db() as c:
                rows = c.execute("SELECT p.id,p.first_name,p.last_name FROM players p JOIN club_players cp ON cp.player_id=p.id WHERE cp.club_id=? ORDER BY p.id", (form["club_id"],)).fetchall()
            kb = [[InlineKeyboardButton(f"کاپیتان دوم: {r['first_name']} {r['last_name']}", callback_data=f"lineup_captain2pick_{r['id']}")] for r in rows if r["id"] in starters and r["id"] != pid]
            kb.append([InlineKeyboardButton("↩️ لغو", callback_data="v3_lineup")])
            await safe_edit(q, "کاپیتان اول ثبت شد. کاپیتان دوم را انتخاب کنید:", InlineKeyboardMarkup(kb)); return
        if data.startswith("lineup_captain2pick_"):
            if pid == form.get("captain1"):
                await q.answer("کاپیتان‌ها باید سه بازیکن متفاوت باشند.", show_alert=True); return
            form["captain2"] = pid
            context.user_data["form"] = form
            with db() as c:
                rows = c.execute("SELECT p.id,p.first_name,p.last_name FROM players p JOIN club_players cp ON cp.player_id=p.id WHERE cp.club_id=? ORDER BY p.id", (form["club_id"],)).fetchall()
            kb = [[InlineKeyboardButton(f"کاپیتان سوم: {r['first_name']} {r['last_name']}", callback_data=f"lineup_captain3pick_{r['id']}")] for r in rows if r["id"] in starters and r["id"] not in (form.get("captain1"), pid)]
            kb.append([InlineKeyboardButton("↩️ لغو", callback_data="v3_lineup")])
            await safe_edit(q, "کاپیتان دوم ثبت شد. کاپیتان سوم را انتخاب کنید:", InlineKeyboardMarkup(kb)); return
        if pid in (form.get("captain1"), form.get("captain2")):
            await q.answer("سه کاپیتان باید متفاوت باشند.", show_alert=True); return
        with db() as c:
            starters_text = ",".join(map(str, form["starters"]))
            bench_text = ",".join(map(str, form["bench"]))
            c.execute("INSERT INTO club_lineups(club_id,starters,bench,saved_at) VALUES(?,?,?,?) ON CONFLICT(club_id) DO UPDATE SET starters=excluded.starters,bench=excluded.bench,saved_at=excluded.saved_at", (form["club_id"], starters_text, bench_text, now()))
            c.execute("DELETE FROM lineup_slots WHERE club_id=?", (form["club_id"],))
            for slot, player_id in enumerate(form["starters"], start=1):
                c.execute("INSERT INTO lineup_slots(club_id,slot_number,player_id,field_position) VALUES(?,?,?,?)", (form["club_id"], slot, player_id, form["positions"][str(player_id)]))
            c.execute("INSERT OR IGNORE INTO club_settings(club_id) VALUES(?)", (form["club_id"],))
            c.execute("UPDATE club_settings SET captain_id=?,captain2_id=?,captain3_id=? WHERE club_id=?", (form["captain1"], form["captain2"], pid, form["club_id"]))
        set_state(context, None)
        await safe_edit(q, "✅ ترکیب، پست‌ها، نیمکت و هر سه کاپیتان ذخیره شدند.", owner_keyboard()); return

    # بازار و باشگاه مالک
    if data == "club_info":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه تأییدشده ندارید.", back_keyboard("owner")); return
        with db() as c:
            pc = c.execute("SELECT COUNT(*) n FROM club_players WHERE club_id=?", (club["id"],)).fetchone()["n"]
            sc = c.execute("SELECT COUNT(*) n FROM club_staff WHERE club_id=?", (club["id"],)).fetchone()["n"]
        await safe_edit(q, f"🏟 {club['name']}\n📍 {club['city']}، {club['country']}\n"
                           f"💰 بودجه: {money(club['budget'])}\n⭐ اعتبار: {club['reputation']}/100\n"
                           f"👥 بازیکنان: {pc}\n🧑‍💼 کادر: {sc}\n"
                           f"🔄 پنجره نقل‌وانتقالات: {'باز' if transfer_window_open() else 'بسته'}",
                        back_keyboard("owner")); return
    if data == "club_finance":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه ندارید.", back_keyboard("owner")); return
        with db() as c:
            rows = c.execute("SELECT * FROM transactions WHERE club_id=? ORDER BY id DESC LIMIT 15",
                             (club["id"],)).fetchall()
        text = f"💰 دفتر مالی {club['name']}\nموجودی: {money(club['budget'])}\n\n"
        text += "\n".join(f"{r['created_at']} | {r['kind']} | {money(r['amount'])}\n{r['description']}" for r in rows)
        if not rows:
            text += "هنوز تراکنشی ثبت نشده است."
        await safe_edit(q, text[:3900], back_keyboard("owner")); return
    if data == "my_players":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه ندارید.", back_keyboard("owner")); return
        with db() as c:
            rows = c.execute("""SELECT p.*, cp.bought_price FROM club_players cp
                JOIN players p ON p.id=cp.player_id WHERE cp.club_id=? ORDER BY p.id""",
                (club["id"],)).fetchall()
        text = f"👥 بازیکنان {club['name']}:\n\n"
        text += "\n".join(f"#{r['id']} {r['first_name']} {r['last_name']} | {r['position']} | {r['age']} سال | ارزش {money(r['price'])}" for r in rows)
        if not rows: text += "بازیکنی ندارید."
        await safe_edit(q, text[:3900], back_keyboard("owner")); return
    if data == "my_staff":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه ندارید.", back_keyboard("owner")); return
        with db() as c:
            rows = c.execute("""SELECT s.* FROM club_staff cs JOIN staff s ON s.id=cs.staff_id
                WHERE cs.club_id=? ORDER BY s.id""", (club["id"],)).fetchall()
        text = f"🧑‍💼 کادر فنی {club['name']}:\n\n"
        text += "\n".join(f"#{r['id']} {r['first_name']} {r['last_name']} | {r['role']} | سبک: {r['style']} | {money(r['price'])}" for r in rows)
        if not rows: text += "عضو کادری ندارید."
        await safe_edit(q, text[:3900], back_keyboard("owner")); return

    if data == "market_players":
        with db() as c:
            rows = c.execute("SELECT p.*,tl.asking_price,sc.name AS seller_name FROM players p LEFT JOIN transfer_listings tl ON tl.player_id=p.id AND tl.status='active' LEFT JOIN clubs sc ON sc.id=tl.seller_club_id WHERE p.status='market' ORDER BY p.id LIMIT 30").fetchall()
        text = f"⚽ بازار بازیکنان | پنجره: {'باز' if transfer_window_open() else 'بسته'}\n\n"
        kb = []
        for p in rows:
            cost = p['asking_price'] if p['asking_price'] is not None else p['price']
            seller_label = f" | فروشنده: {p['seller_name']}" if p['seller_name'] else " | بازار آزاد"
            text += f"#{p['id']} {p['first_name']} {p['last_name']} | {p['position']} | {p['age']} سال | قیمت: {money(cost)}{seller_label}\n"
            if not is_admin(uid):
                kb.append([InlineKeyboardButton(f"خرید #{p['id']} | {money(cost)}", callback_data=f"v15_negotiate_player_{p['id']}")])
        if not rows: text += "بازیکنی در بازار نیست."
        kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="owner" if not is_admin(uid) else "admin")])
        await safe_edit(q, text[:3900], InlineKeyboardMarkup(kb))
        if not is_admin(uid):
            for p in rows[:10]:
                if p['photo_file_id']:
                    cost = p['asking_price'] if p['asking_price'] is not None else p['price']
                    try: await q.message.reply_photo(photo=p['photo_file_id'],caption=f"⚽ {p['first_name']} {p['last_name']}\nپست: {p['position']} | سن: {p['age']} | ملیت: {p['nationality']}\nقیمت: {money(cost)}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤝 مذاکره و خرید",callback_data=f"v15_negotiate_player_{p['id']}")]]))
                    except Exception: pass
        return

    if data.startswith("buy_player_"):
        pid = int(data.rsplit("_", 1)[1])
        await safe_edit(q, "از این نسخه به بعد هیچ بازیکنی بدون مذاکره و قرارداد وارد باشگاه نمی‌شود. مذاکره را از بازار بازیکنان شروع کنید.", back_keyboard("v15_market_players")); return
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "فقط مالک باشگاه می‌تواند خرید کند.", back_keyboard()); return
        if not transfer_window_open():
            await safe_edit(q, "❌ پنجره نقل‌وانتقالات بسته است.", back_keyboard("market_players")); return
        pid = int(data.rsplit("_", 1)[1])
        seller_owner_id = None
        seller_name = "بازار آزاد"
        with db() as c:
            p = c.execute("SELECT * FROM players WHERE id=? AND status='market'", (pid,)).fetchone()
            if not p:
                await safe_edit(q, "این بازیکن دیگر در بازار نیست.", back_keyboard("market_players")); return
            listing = c.execute("SELECT * FROM transfer_listings WHERE player_id=? AND status='active'", (pid,)).fetchone()
            cost = int(listing["asking_price"] if listing else p["price"])
            current = int(c.execute("SELECT budget FROM clubs WHERE id=?", (club["id"],)).fetchone()["budget"])
            if listing and int(listing["seller_club_id"]) == int(club["id"]):
                await safe_edit(q, "❌ باشگاه شما نمی‌تواند بازیکن خودش را بخرد.", back_keyboard("market_players")); return
            if current < cost:
                await safe_edit(q, f"💰 موجودی: {money(current)}\n💸 قیمت درخواستی: {money(cost)}\n❌ بودجه کافی نیست.", back_keyboard("market_players")); return
            # پرداخت خریدار و انتقال مالکیت؛ در آگهی‌های باشگاهی درآمد به فروشنده می‌رسد.
            c.execute("UPDATE clubs SET budget=budget-? WHERE id=?", (cost, club["id"]))
            c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)", (club["id"], "خرید بازیکن", -cost, f"خرید {p['first_name']} {p['last_name']} (#{pid})", now()))
            c.execute("INSERT INTO club_players(club_id,player_id,bought_price,joined_at) VALUES(?,?,?,?)", (club["id"], pid, cost, now()))
            c.execute("INSERT OR IGNORE INTO player_conditions(player_id,fitness,yellow_cards,suspended_matches,injury_until,updated_at) VALUES(?,100,0,0,'',?)", (pid, now()))
            c.execute("UPDATE players SET status='owned',price=? WHERE id=?", (cost, pid))
            if listing:
                seller = c.execute("SELECT * FROM clubs WHERE id=?", (listing["seller_club_id"],)).fetchone()
                if seller:
                    seller_owner_id = int(seller["owner_id"])
                    seller_name = seller["name"]
                    c.execute("UPDATE clubs SET budget=budget+? WHERE id=?", (cost, seller["id"]))
                    c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)", (seller["id"], "فروش بازیکن", cost, f"فروش {p['first_name']} {p['last_name']} به {club['name']} (#{pid})", now()))
                c.execute("UPDATE transfer_listings SET status='sold',sold_to_club_id=?,sold_at=? WHERE player_id=? AND status='active'", (club["id"], now(), pid))
                c.execute("INSERT INTO transfer_history(player_id,player_name,seller_club_id,seller_name,buyer_club_id,buyer_name,price,transferred_at) VALUES(?,?,?,?,?,?,?,?)", (pid, f"{p['first_name']} {p['last_name']}", listing["seller_club_id"], seller_name, club["id"], club["name"], cost, now()))
            msg = f"موجودی جدید: {money(current-cost)}"
        await safe_edit(q, f"✅ {p['first_name']} {p['last_name']} به باشگاه {club['name']} پیوست.\nقیمت انتقال: {money(cost)}\n💰 {msg}", back_keyboard("owner"))
        if seller_owner_id:
            try:
                await context.bot.send_message(seller_owner_id, f"💰 بازیکن {p['first_name']} {p['last_name']} به باشگاه {club['name']} فروخته شد.\nواریزی به باشگاه شما: {money(cost)}")
            except Exception:
                pass
        await send_channel(context, f"🔄 نقل‌وانتقال: {p['first_name']} {p['last_name']} از {seller_name} به {club['name']} منتقل شد؛ مبلغ {money(cost)}.")
        return

    if data == "sell_player":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه ندارید.", back_keyboard()); return
        if not transfer_window_open():
            await safe_edit(q, "❌ پنجره نقل‌وانتقالات بسته است.", back_keyboard("owner")); return
        with db() as c:
            rows = c.execute("SELECT p.* FROM club_players cp JOIN players p ON p.id=cp.player_id WHERE cp.club_id=? AND cp.loan_from_club_id IS NULL", (club["id"],)).fetchall()
        kb = [[InlineKeyboardButton(f"🏷 {p['first_name']} {p['last_name']} (#{p['id']})", callback_data=f"sell_confirm_{p['id']}")] for p in rows]
        kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="owner")])
        await safe_edit(q, "بازیکن را انتخاب کنید و قیمت درخواستی خودتان را وارد کنید. تا زمان خرید توسط باشگاه دیگر، پولی دریافت نمی‌کنید.", InlineKeyboardMarkup(kb)); return

    if data.startswith("sell_confirm_"):
        club = get_club_by_owner(uid)
        if not club or not transfer_window_open():
            await safe_edit(q, "عملیات مجاز نیست یا پنجره بسته است.", back_keyboard("owner")); return
        pid = int(data.rsplit("_", 1)[1])
        with db() as c:
            p = c.execute("SELECT p.* FROM players p JOIN club_players cp ON cp.player_id=p.id WHERE p.id=? AND cp.club_id=? AND cp.loan_from_club_id IS NULL", (pid, club["id"])).fetchone()
            if not p:
                await safe_edit(q, "بازیکن پیدا نشد یا بازیکن قرضی است.", back_keyboard("owner")); return
            active = c.execute("SELECT 1 FROM transfer_listings WHERE player_id=? AND status='active'", (pid,)).fetchone()
            if active:
                await safe_edit(q, "این بازیکن از قبل در لیست فروش است.", back_keyboard("sale_listings")); return
        set_state(context, "sale_price", {"club_id": club["id"], "player_id": pid})
        await safe_edit(q, f"قیمت درخواستی برای {p['first_name']} {p['last_name']} را به تومان وارد کنید.\nمثال: 250000000\nتا خرید باشگاه دیگر هیچ پولی واریز نمی‌شود.", back_keyboard("sell_player")); return

    if data == "sale_listings":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه ندارید.", back_keyboard()); return
        with db() as c:
            rows = c.execute("SELECT tl.player_id,tl.asking_price,p.first_name,p.last_name FROM transfer_listings tl JOIN players p ON p.id=tl.player_id WHERE tl.seller_club_id=? AND tl.status='active' ORDER BY tl.id DESC", (club["id"],)).fetchall()
        text_out = "🏷 بازیکنان باشگاه شما در لیست فروش:\n\n"
        kb = []
        for r in rows:
            text_out += f"#{r['player_id']} {r['first_name']} {r['last_name']} — قیمت: {money(r['asking_price'])}\n"
            kb.append([InlineKeyboardButton(f"❌ لغو فروش #{r['player_id']}", callback_data=f"cancel_listing_{r['player_id']}")])
        if not rows: text_out += "بازیکنی در لیست فروش ندارید."
        kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="owner")])
        await safe_edit(q, text_out[:3900], InlineKeyboardMarkup(kb)); return

    if data.startswith("cancel_listing_"):
        club = get_club_by_owner(uid)
        pid = int(data.rsplit("_", 1)[1])
        if not club:
            await safe_edit(q, "باشگاه پیدا نشد.", back_keyboard()); return
        with db() as c:
            listing = c.execute("SELECT * FROM transfer_listings WHERE player_id=? AND seller_club_id=? AND status='active'", (pid, club["id"])).fetchone()
            player = c.execute("SELECT * FROM players WHERE id=? AND status='market'", (pid,)).fetchone()
            if not listing or not player:
                await safe_edit(q, "این آگهی فعال نیست یا بازیکن قبلاً خریداری شده است.", back_keyboard("sale_listings")); return
            c.execute("UPDATE transfer_listings SET status='cancelled' WHERE player_id=? AND status='active'", (pid,))
            c.execute("UPDATE players SET status='owned',price=? WHERE id=?", (listing["original_price"], pid))
            c.execute("INSERT INTO club_players(club_id,player_id,bought_price,joined_at) VALUES(?,?,?,?)", (club["id"], pid, listing["original_price"], now()))
        await safe_edit(q, f"✅ فروش {player['first_name']} {player['last_name']} لغو شد و بازیکن به باشگاه برگشت. پولی جابه‌جا نشد.", back_keyboard("sale_listings")); return

    if data == "transfer_history":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه ندارید.", back_keyboard()); return
        with db() as c:
            rows = c.execute("SELECT * FROM transfer_history WHERE seller_club_id=? OR buyer_club_id=? ORDER BY id DESC LIMIT 20", (club["id"], club["id"])).fetchall()
        text_out = f"📚 تاریخچه نقل‌وانتقالات — {club['name']}\n\n"
        for r in rows:
            direction = "فروش" if r["seller_club_id"] == club["id"] else "خرید"
            text_out += f"{r['transferred_at']} | {direction} | {r['player_name']}\n{r['seller_name']} → {r['buyer_name']} | {money(r['price'])}\n\n"
        if not rows: text_out += "هنوز نقل‌وانتقالی بین باشگاه‌ها ثبت نشده است."
        await safe_edit(q, text_out[:3900], back_keyboard("owner")); return

    if data == "loan_player":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه ندارید.", back_keyboard()); return
        if not transfer_window_open():
            await safe_edit(q, "پنجره نقل‌وانتقالات بسته است.", back_keyboard("owner")); return
        with db() as c:
            rows = c.execute("""SELECT p.* FROM club_players cp JOIN players p ON p.id=cp.player_id
                WHERE cp.club_id=? AND cp.loan_from_club_id IS NULL ORDER BY p.id""", (club["id"],)).fetchall()
        kb = [[InlineKeyboardButton(f"قرض دادن {p['first_name']} {p['last_name']} (#{p['id']})", callback_data=f"loan_choose_{p['id']}")] for p in rows]
        kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="owner")])
        await safe_edit(q, "نسخه ۵ — بازیکن را برای قرض رسمی به یک باشگاه دیگر انتخاب کنید:", InlineKeyboardMarkup(kb)); return

    if data.startswith("loan_choose_"):
        club = get_club_by_owner(uid)
        if not club or not transfer_window_open():
            await safe_edit(q, "عملیات مجاز نیست یا پنجره نقل‌وانتقالات بسته است.", back_keyboard("owner")); return
        pid = int(data.rsplit("_", 1)[1])
        with db() as c:
            p = c.execute("SELECT p.id,p.first_name,p.last_name FROM players p JOIN club_players cp ON cp.player_id=p.id WHERE p.id=? AND cp.club_id=? AND cp.loan_from_club_id IS NULL", (pid, club["id"])).fetchone()
            targets = c.execute("SELECT id,name FROM clubs WHERE id<>? ORDER BY name", (club["id"],)).fetchall()
        if not p:
            await safe_edit(q, "بازیکن در باشگاه شما پیدا نشد یا قبلاً قرض داده شده است.", back_keyboard("owner")); return
        if not targets:
            await safe_edit(q, "برای قرض رسمی حداقل یک باشگاه دیگر لازم است.", back_keyboard("owner")); return
        kb = [[InlineKeyboardButton(f"{t['name']} (#{t['id']})", callback_data=f"loan_to_{pid}_{t['id']}")] for t in targets]
        kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="loan_player")])
        await safe_edit(q, f"مقصد قرض بازیکن {p['first_name']} {p['last_name']} را انتخاب کنید. مدت قرض ۶ ماه است:", InlineKeyboardMarkup(kb)); return

    if data.startswith("loan_to_"):
        club = get_club_by_owner(uid)
        if not club or not transfer_window_open():
            await safe_edit(q, "عملیات مجاز نیست.", back_keyboard("owner")); return
        try:
            _, _, pid_s, target_s = data.split("_")
            pid, target_id = int(pid_s), int(target_s)
        except Exception:
            await safe_edit(q, "درخواست قرض نامعتبر است.", back_keyboard("owner")); return
        from datetime import timedelta
        with db() as c:
            p = c.execute("SELECT p.* FROM players p JOIN club_players cp ON cp.player_id=p.id WHERE p.id=? AND cp.club_id=? AND cp.loan_from_club_id IS NULL", (pid, club["id"])).fetchone()
            target = c.execute("SELECT id,name,owner_id FROM clubs WHERE id=? AND id<>?", (target_id, club["id"])).fetchone()
            if not p or not target:
                await safe_edit(q, "بازیکن یا باشگاه مقصد پیدا نشد.", back_keyboard("owner")); return
            end_date = (datetime.now() + timedelta(days=183)).strftime("%Y-%m-%d %H:%M:%S")
            c.execute("UPDATE club_players SET club_id=?,loan_from_club_id=?,loan_until=? WHERE player_id=? AND club_id=?", (target_id, club["id"], end_date, pid, club["id"]))
            c.execute("INSERT INTO loan_records(player_id,from_club_id,to_club_id,start_date,end_date,active) VALUES(?,?,?,?,?,1)", (pid, club["id"], target_id, now(), end_date))
        await safe_edit(q, f"✅ قرض رسمی ثبت شد.\nبازیکن: {p['first_name']} {p['last_name']}\nباشگاه مبدأ: {club['name']}\nباشگاه مقصد: {target['name']}\nمدت: ۶ ماه\nپایان قرض: {end_date}", back_keyboard("owner"))
        try: await context.bot.send_message(target["owner_id"], f"📥 بازیکن قرضی به باشگاه شما اضافه شد: {p['first_name']} {p['last_name']} از {club['name']} تا {end_date}.")
        except Exception: pass
        return

    if data == "loan_return":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه ندارید.", back_keyboard()); return
        with db() as c:
            rows = c.execute("SELECT p.id,p.first_name,p.last_name,cp.loan_from_club_id FROM club_players cp JOIN players p ON p.id=cp.player_id WHERE cp.club_id=? AND cp.loan_from_club_id IS NOT NULL", (club["id"],)).fetchall()
        kb = [[InlineKeyboardButton(f"بازگرداندن {r['first_name']} {r['last_name']} (#{r['id']})", callback_data=f"loan_return_{r['id']}")] for r in rows]
        kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="owner")])
        await safe_edit(q, "بازیکنان قرضی باشگاه شما:", InlineKeyboardMarkup(kb) if rows else back_keyboard("owner")); return

    if data.startswith("loan_return_"):
        club = get_club_by_owner(uid)
        if not club: await safe_edit(q, "باشگاه ندارید.", back_keyboard()); return
        pid = int(data.rsplit("_", 1)[1])
        with db() as c:
            row = c.execute("SELECT cp.loan_from_club_id,p.first_name,p.last_name FROM club_players cp JOIN players p ON p.id=cp.player_id WHERE cp.player_id=? AND cp.club_id=? AND cp.loan_from_club_id IS NOT NULL", (pid, club["id"])).fetchone()
            if not row:
                await safe_edit(q, "این بازیکن قرضی در باشگاه شما نیست.", back_keyboard("owner")); return
            origin = int(row["loan_from_club_id"])
            c.execute("UPDATE club_players SET club_id=?,loan_from_club_id=NULL,loan_until=NULL WHERE player_id=? AND club_id=?", (origin, pid, club["id"]))
            c.execute("UPDATE loan_records SET active=0 WHERE player_id=? AND from_club_id=? AND to_club_id=? AND active=1", (pid, origin, club["id"]))
        await safe_edit(q, f"✅ {row['first_name']} {row['last_name']} به باشگاه مبدأ بازگردانده شد.", back_keyboard("owner")); return

    if data == "market_staff":
        with db() as c:
            rows = c.execute("SELECT * FROM staff WHERE status='market' ORDER BY id LIMIT 30").fetchall()
        text = f"🧑‍💼 بازار کادر | پنجره: {'باز' if transfer_window_open() else 'بسته'}\n\n"
        kb = []
        for s in rows:
            text += f"#{s['id']} {s['first_name']} {s['last_name']} | {s['role']} | {s['style']} | {money(s['price'])}\n"
            if not is_admin(uid):
                kb.append([InlineKeyboardButton(f"استخدام #{s['id']}", callback_data=f"v15_negotiate_staff_{s['id']}")])
        if not rows: text += "عضو کادری در بازار نیست."
        kb.append([InlineKeyboardButton("↩️ برگشت", callback_data="owner" if not is_admin(uid) else "admin")])
        await safe_edit(q, text[:3900], InlineKeyboardMarkup(kb)); return
    if data.startswith("hire_staff_"):
        await safe_edit(q, "از این نسخه به بعد هیچ عضو کادری بدون مذاکره و قرارداد استخدام نمی‌شود. از بازار کادر وارد مذاکره شوید.", back_keyboard("v15_market_staff")); return
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "فقط مالک باشگاه می‌تواند استخدام کند.", back_keyboard()); return
        if not transfer_window_open():
            await safe_edit(q, "❌ پنجره نقل‌وانتقالات بسته است.", back_keyboard("market_staff")); return
        sid = int(data.rsplit("_", 1)[1])
        with db() as c:
            s = c.execute("SELECT * FROM staff WHERE id=? AND status='market'", (sid,)).fetchone()
            if not s:
                await safe_edit(q, "این عضو کادر دیگر در بازار نیست.", back_keyboard("market_staff")); return
            current = int(c.execute("SELECT budget FROM clubs WHERE id=?", (club["id"],)).fetchone()["budget"])
            cost = int(s["price"])
            if current < cost:
                await safe_edit(q, f"💰 موجودی: {money(current)}\n💸 هزینه: {money(cost)}\n❌ بودجه کافی نیست.", back_keyboard("market_staff")); return
            c.execute("UPDATE clubs SET budget=budget-? WHERE id=?", (cost, club["id"]))
            c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)",
                      (club["id"], "استخدام کادر", -cost, f"استخدام {s['first_name']} {s['last_name']} ({s['role']})", now()))
            c.execute("INSERT INTO club_staff(club_id,staff_id,hired_price,hired_at) VALUES(?,?,?,?)",
                      (club["id"], sid, s["price"], now()))
            c.execute("UPDATE staff SET status='owned' WHERE id=?", (sid,))
            msg = f"انجام شد.\n💰 موجودی جدید: {money(current-cost)}"
        await safe_edit(q, f"✅ {s['first_name']} {s['last_name']} استخدام شد.\n{msg}", back_keyboard("owner"))
        await send_channel(context, f"🧑‍💼 {club['name']}، {s['first_name']} {s['last_name']} را استخدام کرد.")
        return

    if data == "change_password":
        club = get_club_by_owner(uid)
        if not club:
            await safe_edit(q, "باشگاه ندارید.", back_keyboard()); return
        set_state(context, "owner_change_password")
        await safe_edit(q, "رمز جدید باشگاه را وارد کنید (حداقل ۴ نویسه):", back_keyboard("owner")); return


# ======================== فرم‌های متنی ========================
async def save_player_record(update, context, uid, form, photo_file_id):
    try:
        with db() as c:
            c.execute("""INSERT INTO players(first_name,last_name,position,age,height,nationality,price,contract_months,status,created_at,photo_file_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (form["first_name"], form["last_name"], form["position"], form["age"], form["height"],
                 form["nationality"], form["price"], form["contract_months"], "market", now(), photo_file_id or ""))
    except sqlite3.IntegrityError:
        set_state(context, None)
        await update.message.reply_text("❌ بازیکن تکراری است؛ ثبت نشد.", reply_markup=admin_keyboard())
        return
    except Exception as e:
        logger.exception("Player registration failed")
        await update.message.reply_text(f"❌ خطا هنگام ثبت بازیکن: {type(e).__name__}: {e}")
        return
    set_state(context, None)
    await update.message.reply_text(
        f"✅ بازیکن ثبت شد و در بازار قرار گرفت:\n{form['first_name']} {form['last_name']}\n"
        f"پست: {form['position']} | سن: {form['age']} | قد: {form['height']}\n"
        f"ملیت: {form['nationality']} | قیمت: {money(form['price'])}\nقرارداد: {form['contract_months']} ماه\n"
        f"عکس: {'ثبت شد' if photo_file_id else 'ثبت نشد'}", reply_markup=admin_keyboard())
    await send_channel(context, f"⚽ بازیکن جدید وارد بازار شد: {form['first_name']} {form['last_name']} ({form['position']})")


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user or not update.message.photo:
        return
    uid = update.effective_user.id
    state = context.user_data.get("state")
    if state != "player_photo":
        await update.message.reply_text("برای ثبت عکس بازیکن، ابتدا از پنل ادمین «ثبت بازیکن» را شروع کنید.", reply_markup=main_keyboard(uid))
        return
    if not is_admin(uid):
        set_state(context, None)
        await update.message.reply_text("فقط ادمین می‌تواند عکس بازیکن بازار را ثبت کند.", reply_markup=main_keyboard(uid))
        return
    form = context.user_data.get("form", {})
    photo_file_id = update.message.photo[-1].file_id
    await save_player_record(update, context, uid, form, photo_file_id)


def stadium_project_cost(capacity, pitch_type, roof, floodlights):
    # قیمت تقریبی بازی، نه برآورد مهندسی واقعی
    cost = int(capacity * 220000)
    if pitch_type == "چمن طبیعی": cost += 450_000_000
    elif pitch_type == "چمن هیبریدی": cost += 1_100_000_000
    else: cost += 250_000_000
    if roof: cost += int(capacity * 75_000)
    if floodlights: cost += 280_000_000
    return cost


def finish_stadium_if_due(club_id):
    with db() as c:
        project = c.execute("SELECT * FROM stadium_projects WHERE club_id=? AND status='under_construction' ORDER BY id DESC LIMIT 1", (club_id,)).fetchone()
        if not project: return None
        try: due = datetime.strptime(project['due_at'], "%Y-%m-%d %H:%M:%S")
        except Exception: return dict(project)
        if datetime.now() >= due:
            c.execute("UPDATE stadium_projects SET status='delivered',delivered_at=? WHERE id=?", (now(), project['id']))
            c.execute("INSERT OR IGNORE INTO club_settings(club_id) VALUES(?)", (club_id,))
            c.execute("UPDATE club_settings SET stadium=?,capacity=?,ticket_price=? WHERE club_id=?", (project['stadium_name'], project['capacity'], project['ticket_price'], club_id))
            project = c.execute("SELECT * FROM stadium_projects WHERE id=?", (project['id'],)).fetchone()
        return dict(project)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    uid = update.effective_user.id
    text = update.message.text.strip()
    state = context.user_data.get("state")
    form = context.user_data.setdefault("form", {})

    if not state:
        await update.message.reply_text("از دکمه‌های منو استفاده کنید.", reply_markup=main_keyboard(uid))
        return
    if text.lower() in ("/cancel", "لغو"):
        set_state(context, None)
        await update.message.reply_text("لغو شد.", reply_markup=main_keyboard(uid))
        return

    if state == "stadium_build_form":
        parts=[x.strip() for x in text.split('|')]
        if len(parts)!=7 or not parts[0]:
            await update.message.reply_text("فرمت باید ۷ بخش داشته باشد: نام | ظرفیت | قیمت بلیت | نوع چمن | سقف بله/خیر | نورافکن بله/خیر | روز ساخت"); return
        try:
            capacity=int(parts[1]); ticket=int(parts[2]); days=int(parts[6])
            if not 500<=capacity<=150000 or ticket<0 or not 1<=days<=90: raise ValueError
        except Exception:
            await update.message.reply_text("ظرفیت ۵۰۰ تا ۱۵۰۰۰۰، قیمت بلیت صفر یا بیشتر و مدت ساخت ۱ تا ۹۰ روز باشد."); return
        pitch=parts[3]
        if pitch not in ('چمن طبیعی','چمن مصنوعی','چمن هیبریدی'):
            await update.message.reply_text("نوع چمن را دقیقاً یکی از این موارد بفرستید: چمن طبیعی | چمن مصنوعی | چمن هیبریدی"); return
        yes=lambda x: x.strip().lower() in ('بله','آره','اره','yes','y','1')
        roof=yes(parts[4]); lights=yes(parts[5])
        cost=stadium_project_cost(capacity,pitch,roof,lights)
        form={'club_id':int(form['club_id']),'stadium_name':parts[0],'capacity':capacity,'ticket_price':ticket,'pitch_type':pitch,'roof':int(roof),'floodlights':int(lights),'duration_days':days,'cost':cost}
        context.user_data['pending_stadium']=form; set_state(context,None)
        await update.message.reply_text(f"📋 برآورد ساخت ورزشگاه\nنام: {parts[0]}\nظرفیت: {capacity:,} نفر\nچمن: {pitch}\nسقف: {'دارد' if roof else 'ندارد'} | نورافکن: {'دارد' if lights else 'ندارد'}\nقیمت بلیت: {money(ticket)}\nهزینه تقریبی ساخت: {money(cost)}\nمدت ساخت: {days} روز\nآیا با کسر هزینه و شروع پروژه موافقید؟",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تأیید و شروع ساخت",callback_data='stadium_build_confirm')],[InlineKeyboardButton("❌ لغو",callback_data='owner')]])); return

    if state == 'admin_suspend_details':
        if not is_admin(uid): set_state(context,None); return
        parts=[x.strip() for x in text.split('|')]
        if len(parts)!=2 or not parts[0]:
            await update.message.reply_text("قالب: علت | تعداد بازی؛ مثال: رفتار خشونت‌آمیز | 2"); return
        try: matches=int(parts[1]); assert 1<=matches<=20
        except Exception:
            await update.message.reply_text("تعداد بازی محرومیت باید بین ۱ تا ۲۰ باشد."); return
        pid=int(form['player_id']); club_id=int(form['club_id'])
        with db() as c:
            c.execute("INSERT INTO discipline_cases(club_id,player_id,case_type,reason,suspension_matches,fine_amount,status,created_at) VALUES(?,?,'suspension',?,?,0,'active',?)",(club_id,pid,parts[0],matches,now()))
            c.execute("INSERT INTO player_conditions(player_id,fitness,yellow_cards,suspended_matches,injury_until,updated_at) VALUES(?,100,0,?,'',?) ON CONFLICT(player_id) DO UPDATE SET suspended_matches=MAX(suspended_matches,excluded.suspended_matches),updated_at=excluded.updated_at",(pid,matches,now()))
        set_state(context,None)
        await update.message.reply_text(f"✅ محرومیت ثبت شد. بازیکن: {form['player_name']} | علت: {parts[0]} | محرومیت: {matches} بازی.",reply_markup=admin_keyboard())
        try: await context.bot.send_message(form['owner_id'],f"🚫 حکم انضباطی باشگاه {form['club_name']}\nبازیکن: {form['player_name']}\nعلت: {parts[0]}\nمحرومیت: {matches} بازی\nبرای اعتراض و استفاده از وکیل وارد بخش «وکیل و اعتراض» شوید.")
        except Exception: pass
        return

    if state == 'appeal_text':
        case_id=int(form['case_id']); club_id=int(form['club_id']); appeal=text.strip()
        if len(appeal)<5:
            await update.message.reply_text("لایحه اعتراض را با توضیح بیشتر بنویسید."); return
        import random
        with db() as c:
            case=c.execute("SELECT * FROM discipline_cases WHERE id=? AND club_id=? AND status='active'",(case_id,club_id)).fetchone()
            lawyer=c.execute("SELECT * FROM club_lawyers WHERE club_id=?",(club_id,)).fetchone()
            club=c.execute("SELECT budget,owner_id,name FROM clubs WHERE id=?",(club_id,)).fetchone()
            if not case or not club:
                set_state(context,None); await update.message.reply_text("پرونده دیگر فعال نیست.",reply_markup=owner_keyboard()); return
            score=(int(lawyer['skill']) if lawyer else 30)+min(20,len(appeal)//30)+random.randint(-20,25)
            if any(w in appeal.lower() for w in ('مدرک','ویدئو','اشتباه داور','اشتباه در ثبت','شاهد','گزارش')): score+=12
            if score>=72:
                result="اعتراض پذیرفته شد؛ حکم کاهش یافت."
                if case['case_type']=='suspension':
                    reduced=max(0,int(case['suspension_matches'])-1)
                    c.execute("UPDATE discipline_cases SET status='appeal_accepted',appeal_text=?,appeal_result=?,appealed_at=?,suspension_matches=? WHERE id=?",(appeal,result,now(),reduced,case_id))
                    if case['player_id']:
                        c.execute("UPDATE player_conditions SET suspended_matches=MAX(0,suspended_matches-1),updated_at=? WHERE player_id=?",(now(),case['player_id']))
                else:
                    reduction=int(case['fine_amount']*0.5)
                    c.execute("UPDATE discipline_cases SET status='appeal_accepted',appeal_text=?,appeal_result=?,appealed_at=?,fine_amount=? WHERE id=?",(appeal,result,now(),case['fine_amount']-reduction,case_id))
                    c.execute("UPDATE clubs SET budget=budget+? WHERE id=?",(reduction,club_id))
                    c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)",(club_id,'بازگشت بخشی از جریمه',reduction,f'پذیرش اعتراض پرونده #{case_id}',now()))
            else:
                result="اعتراض رد شد؛ حکم اولیه پابرجا ماند."
                c.execute("UPDATE discipline_cases SET status='appeal_rejected',appeal_text=?,appeal_result=?,appealed_at=? WHERE id=?",(appeal,result,now(),case_id))
        set_state(context,None)
        await update.message.reply_text(f"⚖️ رأی وکیل هوشمند\nپرونده: #{case_id}\nلایحه: {appeal}\nنتیجه: {result}\nامتیاز ارزیابی داخلی: {score}/100\nاین نتیجه شبیه‌سازی مدیریتی است، نه مشاوره حقوقی واقعی.",reply_markup=owner_keyboard()); return

    if state == "v15_sub_minute":
        try:
            minute=int(text)
            if not 1<=minute<=89: raise ValueError
        except Exception:
            await update.message.reply_text("دقیقه باید عددی بین ۱ تا ۸۹ باشد."); return
        club_id=int(form['club_id']); out_id=int(form['out_id']); in_id=int(form['in_id'])
        with db() as c:
            count=c.execute("SELECT COUNT(*) n FROM planned_substitutions WHERE club_id=? AND active=1",(club_id,)).fetchone()['n']
            duplicate=c.execute("SELECT 1 FROM planned_substitutions WHERE club_id=? AND active=1 AND (player_out_id=? OR player_in_id=? OR minute=?)",(club_id,out_id,in_id,minute)).fetchone()
            if count>=6:
                set_state(context,None); await update.message.reply_text("حداکثر ۶ تعویض برنامه‌ریزی می‌شود.",reply_markup=owner_keyboard()); return
            if duplicate:
                await update.message.reply_text("این بازیکن یا دقیقه قبلاً در برنامه تعویض استفاده شده؛ دقیقه دیگری انتخاب کنید."); return
            c.execute("INSERT INTO planned_substitutions(club_id,player_out_id,player_in_id,minute,active,created_at) VALUES(?,?,?,?,1,?)",(club_id,out_id,in_id,minute,now()))
            names=c.execute("SELECT id,first_name,last_name FROM players WHERE id IN (?,?)",(out_id,in_id)).fetchall()
        set_state(context,None)
        nm={r['id']:f"{r['first_name']} {r['last_name']}" for r in names}
        await update.message.reply_text(f"✅ تعویض ذخیره شد: دقیقه {minute}، {nm.get(out_id,'بازیکن')} بیرون و {nm.get(in_id,'بازیکن')} وارد. این برنامه در مسابقه بعدی اجرا می‌شود، مشروط به حضور بازیکنان و قانونی بودن تعویض.",reply_markup=owner_keyboard())
        return

    if state == "v15_renew_offer":
        parts=text.replace(',',' ').replace('٬',' ').split()
        try:
            if len(parts)<2: raise ValueError
            wage=int(parts[0]); months=int(parts[1])
            if wage<=0 or not 1<=months<=60: raise ValueError
        except Exception:
            await update.message.reply_text("قالب صحیح: دستمزد ماهانه مدت تمدید؛ مثال: 18000000 24. مدت بین ۱ تا ۶۰ ماه باشد."); return
        current=int(form['current_wage']); desired=int(current*(1.15 if wage<current*1.1 else 1.0))
        if wage < current*1.08:
            agreed_wage=desired; agreed_months=max(12,min(36,months))
            reply=f"🗣 {form['asset_name']}: پیشنهاد تمدید شما از نظر دستمزد پایین است. برای ادامه همکاری، دستمزد ماهانه {money(agreed_wage)} و تمدید {agreed_months} ماهه را می‌خواهم."
        else:
            agreed_wage=wage; agreed_months=months
            reply=f"🤝 {form['asset_name']}: با تمدید قرارداد با دستمزد {money(wage)} و مدت {months} ماه موافقم."
        context.user_data['v15_pending_renewal']={**form,'wage':agreed_wage,'months':agreed_months}
        set_state(context,None)
        await update.message.reply_text(reply,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ قبول تمدید",callback_data="v15_renew_accept")],[InlineKeyboardButton("❌ رد تمدید",callback_data="v15_renew_reject")]])); return

    # نسخه ۱۵: پیشنهاد اولیه قرارداد؛ طرف مقابل به‌صورت قاعده‌محور چانه‌زنی می‌کند.
    if state == "v15_contract_offer":
        parts=text.replace(',', ' ').replace('٬',' ').split()
        try:
            if len(parts)<2: raise ValueError
            wage=int(parts[0]); months=int(parts[1]); bonus=int(parts[2]) if len(parts)>2 else 0
            requested_clause=int(parts[3]) if len(parts)>3 else 0
            if wage<=0 or not 1<=months<=60 or bonus<0 or requested_clause<0: raise ValueError
        except Exception:
            await update.message.reply_text("فرمت: دستمزد ماهانه مدت‌ماه پاداش‌امضا بند‌فسخ؛ مثال: 12000000 24 5000000 600000000. دو مقدار آخر اختیاری‌اند و بند فسخ سخت خودکار تعیین می‌شود."); return
        base=int(form.get('base_wage',1)); age=int(form.get('age',28)); asset_name=form.get('asset_name','طرف قرارداد')
        # شخصیت قراردادی: سن بالاتر معمولاً مدت کوتاه‌تر می‌خواهد؛ ستاره گران‌قیمت دستمزد بالاتری طلب می‌کند.
        desired=max(500_000, int(base * (1.12 if age<=25 else 1.0 if age<=30 else .92)))
        desired_months=min(48,max(12,months if age<31 else min(months,24)))
        accepted=(wage>=int(desired*.88) and months>=6 and bonus>=0)
        if accepted:
            counter_wage=wage; counter_months=months; counter_bonus=bonus
            min_clause=max(int(form.get('asset_price',0))*2, wage*12, 1000000)
            counter_clause=max(requested_clause,min_clause)
            ai_text=f"🤝 {asset_name}: پیشنهاد دستمزد و مدت را می‌پذیرم. بند فسخ سخت باید حداقل {money(min_clause)} باشد؛ بند نهایی {money(counter_clause)} ثبت می‌شود."
        else:
            counter_wage=desired; counter_months=desired_months; counter_bonus=max(bonus,int(base*.25))
            min_clause=max(int(form.get('asset_price',0))*2, counter_wage*12, 1000000)
            counter_clause=max(requested_clause,min_clause)
            ai_text=f"🗣 پاسخ {asset_name}: دستمزد پیشنهادی متقابل {money(counter_wage)} ماهانه، مدت {counter_months} ماه، پاداش {money(counter_bonus)} و بند فسخ سخت {money(counter_clause)} است. بند فسخ کمتر از این مبلغ را نمی‌پذیرم."
        context.user_data['v15_pending_contract']={**form,'wage':counter_wage,'months':counter_months,'bonus':counter_bonus,'release_clause':counter_clause}
        set_state(context,None)
        await update.message.reply_text(ai_text,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ قبول پیشنهاد و ثبت قرارداد",callback_data="v15_contract_accept")],[InlineKeyboardButton("❌ رد مذاکره",callback_data="v15_contract_reject")],[InlineKeyboardButton("↩️ برگشت به قراردادها",callback_data="v15_contracts")]]))
        return

    # نسخه ۷: قیمت‌گذاری آگهی فروش بازیکن؛ بدون پرداخت هنگام ثبت آگهی
    if state == "sale_price":
        try:
            asking_price = int(text.replace(",", "").replace("٬", "").replace("تومان", "").strip())
            if asking_price <= 0: raise ValueError
        except Exception:
            await update.message.reply_text("قیمت باید عددی بیشتر از صفر باشد. مثال: 250000000"); return
        club_id = int(form.get("club_id", 0)); pid = int(form.get("player_id", 0))
        if not transfer_window_open():
            set_state(context, None)
            await update.message.reply_text("❌ پنجره نقل‌وانتقالات بسته شده است؛ آگهی ثبت نشد.", reply_markup=owner_keyboard()); return
        with db() as c:
            player = c.execute("SELECT p.* FROM players p JOIN club_players cp ON cp.player_id=p.id WHERE p.id=? AND cp.club_id=? AND cp.loan_from_club_id IS NULL", (pid, club_id)).fetchone()
            if not player:
                set_state(context, None)
                await update.message.reply_text("بازیکن دیگر در باشگاه شما نیست یا قرضی است.", reply_markup=owner_keyboard()); return
            if c.execute("SELECT 1 FROM transfer_listings WHERE player_id=? AND status='active'", (pid,)).fetchone():
                set_state(context, None)
                await update.message.reply_text("این بازیکن از قبل آگهی فروش فعال دارد.", reply_markup=owner_keyboard()); return
            c.execute("INSERT INTO transfer_listings(player_id,seller_club_id,asking_price,original_price,status,listed_at) VALUES(?,?,?,?, 'active',?)", (pid, club_id, asking_price, player["price"], now()))
            c.execute("DELETE FROM club_players WHERE player_id=? AND club_id=?", (pid, club_id))
            c.execute("UPDATE players SET status='market',price=? WHERE id=?", (asking_price, pid))
            seller_club = c.execute("SELECT name FROM clubs WHERE id=?", (club_id,)).fetchone()
            c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)", (club_id, "ثبت آگهی فروش", 0, f"آگهی {player['first_name']} {player['last_name']} با قیمت درخواستی {asking_price}؛ پرداختی انجام نشد", now()))
        set_state(context, None)
        await update.message.reply_text(f"✅ آگهی فروش ثبت شد.\nبازیکن: {player['first_name']} {player['last_name']}\nقیمت درخواستی: {money(asking_price)}\n💰 هنوز پولی دریافت نشده؛ اگر باشگاه دیگری بخرد، مبلغ از خریدار کسر و به باشگاه شما واریز می‌شود.", reply_markup=owner_keyboard())
        await send_channel(context, f"🏷 بازیکن {player['first_name']} {player['last_name']} از {seller_club['name']} در بازار قرار گرفت؛ قیمت {money(asking_price)}.")
        return

    # درخواست باشگاه: نام، شهر، کشور
    if state == "club_name":
        form["club_name"] = text
        set_state(context, "club_city", form)
        await update.message.reply_text("شهر باشگاه را وارد کنید:")
    elif state == "club_city":
        form["city"] = text
        set_state(context, "club_country", form)
        await update.message.reply_text("کشور باشگاه را وارد کنید:")
    elif state == "club_country":
        form["country"] = text
        with db() as c:
            try:
                c.execute("""INSERT INTO club_requests(owner_id,club_name,city,country,status,created_at)
                    VALUES(?,?,?,?,?,?)""",
                    (uid, form["club_name"], form["city"], form["country"], "pending", now()))
            except sqlite3.IntegrityError:
                c.execute("""UPDATE club_requests SET club_name=?,city=?,country=?,status='pending',created_at=?
                    WHERE owner_id=?""", (form["club_name"], form["city"], form["country"], now(), uid))
        set_state(context, None)
        await update.message.reply_text(
            f"✅ درخواست ثبت شد.\n🏟 {form['club_name']}\n📍 {form['city']}، {form['country']}\nمنتظر بررسی ادمین باشید.",
            reply_markup=main_keyboard(uid))
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(aid, f"📝 درخواست باشگاه جدید\nنام: {form['club_name']}\nشهر/کشور: {form['city']}، {form['country']}\nمالک: {uid}")
            except Exception:
                pass

    elif state == "user_message":
        kind = form.get("kind", "letter")
        club = get_club_by_owner(uid)
        with db() as c:
            c.execute("INSERT INTO messages(user_id,club_id,kind,body,status,created_at) VALUES(?,?,?,?,?,?)",
                      (uid, club["id"] if club else None, kind, text, "new", now()))
        set_state(context, None)
        await update.message.reply_text("✅ پیام شما برای ادمین ثبت شد.", reply_markup=main_keyboard(uid))
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(aid, f"📨 پیام جدید\nنوع: {kind}\nکاربر: {uid}\n\n{text}")
            except Exception:
                pass

    elif state == "redeem_gift":
        code = text.upper()
        club = get_club_by_owner(uid)
        if not club:
            set_state(context, None)
            await update.message.reply_text("برای دریافت مبلغ کد هدیه، ابتدا باید باشگاه تأییدشده داشته باشید.", reply_markup=main_keyboard(uid))
            return
        with db() as c:
            gift = c.execute("SELECT * FROM gift_codes WHERE code=? COLLATE NOCASE AND active=1", (code,)).fetchone()
            already = c.execute("SELECT 1 FROM gift_redemptions WHERE code=? AND user_id=?", (code, uid)).fetchone()
            if not gift:
                answer = "❌ کد نامعتبر یا غیرفعال است."
            elif already:
                answer = "❌ شما قبلاً از این کد استفاده کرده‌اید."
            elif gift["uses"] >= gift["max_uses"]:
                answer = "❌ ظرفیت استفاده از این کد تمام شده است."
            else:
                c.execute("INSERT INTO gift_redemptions(code,user_id,redeemed_at) VALUES(?,?,?)", (code, uid, now()))
                c.execute("UPDATE gift_codes SET uses=uses+1 WHERE code=?", (code,))
                amount = int(gift["amount"])
                c.execute("UPDATE clubs SET budget=budget+? WHERE id=?", (amount, club["id"]))
                c.execute("INSERT INTO transactions(club_id,kind,amount,description,created_at) VALUES(?,?,?,?,?)",
                          (club["id"], "کد هدیه", amount, f"استفاده از کد هدیه {code}", now()))
                answer = f"🎁 کد پذیرفته شد.\nمبلغ: {money(amount)}\n💰 موجودی جدید: {money(int(club['budget']) + amount)}"
        set_state(context, None)
        await update.message.reply_text(answer, reply_markup=main_keyboard(uid))

    elif state == "admin_password":
        if not is_admin(uid):
            set_state(context, None); return
        try:
            owner_id = int(text)
        except ValueError:
            await update.message.reply_text("شناسه باید عددی باشد. دوباره بفرستید:"); return
        club = get_club_by_owner(owner_id)
        if not club:
            await update.message.reply_text("برای این مالک باشگاه پیدا نشد. شناسه دیگری بفرستید:"); return
        password = secrets.token_urlsafe(7)
        with db() as c:
            c.execute("UPDATE clubs SET password_hash=? WHERE id=?", (password, club["id"]))
        set_state(context, None)
        await update.message.reply_text(f"رمز جدید باشگاه {club['name']}:\n{password}", reply_markup=admin_keyboard())
        try:
            await context.bot.send_message(owner_id, f"🔑 رمز باشگاه شما توسط ادمین تغییر کرد:\n{password}")
        except Exception:
            pass

    elif state in ("admin_fine", "admin_budget"):
        if not is_admin(uid):
            set_state(context, None); return
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("دو عدد با فاصله بفرستید؛ مثال: 2 5000000"); return
        try:
            club_id, amount = int(parts[0]), int(parts[1])
        except ValueError:
            await update.message.reply_text("هر دو مقدار باید عدد باشند."); return
        club = get_club(club_id)
        if not club:
            await update.message.reply_text("شناسه باشگاه درست نیست؛ دوباره بفرستید:"); return
        if state == "admin_fine":
            if amount <= 0:
                await update.message.reply_text("مبلغ جریمه باید مثبت باشد."); return
            ok, answer = change_budget(club_id, -amount, "جریمه ادمین", "جریمه ثبت‌شده توسط ادمین")
            if ok:
                with db() as c:
                    c.execute("INSERT INTO discipline_cases(club_id,player_id,case_type,reason,suspension_matches,fine_amount,status,created_at) VALUES(?,NULL,'fine','جریمه مالی ثبت‌شده توسط ادمین',0,?,'active',?)",(club_id,amount,now()))
                answer = f"جریمه {money(amount)} اعمال شد.\nبرای اعتراض، باشگاه می‌تواند از وکیل هوشمند استفاده کند.\n{answer}"
        else:
            ok, answer = change_budget(club_id, amount, "تغییر بودجه ادمین", "تغییر بودجه توسط ادمین")
            if ok:
                answer = f"بودجه به میزان {money(amount)} تغییر کرد.\n{answer}"
        set_state(context, None)
        await update.message.reply_text(answer, reply_markup=admin_keyboard())
        try:
            await context.bot.send_message(club["owner_id"], f"📢 تغییر مالی باشگاه:\n{answer}")
        except Exception:
            pass

    elif state == "admin_delete_club":
        if not is_admin(uid):
            set_state(context, None); return
        try: club_id = int(text)
        except ValueError:
            await update.message.reply_text("شناسه باشگاه باید عدد باشد."); return
        club = get_club(club_id)
        if not club:
            await update.message.reply_text("باشگاه پیدا نشد. شناسه دیگری بفرستید:"); return
        with db() as c:
            c.execute("DELETE FROM clubs WHERE id=?", (club_id,))
            c.execute("UPDATE club_requests SET status='rejected' WHERE owner_id=?", (club["owner_id"],))
        set_state(context, None)
        await update.message.reply_text(f"🗑 باشگاه {club['name']} حذف شد.", reply_markup=admin_keyboard())
        await send_channel(context, f"🗑 باشگاه {club['name']} توسط مدیریت حذف شد.")

    elif state == "player_first":
        form["first_name"] = text; set_state(context, "player_last", form)
        await update.message.reply_text("نام خانوادگی بازیکن:")
    elif state == "player_last":
        form["last_name"] = text; set_state(context, "player_position", form)
        await update.message.reply_text("پست بازیکن (مثلاً دروازه‌بان، دفاع، هافبک، مهاجم):")
    elif state == "player_position":
        form["position"] = text; set_state(context, "player_age", form)
        await update.message.reply_text("سن بازیکن (عدد):")
    elif state == "player_age":
        try: form["age"] = int(text); assert 15 <= form["age"] <= 50
        except Exception:
            await update.message.reply_text("سن باید عددی بین ۱۵ تا ۵۰ باشد."); return
        set_state(context, "player_height", form)
        await update.message.reply_text("قد بازیکن به سانتی‌متر (عدد):")
    elif state == "player_height":
        try: form["height"] = int(text); assert 130 <= form["height"] <= 230
        except Exception:
            await update.message.reply_text("قد باید عددی بین ۱۳۰ تا ۲۳۰ باشد."); return
        set_state(context, "player_nationality", form)
        await update.message.reply_text("ملیت بازیکن:")
    elif state == "player_nationality":
        form["nationality"] = text; set_state(context, "player_price", form)
        await update.message.reply_text("قیمت بازیکن به تومان (عدد):")
    elif state == "player_price":
        try: form["price"] = int(text); assert form["price"] > 0
        except Exception:
            await update.message.reply_text("قیمت باید عددی بیشتر از صفر باشد."); return
        set_state(context, "player_contract", form)
        await update.message.reply_text("مدت قرارداد به ماه (عدد):")
    elif state == "player_contract":
        try: form["contract_months"] = int(text); assert 1 <= form["contract_months"] <= 120
        except Exception:
            await update.message.reply_text("مدت قرارداد باید بین ۱ تا ۱۲۰ ماه باشد."); return
        set_state(context, "player_photo", form)
        await update.message.reply_text("📸 حالا عکس واضح بازیکن را به‌صورت عکس تلگرام ارسال کنید تا در بازار کنار مشخصات نمایش داده شود. اگر عکس ندارید، «بدون عکس» بنویسید.")

    elif state == "player_photo":
        if text.strip().lower() not in ("بدون عکس", "رد", "skip", "no photo"):
            await update.message.reply_text("لطفاً عکس بازیکن را ارسال کنید یا «بدون عکس» بنویسید."); return
        await save_player_record(update, context, uid, form, "")
        return

    elif state == "lineup_starters":
        club_id = form.get("club_id")
        try:
            ids = [int(x.strip()) for x in text.split(",") if x.strip()]
            if len(ids) != 11 or len(set(ids)) != 11: raise ValueError
        except Exception:
            await update.message.reply_text("باید دقیقاً ۱۱ شناسه عددیِ متفاوت با کاما بفرستید. مثال: 1,2,3,4,5,6,7,8,9,10,11"); return
        with db() as c:
            owned = {r['id'] for r in c.execute("SELECT p.id FROM players p JOIN club_players cp ON cp.player_id=p.id WHERE cp.club_id=?", (club_id,)).fetchall()}
        if not set(ids).issubset(owned):
            await update.message.reply_text("حداقل یکی از شناسه‌ها متعلق به بازیکنان باشگاه شما نیست. دوباره بفرستید."); return
        form['starters'] = ','.join(map(str, ids))
        set_state(context, "lineup_bench", form)
        await update.message.reply_text("شناسه بازیکنان نیمکت را با کاما بفرستید (حداکثر ۱۱ نفر). اگر نیمکت ندارید، عدد ۰ بفرستید:")
    elif state == "lineup_bench":
        club_id = form.get('club_id')
        try:
            ids = [] if text.strip() == '0' else [int(x.strip()) for x in text.split(',') if x.strip()]
            if len(ids) > 11 or len(set(ids)) != len(ids): raise ValueError
        except Exception:
            await update.message.reply_text("حداکثر ۱۱ شناسه متفاوت با کاما وارد کنید؛ برای خالی گذاشتن ۰ بفرستید."); return
        starters = [int(x) for x in form['starters'].split(',')]
        if set(ids) & set(starters):
            await update.message.reply_text("بازیکن نمی‌تواند هم در ترکیب اصلی و هم نیمکت باشد."); return
        with db() as c:
            owned = {r['id'] for r in c.execute("SELECT p.id FROM players p JOIN club_players cp ON cp.player_id=p.id WHERE cp.club_id=?", (club_id,)).fetchall()}
            if not set(ids).issubset(owned):
                await update.message.reply_text("حداقل یکی از شناسه‌های نیمکت متعلق به باشگاه شما نیست."); return
        form['bench'] = ','.join(map(str,ids))
        set_state(context, "lineup_captain", form)
        await update.message.reply_text("شناسه یکی از ۱۱ بازیکن اصلی را به‌عنوان کاپیتان بفرستید:")
    elif state == "lineup_captain":
        try: captain_id = int(text)
        except ValueError:
            await update.message.reply_text("شناسه کاپیتان باید عددی باشد."); return
        starters = [int(x) for x in form['starters'].split(',')]
        if captain_id not in starters:
            await update.message.reply_text("کاپیتان باید یکی از ۱۱ بازیکن اصلی باشد. شناسه درست را بفرستید:"); return
        with db() as c:
            c.execute("INSERT INTO club_lineups(club_id,starters,bench,saved_at) VALUES(?,?,?,?) ON CONFLICT(club_id) DO UPDATE SET starters=excluded.starters,bench=excluded.bench,saved_at=excluded.saved_at", (form['club_id'], form['starters'], form.get('bench',''), now()))
            c.execute("INSERT OR IGNORE INTO club_settings(club_id) VALUES(?)", (form['club_id'],))
            c.execute("UPDATE club_settings SET captain_id=? WHERE club_id=?", (captain_id, form['club_id']))
        set_state(context, None)
        await update.message.reply_text(f"✅ ترکیب اصلی، نیمکت و کاپیتان (شناسه {captain_id}) ذخیره شد. حالا می‌توانید بازی دوستانه برگزار کنید.", reply_markup=owner_keyboard())
    elif state == "v3_tactics":
        parts = text.split(maxsplit=1)
        if len(parts) != 2 or parts[0] not in ("4-4-2", "4-3-3", "4-2-3-1", "4-1-4-1", "4-3-2-1", "4-2-2-2", "4-3-1-2", "4-1-2-1-2", "4-5-1", "4-4-1-1", "3-5-2", "3-4-3", "3-4-2-1", "3-4-1-2", "3-1-4-2", "3-2-4-1", "5-3-2", "5-4-1", "5-2-3", "5-2-1-2"):
            await update.message.reply_text("فرمت درست مثل 4-3-3 هجومی است. آرایش‌های مجاز: 4-4-2، 4-3-3، 4-2-3-1، 4-1-4-1، 4-3-2-1، 4-2-2-2، 4-3-1-2، 4-1-2-1-2، 4-5-1، 4-4-1-1، 3-5-2، 3-4-3، 3-4-2-1، 3-4-1-2، 3-1-4-2، 3-2-4-1، 5-3-2، 5-4-1، 5-2-3، 5-2-1-2"); return
        with db() as c:
            c.execute("INSERT OR IGNORE INTO club_settings(club_id) VALUES(?)", (form['club_id'],))
            c.execute("UPDATE club_settings SET formation=?,tactics=? WHERE club_id=?", (parts[0],parts[1],form['club_id']))
        set_state(context, None)
        await update.message.reply_text(f"✅ آرایش {parts[0]} و تاکتیک {parts[1]} ذخیره شد.", reply_markup=owner_keyboard())
    elif state == "v3_stadium":
        parts = [x.strip() for x in text.split('|')]
        if len(parts) not in (2,3) or not parts[0]:
            await update.message.reply_text("نام ورزشگاه | قیمت بلیت | ظرفیت را وارد کنید. مثال: آزادی | 250000 | 45000 (ظرفیت اختیاری است)"); return
        try:
            ticket = int(parts[1]); capacity = int(parts[2]) if len(parts)==3 else 30000
            if ticket < 0 or not 500 <= capacity <= 150000: raise ValueError
        except ValueError:
            await update.message.reply_text("قیمت بلیت باید صفر یا بیشتر و ظرفیت بین ۵۰۰ تا ۱۵۰۰۰۰ نفر باشد."); return
        with db() as c:
            c.execute("INSERT OR IGNORE INTO club_settings(club_id) VALUES(?)", (form['club_id'],))
            c.execute("UPDATE club_settings SET stadium=?,ticket_price=?,capacity=? WHERE club_id=?", (parts[0],ticket,capacity,form['club_id']))
        set_state(context, None)
        await update.message.reply_text(f"✅ ورزشگاه «{parts[0]}»، قیمت بلیت {money(ticket)} و ظرفیت {capacity:,} نفر ذخیره شد.", reply_markup=owner_keyboard())

    elif state == "staff_first":
        form["first_name"] = text; set_state(context, "staff_last", form)
        await update.message.reply_text("نام خانوادگی:")
    elif state == "staff_last":
        form["last_name"] = text; set_state(context, "staff_age", form)
        await update.message.reply_text("سن (عدد):")
    elif state == "staff_age":
        try: form["age"] = int(text); assert 18 <= form["age"] <= 100
        except Exception:
            await update.message.reply_text("سن باید عددی بین ۱۸ تا ۱۰۰ باشد."); return
        set_state(context, "staff_role", form)
        await update.message.reply_text("سمت کادر (سرمربی، دستیار، بدنساز، پزشک، مربی دروازه‌بان و ...):")
    elif state == "staff_role":
        form["role"] = text; set_state(context, "staff_style", form)
        await update.message.reply_text("سبک/تخصص (مثلاً هجومی، دفاعی، بدنسازی، پزشکی):")
    elif state == "staff_style":
        form["style"] = text; set_state(context, "staff_price", form)
        await update.message.reply_text("قیمت استخدام/قرارداد به تومان (عدد):")
    elif state == "staff_price":
        try: form["price"] = int(text); assert form["price"] > 0
        except Exception:
            await update.message.reply_text("قیمت باید عددی بیشتر از صفر باشد."); return
        try:
            with db() as c:
                c.execute("""INSERT INTO staff(first_name,last_name,age,role,style,price,status,created_at)
                    VALUES(?,?,?,?,?,?,?,?)""",
                    (form["first_name"], form["last_name"], form["age"], form["role"], form["style"],
                     form["price"], "market", now()))
        except sqlite3.IntegrityError:
            set_state(context, None)
            await update.message.reply_text("❌ این عضو کادر تکراری است.", reply_markup=admin_keyboard())
            return
        set_state(context, None)
        await update.message.reply_text(
            f"✅ عضو کادر ثبت شد:\n{form['first_name']} {form['last_name']}\n"
            f"سن: {form['age']} | سمت: {form['role']} | تخصص: {form['style']}\nقیمت: {money(form['price'])}",
            reply_markup=admin_keyboard())
        await send_channel(context, f"🧑‍💼 عضو جدید کادر وارد بازار شد: {form['first_name']} {form['last_name']} ({form['role']})")

    elif state == "admin_gift_amount":
        try: form["amount"] = int(text); assert form["amount"] > 0
        except Exception:
            await update.message.reply_text("مبلغ باید عددی بیشتر از صفر باشد."); return
        set_state(context, "admin_gift_uses", form)
        await update.message.reply_text("حداکثر تعداد استفاده از کد را وارد کنید (عدد):")
    elif state == "admin_gift_uses":
        try: form["uses"] = int(text); assert 1 <= form["uses"] <= 100000
        except Exception:
            await update.message.reply_text("تعداد استفاده باید حداقل ۱ باشد."); return
        code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(10))
        with db() as c:
            c.execute("INSERT INTO gift_codes(code,amount,max_uses,uses,active,created_at) VALUES(?,?,?,?,?,?)",
                      (code, form["amount"], form["uses"], 0, 1, now()))
        set_state(context, None)
        await update.message.reply_text(f"🎁 کد هدیه ساخته شد:\nکد: {code}\nمبلغ هر استفاده: {money(form['amount'])}\nحداکثر استفاده: {form['uses']}", reply_markup=admin_keyboard())

    elif state == "admin_broadcast":
        if not is_admin(uid):
            set_state(context, None); return
        if not text.strip():
            await update.message.reply_text("متن پیام خالی است؛ دوباره بفرستید."); return
        context.user_data["pending_broadcast"] = text.strip()
        set_state(context, "admin_broadcast_confirm")
        await update.message.reply_text(
            f"📢 پیش‌نمایش پیام همگانی\n\n{text.strip()[:3500]}\n\nاین پیام برای تمام کاربرانی که ربات را قبلاً باز کرده‌اند ارسال شود؟",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تأیید و ارسال", callback_data="broadcast_send")], [InlineKeyboardButton("❌ لغو", callback_data="broadcast_cancel")]])
        )

    elif state == "admin_announce":
        if not is_admin(uid):
            set_state(context, None); return
        await send_channel(context, "📣 اطلاعیه مدیریت\n\n" + text)
        set_state(context, None)
        await update.message.reply_text("درخواست ارسال اطلاعیه انجام شد. اگر کانال تنظیم شده و ربات ادمین باشد، پیام ارسال می‌شود.", reply_markup=admin_keyboard())

    elif state == "owner_change_password":
        club = get_club_by_owner(uid)
        if not club:
            set_state(context, None)
            await update.message.reply_text("باشگاه پیدا نشد.", reply_markup=main_keyboard(uid)); return
        if len(text) < 4:
            await update.message.reply_text("رمز باید حداقل ۴ نویسه باشد."); return
        with db() as c:
            c.execute("UPDATE clubs SET password_hash=? WHERE id=?", (text, club["id"]))
        set_state(context, None)
        await update.message.reply_text("🔑 رمز باشگاه تغییر کرد.", reply_markup=owner_keyboard())

    else:
        set_state(context, None)
        await update.message.reply_text("مرحله نامعتبر بود؛ از منوی اصلی شروع کنید.", reply_markup=main_keyboard(uid))


async def stadium_delivery_watcher(application: Application):
    """تحویل خودکار ورزشگاه‌ها پس از رسیدن موعد ساخت."""
    import asyncio
    while True:
        try:
            due_projects=[]
            with db() as c:
                due_projects=[dict(r) for r in c.execute("SELECT sp.*,cl.name club_name,cl.owner_id FROM stadium_projects sp JOIN clubs cl ON cl.id=sp.club_id WHERE sp.status='under_construction' AND sp.due_at<=?",(now(),)).fetchall()]
                for project in due_projects:
                    c.execute("UPDATE stadium_projects SET status='delivered',delivered_at=? WHERE id=? AND status='under_construction'",(now(),project['id']))
                    c.execute("INSERT OR IGNORE INTO club_settings(club_id) VALUES(?)",(project['club_id'],))
                    c.execute("UPDATE club_settings SET stadium=?,capacity=?,ticket_price=? WHERE club_id=?",(project['stadium_name'],project['capacity'],project['ticket_price'],project['club_id']))
            for project in due_projects:
                try:
                    await application.bot.send_message(chat_id=project['owner_id'],text=f"🎉 ورزشگاه جدید باشگاه {project['club_name']} تحویل داده شد!\nنام: {project['stadium_name']}\nظرفیت: {project['capacity']:,} نفر\nنوع چمن: {project['pitch_type']}\nقیمت بلیت: {money(project['ticket_price'])}\nاکنون ورزشگاه در تنظیمات باشگاه فعال است.",reply_markup=owner_keyboard())
                except Exception as exc:
                    logger.info("Stadium delivery notification failed: %s",exc)
        except Exception as exc:
            logger.exception("Stadium delivery watcher error: %s",exc)
        await asyncio.sleep(60)


async def post_init(application: Application):
    init_db()
    application.create_task(stadium_delivery_watcher(application))
    logger.info("Database initialized; stadium delivery watcher started.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled bot error", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("❌ خطای داخلی رخ داد. ادمین لاگ خطا را بررسی کند؛ اطلاعات فرم شما را دوباره از ابتدا وارد نکنید.")
    except Exception:
        pass


def main():
    if not BOT_TOKEN or "توکن_جدید_را_اینجا_قرار_بده" in BOT_TOKEN or "توکن_ربات_را_اینجا_قرار_بده" in BOT_TOKEN or ":" not in BOT_TOKEN:
        print("خطا: ابتدا BOT_TOKEN را در ابتدای فایل وارد کنید.")
        return
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CallbackQueryHandler(buttons))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_error_handler(error_handler)
    print("ربات در حال اجراست...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
