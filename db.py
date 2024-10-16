import mysql.connector
from mysql.connector import Error
import datetime
import pytz


# Fuso horário de Brasília (GMT-3)
BRAZIL_TZ = pytz.timezone("America/Sao_Paulo")

# Informações de conexão com o banco de dados
def create_connection():
    """Estabelece a conexão com o banco de dados MySQL"""
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="User",
            password="password",
            database="database"
        )
        if connection.is_connected():
            print("Conexão ao banco de dados MySQL estabelecida com sucesso")
        return connection
    except Error as e:
        print(f"Erro ao conectar ao MySQL: {e}")
        return None

# Função para obter compromissos nas próximas 24 horas e que ainda não receberam lembretes
def get_appointments_in_next_24_hours():
    """Recupera compromissos marcados nas próximas 24 horas que ainda não receberam lembrete"""
    connection = create_connection()
    if connection is not None:
        try:
            cursor = connection.cursor()
            now = datetime.datetime.now(BRAZIL_TZ)
            next_24_hours = now + datetime.timedelta(hours=24)

            # Consulta para encontrar compromissos nas próximas 24 horas e cujo lembrete ainda não foi enviado
            query = """
                SELECT a.appointment_id, a.appointment_date, a.appointment_time, p.name, p.telegram_id
                FROM appointments a
                JOIN patients p ON a.patient_id = p.patient_id
                WHERE a.appointment_date = %s AND a.reminder_sent = FALSE
            """
            cursor.execute(query, (next_24_hours.date(),))
            appointments = cursor.fetchall()
            return appointments
        except Error as e:
            print(f"Erro ao buscar compromissos: {e}")
        finally:
            cursor.close()
            connection.close()
    return []

# Função para armazenar diálogo no banco de dados
def save_dialogue(telegram_id, user_message, bot_response):
    """Armazena o diálogo no banco de dados"""
    connection = create_connection()
    if connection is not None:
        try:
            cursor = connection.cursor()
            query = """
                INSERT INTO dialogues (telegram_id, user_message, bot_response)
                VALUES (%s, %s, %s)
            """
            cursor.execute(query, (telegram_id, user_message, bot_response))
            connection.commit()
        except Error as e:
            print(f"Erro ao salvar diálogo: {e}")
        finally:
            cursor.close()
            connection.close()


def delete_appointment(appointment_id):
    """Apaga um compromisso do banco de dados"""
    connection = create_connection()
    if connection is not None:
        try:
            cursor = connection.cursor()
            query = "DELETE FROM appointments WHERE appointment_id = %s"
            cursor.execute(query, (appointment_id,))
            connection.commit()
        except Error as e:
            print(f"Erro ao apagar compromisso: {e}")
        finally:
            cursor.close()
            connection.close()


def check_availability(date, time):
    """Verifica se há disponibilidade para um novo compromisso"""
    connection = create_connection()
    if connection is not None:
        try:
            cursor = connection.cursor()
            query = """
                SELECT COUNT(*) FROM appointments
                WHERE appointment_date = %s AND appointment_time = %s
            """
            cursor.execute(query, (date, time))
            result = cursor.fetchone()
            return result[0] == 0  # Retorna True se estiver disponível
        except Error as e:
            print(f"Erro ao verificar disponibilidade: {e}")
        finally:
            cursor.close()
            connection.close()
    return False

def add_appointment(patient_id, date, time):
    """Adiciona um novo compromisso ao banco de dados"""
    connection = create_connection()
    if connection is not None:
        try:
            cursor = connection.cursor()
            query = """
                INSERT INTO appointments (patient_id, appointment_date, appointment_time)
                VALUES (%s, %s, %s)
            """
            cursor.execute(query, (patient_id, date, time))
            connection.commit()
        except Error as e:
            print(f"Erro ao adicionar compromisso: {e}")
        finally:
            cursor.close()
            connection.close()


def find_next_available_time(date):
    """Encontra o próximo horário disponível em uma data específica"""
    connection = create_connection()
    if connection is not None:
        try:
            cursor = connection.cursor()
            query = """
                SELECT appointment_time FROM appointments
                WHERE appointment_date = %s
                ORDER BY appointment_time ASC
            """
            cursor.execute(query, (date,))
            occupied_times = cursor.fetchall()

            # Supondo que o horário de trabalho seja das 08:00 às 18:00
            available_times = generate_working_hours()

            for time in available_times:
                if (time,) not in occupied_times:
                    return time

            return None  # Não há horários disponíveis
        except Error as e:
            print(f"Erro ao encontrar próximo horário disponível: {e}")
        finally:
            cursor.close()
            connection.close()
    return None

def generate_working_hours():
    """Gera os horários de trabalho (por exemplo, das 08:00 às 18:00)"""
    working_hours = []
    for hour in range(8, 18):  # Horários das 08:00 às 17:00
        working_hours.append(f"{hour:02d}:00:00")
    return working_hours


def get_appointment_by_telegram_id(telegram_id):
    connection = create_connection()
    if connection is not None:
        try:
            cursor = connection.cursor()
            query = """
            SELECT a.appointment_id, a.appointment_date, a.appointment_time, p.patient_id
            FROM appointments a
            JOIN patients p ON a.patient_id = p.patient_id
            WHERE p.telegram_id = %s
            """
            cursor.execute(query, (telegram_id,))
            appointment = cursor.fetchone()
            return appointment
        except Error as e:
            print(f"Erro ao buscar compromisso: {e}")
        finally:
            cursor.close()
            connection.close()
    return None



# Função para marcar lembrete como enviado
def mark_reminder_sent(appointment_id):
    """Marca o lembrete como enviado para um compromisso"""
    connection = create_connection()
    if connection is not None:
        try:
            cursor = connection.cursor()
            query = "UPDATE appointments SET reminder_sent = TRUE WHERE appointment_id = %s"
            cursor.execute(query, (appointment_id,))
            connection.commit()
        except Error as e:
            print(f"Erro ao marcar lembrete como enviado: {e}")
        finally:
            cursor.close()
            connection.close()