import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta

# ================= CONFIGURACIÓN ================
import os

# Obtener variables de entorno (Railway) o usar valores por defecto
API_TOKEN = os.environ.get('API_TOKEN', 'TU_TOKEN_AQUI')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '0'))

# ================================================

bot = telebot.TeleBot(API_TOKEN)

# Crear base de datos
def init_db():
    conn = sqlite3.connect('sfs_alliance.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            name TEXT,
            total_sfs INTEGER DEFAULT 0,
            today_sfs INTEGER DEFAULT 0,
            last_report_date TEXT,
            late_count INTEGER DEFAULT 0,
            joined_date TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            screenshot_date TEXT,
            sfs_amount INTEGER,
            is_valid INTEGER,
            notes TEXT,
            created_at TEXT
        )
    ''')
    
    conn.commit()
    return conn

conn = init_db()

# Comando /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Sin username"
    name = message.from_user.first_name
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, name, joined_date)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, name, today))
    conn.commit()
    
    welcome = f"""
👑 **BOT SFS ALLIANCE** 👑

¡Hola {name}! Bienvenido al sistema de reportes.

📊 **COMANDOS:**
/reportar - Reportar captura SFS
/misestadisticas - Ver tu progreso
/ranking - Ver clasificación
/ayuda - Información

📌 **REGLAS:**
• Meta diaria: 5,000 vistas
• Mínimo por captura: 200 vistas
• Máximo por captura: 1,000 vistas
• Domingos: Descanso
• 3 atrasos = Salida

Para reportar, envía una foto con:
1. Spam de la alianza visible
2. Confirmación de subida
3. Vistas claras (200-1000)

¡Éxito! 💪
    """
    bot.reply_to(message, welcome, parse_mode='Markdown')

# Comando /ayuda
@bot.message_handler(commands=['ayuda'])
def help_command(message):
    help_text = """
📖 **AYUDA - BOT SFS**

**¿CÓMO REPORTAR?**
1. Toma captura de tu SFS
2. Asegúrate que se vean:
   - El spam de la alianza
   - La confirmación de subida
   - Las vistas (200-1000)
3. Envía la foto al bot
4. El bot validará y sumará

**COMANDOS:**
/start - Iniciar el bot
/reportar - Iniciar reporte
/misestadisticas - Tu progreso
/ranking - Clasificación global
/ayuda - Este mensaje

**REGLAS IMPORTANTES:**
✅ Meta: 5,000 vistas/día
✅ Domingo: Descanso
✅ Máx 1 día atraso/adelanto
❌ 3 atrasos = Expulsión

¿Dudas? Contacta al admin.
    """
    bot.reply_to(message, help_text, parse_mode='Markdown')

# Comando /reportar
@bot.message_handler(commands=['reportar'])
def report_command(message):
    bot.reply_to(message, "📸 **Envía tu captura de SFS ahora**\n\nAsegúrate que se vean claramente las vistas.", parse_mode='Markdown')

# Recibir fotos
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    today = datetime.now()
    today_str = today.strftime('%Y-%m-%d')
    day_of_week = today.weekday()  # 0=Lunes, 6=Domingo
    
    # Verificar si es domingo
    if day_of_week == 6:
        bot.reply_to(message, 
            "❌ **HOY ES DOMINGO - DÍA DE DESCANSO**\n\n"
            "Los domingos no se suben capturas. ¡Disfruta tu día! 😊\n\n"
            "Vuelve mañana lunes.", 
            parse_mode='Markdown')
        return
    
    cursor = conn.cursor()
    
    # Verificar si ya reportó hoy
    cursor.execute('SELECT today_sfs FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result and result[0] >= 5000:
        bot.reply_to(message, 
            f"✅ **¡Ya cumpliste tu meta de hoy!**\n\n"
            f"Total: {result[0]}/5,000 vistas\n\n"
            f"¡Excelente trabajo! 🎉", 
            parse_mode='Markdown')
        return
    
    # Pedir cantidad de vistas (modo manual - más fácil)
    msg = bot.reply_to(message, 
        "🔢 **Ingresa la cantidad de vistas de esta captura:**\n\n"
        "Ejemplo: 500\n"
        "Mínimo: 200 | Máximo: 1000\n\n"
        "Escribe solo el número:")
    
    bot.register_next_step_handler(msg, process_sfs_amount, message)

def process_sfs_amount(message, original_message):
    try:
        views = int(message.text)
        
        # Validar rango
        if views < 200 or views > 1000:
            bot.reply_to(message, 
                "❌ **Cantidad inválida**\n\n"
                "Las vistas deben ser entre 200 y 1000.\n\n"
                "Usa /reportar para intentar de nuevo.", 
                parse_mode='Markdown')
            return
        
        user_id = original_message.from_user.id
        today_str = datetime.now().strftime('%Y-%m-%d')
        cursor = conn.cursor()
        
        # Actualizar usuario
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, name, joined_date)
            VALUES (?, ?, ?, ?)
        ''', (user_id, original_message.from_user.username, 
              original_message.from_user.first_name, today_str))
        
        cursor.execute('''
            UPDATE users 
            SET today_sfs = today_sfs + ?,
                total_sfs = total_sfs + ?,
                last_report_date = ?
            WHERE user_id = ?
        ''', (views, views, today_str, user_id))
        
        # Guardar reporte
        cursor.execute('''
            INSERT INTO reports (user_id, screenshot_date, sfs_amount, is_valid, notes, created_at)
            VALUES (?, ?, ?, 1, 'Aprobado', ?)
        ''', (user_id, today_str, views, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.commit()
        
        # Obtener estadísticas actualizadas
        cursor.execute('SELECT today_sfs, total_sfs FROM users WHERE user_id = ?', (user_id,))
        stats = cursor.fetchone()
        remaining = 5000 - stats[0]
        
        success_msg = f"""
✅ **¡CAPTURA VALIDADA!**

📊 **Vistas registradas:** {views}
📈 **Total hoy:** {stats[0]}/5,000
🎯 **Faltan:** {max(0, remaining)}
🏆 **Total acumulado:** {stats[1]}

{"🎉 ¡META COMPLETADA!" if remaining <= 0 else "💪 ¡Sigue así!"}
        """
        bot.reply_to(message, success_msg, parse_mode='Markdown')
        
    except ValueError:
        bot.reply_to(message, 
            "❌ **Error:** Ingresa solo números\n\n"
            "Ejemplo: 500\n\n"
            "Usa /reportar para intentar de nuevo.", 
            parse_mode='Markdown')

# Comando /misestadisticas
@bot.message_handler(commands=['misestadisticas'])
def user_stats(message):
    user_id = message.from_user.id
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        bot.reply_to(message, "No estás registrado. Usa /start primero")
        return
    
    today_sfs = user[4] if user[4] else 0
    total_sfs = user[3] if user[3] else 0
    late_count = user[6] if user[6] else 0
    remaining = 5000 - today_sfs
    
    stats_text = f"""
📊 **TUS ESTADÍSTICAS**

👤 **Usuario:** @{user[2] or 'Sin username'}
📅 **Hoy:** {today_sfs}/5,000 vistas
🎯 **Meta restante:** {max(0, remaining)}
🏆 **Total acumulado:** {total_sfs} vistas
⚠️ **Atrasos:** {late_count}/3

💡 **Estado:** {'✅ Meta cumplida' if today_sfs >= 5000 else '⏳ En progreso'}
    """
    bot.reply_to(message, stats_text, parse_mode='Markdown')

# Comando /ranking
@bot.message_handler(commands=['ranking'])
def ranking(message):
    cursor = conn.cursor()
    cursor.execute('''
        SELECT username, today_sfs, total_sfs 
        FROM users 
        ORDER BY today_sfs DESC, total_sfs DESC 
        LIMIT 10
    ''')
    
    users = cursor.fetchall()
    
    if not users:
        bot.reply_to(message, "Aún no hay reportes")
        return
    
    ranking_text = "🏆 **TOP 10 DEL DÍA** 🏆\n\n"
    for i, user in enumerate(users, 1):
        medal = ['🥇', '🥈', '🥉'][i-1] if i <= 3 else '🔹'
        username = user[0] or f"Usuario{i}"
        ranking_text += f"{medal} **{i}. @{username}** - {user[1]}/5k\n"
    
    ranking_text += "\n¡Sigue reportando para subir! 💪"
    bot.reply_to(message, ranking_text, parse_mode='Markdown')

# Comando /admin (solo para admin)
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(today_sfs) FROM users')
    total_today = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM reports WHERE created_at LIKE ?', (f"%{datetime.now().strftime('%Y-%m-%d')}%",))
    reports_today = cursor.fetchone()[0]
    
    admin_text = f"""
🔧 **PANEL DE ADMINISTRADOR**

👥 **Total usuarios:** {total_users}
📊 **Vistas hoy:** {total_today}/5,000 por usuario
📸 **Reportes hoy:** {reports_today}
📅 **Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

**Comandos admin:**
/reset - Resetear contadores diarios
    """
    bot.reply_to(message, admin_text, parse_mode='Markdown')

# Comando /reset (solo admin)
@bot.message_handler(commands=['reset'])
def reset_daily(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET today_sfs = 0')
    conn.commit()
    
    bot.reply_to(message, "✅ Contadores diarios reseteados")

# Mensaje inicial
print("🤖 BOT INICIADO...")
print("📱 Busca tu bot en Telegram y envíale /start")
print("⏹️  Presiona Ctrl + C para detener el bot")

# Iniciar bot
bot.infinity_polling()