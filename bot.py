import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from model import generate_text
from config import TELEGRAM_TOKEN
from db import (create_connection, get_appointments_in_next_24_hours, 
                mark_reminder_sent, get_appointment_by_telegram_id, 
                save_dialogue, delete_appointment, check_availability, 
                add_appointment, find_next_available_time)
from dateutil import parser
from datetime import datetime, timedelta
import pytz
from colorama import Fore, Style, init  # Biblioteca para cores no terminal

# Inicializa o uso de cores no terminal
init()

# Fuso horário de Brasília
BRAZIL_TZ = pytz.timezone("America/Sao_Paulo")

# Estados da conversa
NEW_DATE, CONFIRM_REMARK = range(2)

def parse_date_time(user_input):
    """Tenta interpretar a data e hora de um texto fornecido pelo usuário."""
    try:
        logging.info(f"{Fore.YELLOW}Recebido input para análise de data e hora: {user_input}{Style.RESET_ALL}")
        
        # Limpa palavras desnecessárias como "dia", "de", etc., apenas se isoladas
        user_input = user_input.lower()
        palavras_ignoradas = [" dia ", " de ", " do ", " da ", " às ", " as ", " ao ", " a ", " o ", " para "]
        for palavra in palavras_ignoradas:
            user_input = user_input.replace(palavra, " ")

        # Remove espaços extras
        user_input = " ".join(user_input.split())

        logging.info(f"{Fore.CYAN}Texto para análise após limpeza: {user_input}{Style.RESET_ALL}")

        # Substituir expressões comuns de tempo como "amanhã" ou "hoje"
        if "amanhã" in user_input:
            user_input = user_input.replace("amanhã", (datetime.now(BRAZIL_TZ) + timedelta(days=1)).strftime('%Y-%m-%d'))
        if "hoje" in user_input:
            user_input = user_input.replace("hoje", datetime.now(BRAZIL_TZ).strftime('%Y-%m-%d'))

        # Usa o dateutil.parser para interpretar a data e a hora
        now = datetime.now(BRAZIL_TZ)
        parsed_datetime = parser.parse(user_input, fuzzy=True, default=now)

        # Se a data interpretada é anterior à data atual, assume que o usuário quis o próximo ano
        if parsed_datetime.year == now.year and parsed_datetime < now:
            parsed_datetime = parsed_datetime.replace(year=now.year + 1)

        # Formatar a data como YYYY-MM-DD e a hora como HH:MM:SS
        new_date = parsed_datetime.strftime('%Y-%m-%d')
        new_time = parsed_datetime.strftime('%H:%M:%S')
        
        logging.info(f"{Fore.GREEN}Data e hora interpretadas com sucesso: {new_date} {new_time}{Style.RESET_ALL}")
        return new_date, new_time

    except ValueError:
        logging.error(f"{Fore.RED}Falha ao interpretar a data e hora fornecidas: {user_input}{Style.RESET_ALL}")
        return None, None



# Configuração básica de logging para incluir o horário de Brasília
class BrazilFormatter(logging.Formatter):
    """Formata os logs para mostrar o horário de Brasília"""

    def formatTime(self, record, datefmt=None):
        record_time = datetime.now(BRAZIL_TZ).astimezone()
        return record_time.strftime("%Y-%m-%d %H:%M:%S")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)
for handler in logging.getLogger().handlers:
    handler.setFormatter(BrazilFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Função chamada quando o comando /start é enviado
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Olá! Eu sou um chatbot LLaMA. Como posso te ajudar?')

# Função para enviar lembretes aos pacientes
async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    appointments = get_appointments_in_next_24_hours()
    
    for appointment in appointments:
        appointment_id, appointment_date, appointment_time, name, telegram_id = appointment
        
        reminder_message = f"Olá {name}, lembrete do seu compromisso marcado para {appointment_date} às {appointment_time}. Por favor, confirme, remarque ou cancele sua consulta."
        await context.bot.send_message(chat_id=telegram_id, text=reminder_message)
        mark_reminder_sent(appointment_id)

# Função para analisar a intenção do paciente
def analyze_intent(patient_response):
    response = patient_response.lower()

    if "confirmar" in response or "confirmo" in response or "sim" in response:
        return "confirmar"
    elif "remarcar" in response or "adiar" in response or "mudar" in response:
        return "remarcar"
    elif "cancelar" in response or "não posso" in response or "desmarcar" in response:
        return "cancelar"
    else:
        return "intenção não identificada"

# Função para capturar a resposta do paciente e identificar a intenção
async def handle_patient_response(update: Update, context):
    """Captura a resposta do paciente e identifica a intenção"""
    patient_response = update.message.text
    patient_telegram_id = update.message.chat_id
    
    # Analisar a intenção do paciente
    intent = analyze_intent(patient_response)
    
    logging.info(f"{Fore.CYAN}Intenção identificada: {intent}{Style.RESET_ALL}")
    
    # Obter o compromisso do paciente
    appointment = get_appointment_by_telegram_id(patient_telegram_id)

    if appointment:
        appointment_id, appointment_date, appointment_time = appointment  # Agora esperamos apenas 3 valores
    else:
        await update.message.reply_text("Não encontrei um compromisso agendado para você.")
        return
    
    # Se o paciente confirmou, nada muda
    if intent == "confirmar":
        response = f"Obrigado por confirmar sua consulta marcada para {appointment_date} às {appointment_time}."
    
    # Se o paciente deseja cancelar, apaga o compromisso
    elif intent == "cancelar":
        delete_appointment(appointment_id)
        response = "Sua consulta foi cancelada com sucesso."

    # Se o paciente deseja remarcar, pergunta o novo horário
    elif intent == "remarcar":
        response = "Por favor, informe o novo dia e horário para remarcarmos sua consulta."
        await update.message.reply_text(response)
        
        # Iniciar o estado de aguardo para o novo horário
        return NEW_DATE

    else:
        response = "Desculpe, não consegui entender sua resposta. Por favor, tente novamente."

    # Salvar o diálogo no banco de dados
    save_dialogue(patient_telegram_id, patient_response, response)

    # Envia a resposta gerada ao paciente
    await update.message.reply_text(response)

    return ConversationHandler.END

# Função para lidar com o novo horário
async def handle_reschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_response = update.message.text
    logging.info(f"{Fore.YELLOW}Recebido novo horário para remarcar: {new_response}{Style.RESET_ALL}")
    
    new_date, new_time = parse_date_time(new_response)
    
    if new_date and new_time:
        appointment = get_appointment_by_telegram_id(update.message.chat_id)
        appointment_id, _, _, patient_id = appointment

        if check_availability(new_date, new_time):
            add_appointment(patient_id, new_date, new_time)
            response = f"Sua consulta foi remarcada para {new_date} às {new_time}."
            logging.info(f"{Fore.GREEN}Consulta remarcada com sucesso para {new_date} às {new_time}{Style.RESET_ALL}")
        else:
            next_time = find_next_available_time(new_date)
            if next_time:
                response = f"O horário solicitado está ocupado. O próximo horário disponível é {next_time}. Deseja remarcar para esse horário?"
                logging.info(f"{Fore.YELLOW}Próximo horário disponível sugerido: {next_time}{Style.RESET_ALL}")
            else:
                response = "Infelizmente, não há horários disponíveis para o dia solicitado."
                logging.error(f"{Fore.RED}Nenhum horário disponível para a data solicitada: {new_date}{Style.RESET_ALL}")
    else:
        response = "Desculpe, não consegui interpretar a data e hora fornecidas. Por favor, tente novamente."
        logging.error(f"{Fore.RED}Falha ao interpretar a data e hora fornecidas: {new_response}{Style.RESET_ALL}")

    await update.message.reply_text(response, reply_markup=ReplyKeyboardRemove())
    save_dialogue(update.message.chat_id, new_response, response)

    return ConversationHandler.END

# Função principal para iniciar o bot e agendar os lembretes
def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    job_queue = application.job_queue

    now_brazil = datetime.now(BRAZIL_TZ)
    first_check = now_brazil + timedelta(seconds=60)
    first_check_utc = first_check.astimezone(pytz.utc)

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_patient_response)],
        states={
            NEW_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reschedule)],
        },
        fallbacks=[CommandHandler('start', start)]
    )

    application.add_handler(conv_handler)
    job_queue.run_repeating(send_reminders, interval=30, first=first_check_utc)
    application.run_polling()

if __name__ == "__main__":
    main()
