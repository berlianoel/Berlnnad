import logging
import time
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
import os

# Aktifkan logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Token bot Telegram dari environment variable
BOT_TOKEN = "7218211927:AAH-X_k_71BNI0eJbAcMjYCcSEsRhsl5z94"

# Data global untuk permainan
game_data = {
    "group_id": None,
    "players": [],
    "roles": {},
    "phase": "idle",
    "votes": {},
    "night_actions": {},
    "alive_players": [],
    "winners": None,
    "night_results": [],
    "vote_time": 60,  # Waktu voting dalam detik
    "night_time": 45,  # Waktu malam dalam detik
    "max_players": 15,  # Maksimum pemain default
    "current_day": 1,  # Hari permainan
    "admins": set(),  # Admin grup
    "bot_admin": 5136750253,  # ID admin bot
    "role_percentages": {
        "Mafia": 25,
        "Dokter": 10,
        "Detektif": 10,
        "Pelacur": 10,
        "Pembunuh": 10,
        "Pengintai": 10,
        "Bodyguard": 10,
        "Warga": 15
    }
}

def get_mafia_count(num_players):
    if num_players > 22:
        return 7
    elif num_players > 15:
        return 5
    elif num_players >= 15:
        return 4
    else:
        return 3

def generate_role_distribution(num_players):
    mafia_count = get_mafia_count(num_players)
    roles = ["Boss Mafia"]
    roles.extend(["Mafia"] * (mafia_count - 1))

    support_roles = ["Dokter", "Detektif", "Pelacur", "Pembunuh", "Pengintai", "Bodyguard"]
    remaining = num_players - mafia_count

    roles.extend(support_roles[:min(len(support_roles), remaining)])
    roles.extend(["Warga"] * (remaining - len(support_roles)))
    return roles
PHASES = ["idle", "playing", "night", "day"]

# Add room state
room_state = {
    "message_id": None,
    "join_timer": None,
    "players": []
}

async def update_player_list(context: ContextTypes.DEFAULT_TYPE):
    if not room_state["message_id"] or not game_data["group_id"]:
        return

    player_list = "\n".join([f"👤 @{p['name']}" for p in room_state["players"]])
    keyboard = [
        [InlineKeyboardButton("✅ Join Room", callback_data="room_join")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.edit_message_text(
            chat_id=game_data["group_id"],
            message_id=room_state["message_id"],
            text=f"🎮 Room MafiosoNnad\n\nPemain yang sudah bergabung ({len(room_state['players'])}):\n{player_list}",
            reply_markup=reply_markup
        )
    except:
        pass

async def check_join_timer(context: ContextTypes.DEFAULT_TYPE):
    if not game_data["group_id"]:
        return

    not_joined = []
    for member in await context.bot.get_chat_administrators(game_data["group_id"]):
        user = member.user
        if not any(p["id"] == user.id for p in room_state["players"]) and not user.is_bot:
            not_joined.append(user.name)

    if not_joined:
        mentions = " ".join([f"@{name}" for name in not_joined])
        await context.bot.send_message(
            chat_id=game_data["group_id"],
            text=f"⏰ 30 detik tersisa!\nPemain yang belum bergabung:\n{mentions}\nSegera bergabung ke room!"
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎮 Buat Room", callback_data="cmd_createroom")],
        [InlineKeyboardButton("❓ Bantuan", callback_data="cmd_help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎮 Selamat datang di MafiosoNnad! 🎮\n\n"
        "Silakan pilih menu di bawah ini:",
        reply_markup=reply_markup
    )

async def auto_start_game(context: ContextTypes.DEFAULT_TYPE):
    # Transfer players from room to game
    game_data["players"] = room_state["players"].copy()
    game_data["alive_players"] = room_state["players"].copy()

    if len(game_data["players"]) >= 4:
        await context.bot.send_message(
            chat_id=game_data["group_id"],
            text="⏰ Waktu join telah habis! Memulai permainan..."
        )
        await startgame(None, context)
    else:
        await context.bot.send_message(
            chat_id=game_data["group_id"],
            text="❌ Permainan dibatalkan karena pemain kurang dari 4 orang."
        )
        room_state["players"] = []

async def create_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.callback_query.message.chat.type not in ["group", "supergroup"]:
        await query.edit_message_text("Gunakan command ini di dalam grup!")
        return

    # Auto set group
    game_data["group_id"] = update.callback_query.message.chat.id
    game_data["phase"] = "idle"

    # Reset room state
    room_state["players"] = []
    keyboard = [[InlineKeyboardButton("✅ Join Room", callback_data="room_join")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await context.bot.send_message(
        chat_id=game_data["group_id"],
        text="🎮 Room MafiosoNnad\n\nPemain yang sudah bergabung (0):\n\n⏰ Game akan dimulai dalam 1 menit!",
        reply_markup=reply_markup
    )
    room_state["message_id"] = msg.message_id

    # Set join timer for 30s reminder
    if room_state["join_timer"]:
        room_state["join_timer"].schedule_removal()
    room_state["join_timer"] = context.job_queue.run_once(check_join_timer, 30)

    # Set auto-start timer for 60s
    context.job_queue.run_once(auto_start_game, 60)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "📖 Panduan Permainan True Mafia 📖\n\n"
            "Perintah Umum:\n"
            "/start - Mulai bot\n"
            "/help - Tampilkan bantuan\n"
            "/setgroup - Set grup untuk bermain\n"
            "/join - Bergabung ke permainan\n"
            "/startgame - Mulai permainan\n"
            "/hari - Cek hari permainan\n\n"
            "Perintah Admin:\n"
            "/setmaxplayers - Set maksimum pemain\n"
            "/setadmin - Tambah admin baru\n"
            "/setrole - Atur persentase role\n\n"
            "Info Role:\n"
            "🔪 Mafia - Membunuh warga setiap malam\n"
            "👨‍⚕️ Dokter - Menyelamatkan pemain\n"
            "🕵️ Detektif - Menyelidiki peran pemain\n"
            "💃 Pelacur - Menghalangi aksi malam\n"
            "🔫 Pembunuh - Membunuh satu target\n"
            "👀 Pengintai - Mengintai aktivitas pemain\n"
            "🛡️ Bodyguard - Melindungi pemain\n"
            "👥 Warga - Membantu menangkap mafia"
        )
    else:
        await update.message.reply_text(
            "📖 Panduan Permainan True Mafia 📖\n\n"
            "Perintah Umum:\n"
            "/start - Mulai bot\n"
            "/help - Tampilkan bantuan\n"
            "/setgroup - Set grup untuk bermain\n"
            "/join - Bergabung ke permainan\n"
            "/startgame - Mulai permainan\n"
            "/hari - Cek hari permainan\n\n"
            "Perintah Admin:\n"
            "/setmaxplayers - Set maksimum pemain\n"
            "/setadmin - Tambah admin baru\n"
            "/setrole - Atur persentase role\n\n"
            "Info Role:\n"
            "🔪 Mafia - Membunuh warga setiap malam\n"
            "👨‍⚕️ Dokter - Menyelamatkan pemain\n"
            "🕵️ Detektif - Menyelidiki peran pemain\n"
            "💃 Pelacur - Menghalangi aksi malam\n"
            "🔫 Pembunuh - Membunuh satu target\n"
            "👀 Pengintai - Mengintai aktivitas pemain\n"
            "🛡️ Bodyguard - Melindungi pemain\n"
            "👥 Warga - Membantu menangkap mafia"
        )

async def setgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Perintah ini hanya dapat digunakan di grup!")
        return
    game_data["group_id"] = update.message.chat_id
    game_data["phase"] = "idle"
    await update.message.reply_text("✅ Grup telah diset sebagai lokasi permainan!")

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if game_data["phase"] != "idle":
        await update.message.reply_text("❌ Permainan sudah dimulai!")
        return

    if len(game_data["players"]) >= game_data["max_players"]:
        await update.message.reply_text(f"❌ Pemain sudah penuh! (max: {game_data['max_players']})")
        return

    player = {
        "id": update.message.from_user.id,
        "name": update.message.from_user.first_name,
    }
    if not any(p["id"] == player["id"] for p in game_data["players"]):
        game_data["players"].append(player)
        game_data["alive_players"].append(player)
        await update.message.reply_text(f"{player['name']} telah bergabung! ({len(game_data['players'])}/{game_data['max_players']} pemain)")
    else:
        await update.message.reply_text("Kamu sudah terdaftar dalam permainan.")

async def room_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    player = {
        "id": query.from_user.id,
        "name": query.from_user.first_name,
    }
    
    if not any(p["id"] == player["id"] for p in room_state["players"]):
        room_state["players"].append(player)
        await update.callback_query.answer("✅ Berhasil bergabung!")
        await update_player_list(context)
    else:
        await update.callback_query.answer("⚠️ Kamu sudah bergabung!")

async def perform_role_action(player_id: int, target_id: int, context: ContextTypes.DEFAULT_TYPE):
    role = game_data["roles"][player_id]
    player_name = next((p["name"] for p in game_data["players"] if p["id"] == player_id), "Unknown")
    target_name = next((p["name"] for p in game_data["players"] if p["id"] == target_id), "Unknown")

    if role == "Dokter":
        await context.bot.send_message(
            chat_id=player_id,
            text=f"✅ Kamu telah menyembuhkan @{target_name}"
        )
    elif role == "Detektif":
        target_role = game_data["roles"][target_id]
        await context.bot.send_message(
            chat_id=player_id,
            text=f"🔍 Hasil investigasi: @{target_name} adalah seorang {target_role}"
        )
    elif role == "Mafia":
        await context.bot.send_message(
            chat_id=player_id,
            text=f"🔪 Kamu telah memilih untuk membunuh @{target_name}"
        )
    elif role == "Pelacur":
        await context.bot.send_message(
            chat_id=player_id,
            text=f"💃 Kamu telah menghalangi aksi @{target_name} malam ini"
        )
    elif role == "Bodyguard":
        await context.bot.send_message(
            chat_id=player_id,
            text=f"🛡️ Kamu telah melindungi @{target_name}"
        )

def check_win_condition():
    mafia_count = sum(1 for p in game_data["alive_players"] if game_data["roles"][p["id"]] in ["Boss Mafia", "Mafia"])
    civilian_count = len(game_data["alive_players"]) - mafia_count

    if mafia_count == 0:
        return "Warga"
    elif mafia_count >= civilian_count:
        return "Mafia"
    return None

def eliminate_player(player_id, reason):
    game_data["alive_players"] = [p for p in game_data["alive_players"] if p["id"] != player_id]
    player_name = next((p["name"] for p in game_data["players"] if p["id"] == player_id), "Unknown")
    return f"{player_name} telah {reason}!"

async def show_alive_players(context: ContextTypes.DEFAULT_TYPE):
    alive_players = [p["name"] for p in game_data["alive_players"]]
    dead_players = [p["name"] for p in game_data["players"] if p not in game_data["alive_players"]]

    status_msg = "👥 Pemain yang masih hidup:\n"
    for i, player in enumerate(alive_players, 1):
        status_msg += f"{i}. @{player}\n"

    status_msg += "\n💀 Pemain yang sudah mati:\n"
    for i, player in enumerate(dead_players, 1):
        status_msg += f"{i}. @{player}\n"

    await context.bot.send_message(
        chat_id=game_data["group_id"],
        text=status_msg
    )

async def process_night_actions():
    mafia_targets = {}
    doctor_target = None
    detective_target = None
    hooker_target = None
    bodyguard_target = None
    killer_target = None
    
    # Collect all actions
    for player_id, action in game_data["night_actions"].items():
        role = game_data["roles"][player_id]
        if role in ["Boss Mafia", "Mafia"]:
            if action not in mafia_targets:
                mafia_targets[action] = 0
            mafia_targets[action] += 1
        elif role == "Dokter":
            doctor_target = action
        elif role == "Detektif":
            detective_target = action
        elif role == "Pelacur":
            hooker_target = action
        elif role == "Bodyguard":
            bodyguard_target = action
        elif role == "Pembunuh":
            killer_target = action

    results = []
    
    # Find mafia target with most votes
    mafia_target = None
    if mafia_targets:
        max_votes = max(mafia_targets.values())
        potential_targets = [t for t, v in mafia_targets.items() if v == max_votes]
        if potential_targets:
            mafia_target = random.choice(potential_targets)
    
    # Process mafia kill
    if mafia_target and mafia_target != doctor_target and mafia_target != hooker_target and mafia_target != bodyguard_target:
        results.append(eliminate_player(mafia_target, "dibunuh oleh Mafia"))
    
    # Process killer action
    if killer_target and killer_target != doctor_target and killer_target != hooker_target and killer_target != bodyguard_target:
        results.append(eliminate_player(killer_target, "dibunuh oleh Pembunuh"))
        
    # Process detective result
    if detective_target and detective_target != hooker_target:
        detective_id = next((p_id for p_id, action in game_data["night_actions"].items() 
                            if game_data["roles"][p_id] == "Detektif"), None)
        if detective_id:
            target_role = game_data["roles"][detective_target]
            detective_name = next((p["name"] for p in game_data["players"] if p["id"] == detective_id), "Unknown")
            await context.bot.send_message(
                chat_id=detective_id,
                text=f"🔍 Hasil investigasi: target adalah seorang {target_role}"
            )

    return results

async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update and update.message:
        chat_id = update.message.chat_id
    else:
        chat_id = game_data["group_id"]
        
    if not game_data["group_id"]:
        if update and update.message:
            await update.message.reply_text("❌ Gunakan /setgroup terlebih dahulu di grup!")
        return

    if len(game_data["players"]) < 4:
        if update and update.message:
            await update.message.reply_text("❌ Minimal pemain untuk memulai adalah 4 orang.")
        return

    if game_data["phase"] != "idle":
        if update and update.message:
            await update.message.reply_text("❌ Game sedang berjalan!")
        return

    game_data["phase"] = "playing"
    game_data["current_day"] = 1
    
    # Send game starting message
    await context.bot.send_message(
        chat_id=game_data["group_id"],
        text="🎮 Permainan dimulai! Mengirim peran ke masing-masing pemain..."
    )
    
    # Assign roles to players
    await assign_roles(update, context)
    
    # Start with night phase
    await night_phase(update, context)

async def assign_roles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    num_players = len(game_data["players"])
    roles = generate_role_distribution(num_players)

    random.shuffle(roles)
    mafia_members = []

    # Assign roles
    for i, player in enumerate(game_data["players"]):
        role = roles[i]
        game_data["roles"][player["id"]] = role

        role_desc = {
            "Boss Mafia": "👑 Pemimpin mafia dengan kemampuan membunuh",
            "Mafia": "🔪 Bunuh warga setiap malam bersama mafia lain",
            "Dokter": "👨‍⚕️ Selamatkan satu pemain setiap malam",
            "Detektif": "🕵️ Selidiki peran satu pemain setiap malam",
            "Pelacur": "💃 Halangi aksi satu pemain setiap malam",
            "Pembunuh": "🔫 Bunuh satu target di malam hari",
            "Pengintai": "👀 Intai aktivitas pemain di malam hari",
            "Bodyguard": "🛡️ Lindungi satu pemain dari serangan",
            "Warga": "👥 Bantu menangkap mafia dengan voting"
        }

        msg = f"🎭 Peran kamu adalah: {role}\n{role_desc[role]}"
        await context.bot.send_message(
            chat_id=player["id"],
            text=msg
        )

        if role in ["Boss Mafia", "Mafia"]:
            mafia_members.append(player)

    # Send mafia group chat info
    if mafia_members:
        mafia_list = []
        for p in mafia_members:
            role = game_data["roles"][p["id"]]
            icon = "👑" if role == "Boss Mafia" else "🔪"
            mafia_list.append(f"{icon} {role} @{p['name']}")

        mafia_list_str = "\n".join(mafia_list)
        for mafia in mafia_members:
            await context.bot.send_message(
                chat_id=mafia["id"],
                text=f"👥 Tim Mafia:\n{mafia_list_str}\n\nChat di sini untuk berbicara dengan mafia lain"
            )

    await context.bot.send_message(
        chat_id=game_data["group_id"],
        text="✅ Peran telah dibagikan ke semua pemain. Malam pertama dimulai..."
    )

async def night_phase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_data["phase"] = "night"
    game_data["night_actions"] = {}

    # Send night message with GIF
    await context.bot.send_animation(
        chat_id=game_data["group_id"],
        animation="https://media.tenor.com/P5CR7NZc2AAAAAAC/dark-darkness.gif",
        caption=f"🌙 Malam ke-{game_data['current_day']} telah tiba!\nPara pemain dengan peran khusus dapat melakukan aksi malam.\nSilakan cek pesan pribadi dari bot."
    )

    # Show alive players list
    alive_list = "\n".join([f"{i}. @{p['name']}" for i, p in enumerate(game_data["alive_players"], 1)])
    await context.bot.send_message(
        chat_id=game_data["group_id"],
        text=f"👥 Pemain hidup ({len(game_data['alive_players'])}):\n{alive_list}\n\n⏰ Waktu malam: {game_data['night_time']} detik"
    )

    # Send role instructions to each player
    for player in game_data["alive_players"]:
        role = game_data["roles"][player["id"]]
        buttons = [[InlineKeyboardButton(p["name"], callback_data=f"night_{p['id']}")] 
                  for p in game_data["alive_players"] if p["id"] != player["id"]]
        
        if not buttons:  # If no other players alive
            continue
            
        markup = InlineKeyboardMarkup(buttons)

        role_instructions = {
            "Boss Mafia": "👑 Pilih target untuk dibunuh:",
            "Mafia": "🔪 Pilih target untuk dibunuh:",
            "Dokter": "👨‍⚕️ Pilih pemain untuk diselamatkan:",
            "Detektif": "🕵️ Pilih pemain untuk diselidiki:",
            "Pelacur": "💃 Pilih pemain untuk diganggu:",
            "Bodyguard": "🛡️ Pilih pemain untuk dilindungi:",
            "Pembunuh": "🔫 Pilih target untuk dibunuh:"
        }
        
        if role in role_instructions:
            await context.bot.send_message(
                chat_id=player["id"],
                text=f"{role_instructions[role]}",
                reply_markup=markup
            )
        else:
            await context.bot.send_message(
                chat_id=player["id"],
                text=f"Kamu adalah {role}. Tunggu hingga pagi tiba."
            )

    # Set timer for night phase
    context.job_queue.run_once(
        lambda ctx: asyncio.create_task(day_phase(None, context)),
        game_data["night_time"]
    )

async def day_phase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Update game phase
    game_data["phase"] = "day"
    game_data["votes"] = {}
    
    # Send day animation
    await context.bot.send_animation(
        chat_id=game_data["group_id"],
        animation="https://c.tenor.com/3GgX9XG4fe0AAAAd/tenor.gif",
        caption=f"🌅 Hari ke-{game_data['current_day']} telah tiba!"
    )

    # Auto end game after 7 days
    if game_data["current_day"] > 7:
        await context.bot.send_message(
            chat_id=game_data["group_id"],
            text="🎭 Permainan berakhir karena sudah mencapai 7 hari!\nMafia menang!"
        )
        game_data["phase"] = "idle"
        game_data["players"] = []
        game_data["alive_players"] = []
        return

    # Process night results
    night_results = await process_night_actions()
    result_text = "\n".join(night_results) if night_results else "🌙 Tidak ada kejadian malam ini. Semua pemain masih hidup."
    
    await context.bot.send_message(
        chat_id=game_data["group_id"],
        text=f"📢 Hasil malam:\n{result_text}"
    )

    # Check win condition after night phase
    winners = check_win_condition()
    if winners:
        await context.bot.send_message(
            chat_id=game_data["group_id"],
            text=f"🎮 Permainan Selesai! {winners} menang!"
        )
        game_data["phase"] = "idle"
        return

    # Show alive players
    await show_alive_players(context)

    # Create voting buttons
    buttons = []
    for i, p in enumerate(game_data["alive_players"], 1):
        buttons.append([InlineKeyboardButton(f"Vote @{p['name']}", callback_data=f"vote_{p['id']}")])
    buttons.append([InlineKeyboardButton("❌ Skip Vote", callback_data="vote_skip")])
    markup = InlineKeyboardMarkup(buttons)

    # Send voting instructions
    await context.bot.send_message(
        chat_id=game_data["group_id"],
        text=f"⚖️ WAKTU VOTING!\nSiapa yang menurut kalian Mafia?\nPilih dengan bijak, kalian punya {game_data['vote_time']} detik untuk voting:",
        reply_markup=markup
    )

    # Send voting instructions to each player
    for player in game_data["alive_players"]:
        await context.bot.send_message(
            chat_id=player["id"],
            text="⚖️ Saatnya voting! Silakan kembali ke grup untuk memilih target eliminasi."
        )

    # Set timer for voting
    context.job_queue.run_once(
        lambda ctx: asyncio.create_task(end_voting(context)),
        game_data["vote_time"]
    )

async def end_voting(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=game_data["group_id"],
        text="⏰ Waktu voting telah berakhir!"
    )
    
    if not game_data["votes"]:
        await context.bot.send_message(
            chat_id=game_data["group_id"],
            text="🤔 Tidak ada yang voting hari ini! Tidak ada yang tereliminasi."
        )
    else:
        # Hitung hasil voting
        vote_counts = {}
        for player_id in game_data["votes"].values():
            if player_id not in vote_counts:
                vote_counts[player_id] = 0
            vote_counts[player_id] += 1
        
        # Show vote results
        vote_result = "📊 Hasil voting:\n"
        for player_id, count in vote_counts.items():
            player_name = next((p["name"] for p in game_data["players"] if p["id"] == player_id), "Unknown")
            vote_result += f"@{player_name}: {count} vote\n"
            
        await context.bot.send_message(
            chat_id=game_data["group_id"],
            text=vote_result
        )
        
        # Find player with most votes
        if vote_counts:
            max_votes = max(vote_counts.values())
            voted_players = [pid for pid, votes in vote_counts.items() if votes == max_votes]

            if len(voted_players) > 1:
                await context.bot.send_message(
                    chat_id=game_data["group_id"],
                    text