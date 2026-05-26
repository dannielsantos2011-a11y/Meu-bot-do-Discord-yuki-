import discord
from discord.ext import commands
import os
import sqlite3
import requests
from openai import OpenAI

# ================= BOT =================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")
GROUP_ID = 668141642

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ================= BANCO =================
conn = sqlite3.connect("data.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    discord_id TEXT PRIMARY KEY,
    roblox_id TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    roblox_name TEXT,
    discord_id TEXT,
    type TEXT
)
""")

conn.commit()

# ================= ROBLOX =================
def pegar_rank(roblox_id):
    try:
        r = requests.get(f"https://groups.roblox.com/v1/users/{roblox_id}/groups/roles", timeout=10)
        if r.status_code != 200:
            return None

        for g in r.json().get("data", []):
            if g["group"]["id"] == GROUP_ID:
                return g["role"]["name"]
    except:
        pass
    return None


def pegar_username(roblox_id):
    try:
        r = requests.get(f"https://users.roblox.com/v1/users/{roblox_id}", timeout=10)
        if r.status_code == 200:
            return r.json().get("name")
    except:
        pass
    return None


# ================= RANK MAP (COMPLETO) =================
RANK_MAP = {
    "[Rcr] Recruta": "Rcr",
    "[Sd] Soldado": "Sd",
    "[Cb] Cabo": "Cb",
    "[3°Sgt] Terceiro-Sargento": "3°Sgt",
    "[2°Sgt] Segundo-Sargento": "2°Sgt",
    "[1°Sgt] Primeiro-Sargento": "1°Sgt",
    "[ST] Subtenente": "ST",
    "[Asp] Aspirante-a-Oficial": "Asp",
    "[2°Ten] Segundo-Tenente": "2°Ten",
    "[1°Ten] Primeiro-Tenente": "1°Ten",
    "[Cap] Capitão": "Cap",
    "[Maj] Major": "Maj",
    "[Ten-Cel] Tenente-Coronel": "Ten-Cel",
    "[Cel] Coronel": "Cel",
    "[Gen-B] General-de-Brigada": "Gen-B",
    "[Gen-D] General-de-Divisão": "Gen-D",
    "[Gen-E] General-de-Exército": "Gen-E"
}

# ================= LOGS =================
def salvar_log(nome, discord_id, tipo):
    cursor.execute("INSERT INTO logs VALUES (?, ?, ?)", (nome, discord_id, tipo))
    conn.commit()


def processar_logs(message):
    txt = message.content.lower()

    if "exilado(a):" in txt:
        for u in message.mentions:
            salvar_log(u.display_name, str(u.id), "exilio")

    if "banido(a):" in txt:
        for u in message.mentions:
            salvar_log(u.display_name, str(u.id), "ban")

    if "advertido:" in txt:
        for u in message.mentions:
            salvar_log(u.display_name, str(u.id), "advertencia")

    if "aprovados:" in txt:
        nomes = message.content.split("aprovados:")[-1]
        lista = [n.strip() for n in nomes.replace("\n", ",").split(",")]
        for nome in lista:
            if nome:
                salvar_log(nome, "", "recrutamento")

# ================= IA =================
def eh_militar(txt):
    termos = ["exílio", "banimento", "advertência", "verify", "link", "cargo", "patente"]
    return any(t in txt.lower() for t in termos)


async def responder_ia(msg):

    if eh_militar(msg):
        return "Não irei responder isso. Estude o regulamento antes de perguntar."

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Responda tudo em português claro e natural."},
                {"role": "user", "content": msg}
            ]
        )
        return r.choices[0].message.content
    except:
        return "Erro na IA."


# ================= COMANDOS =================
@bot.tree.command(name="link")
async def link(interaction: discord.Interaction, roblox_id: str):

    cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?)",
                   (str(interaction.user.id), roblox_id))
    conn.commit()

    await interaction.response.send_message("Conta vinculada.", ephemeral=True)


@bot.tree.command(name="verify")
async def verify(interaction: discord.Interaction):

    cursor.execute("SELECT roblox_id FROM users WHERE discord_id = ?",
                   (str(interaction.user.id),))
    result = cursor.fetchone()

    if not result:
        await interaction.response.send_message("Use /link primeiro.", ephemeral=True)
        return

    roblox_id = result[0]
    rank = pegar_rank(roblox_id)

    if not rank:
        await interaction.response.send_message("Erro ao pegar rank.", ephemeral=True)
        return

    prefix = RANK_MAP.get(rank, rank[:3])
    roblox_name = pegar_username(roblox_id) or interaction.user.name

    role = discord.utils.get(interaction.guild.roles, name=rank)

    if role:
        try:
            await interaction.user.add_roles(role)
        except:
            pass

    try:
        await interaction.user.edit(nick=f"[{prefix}] ({roblox_name})")
    except:
        pass

    await interaction.response.send_message(
        f"✔ Verificado!\nRank: {rank}",
        ephemeral=True
    )


# ================= IA CHAT =================
@bot.event
async def on_message(message):

    if message.author.bot:
        return

    processar_logs(message)

    if bot.user in message.mentions:
        resposta = await responder_ia(message.content)
        await message.channel.send(resposta)
        return

    await bot.process_commands(message)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot online como {bot.user}")


bot.run("TOKEN")
