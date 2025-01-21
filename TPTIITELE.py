import time
import logging
import requests
from pymodbus.client import ModbusTcpClient
import mysql.connector

#Konfigurasi penggunaan bot telegram
BOT_TOKEN =  "7885685265:AAHv4VjzU6n3RFzdJndTFuZhsnSBMG7i_tw"
CHAT_ID = -4720345037
'''url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
response = requests.get(url)
print(response.json())

message = 'Haloo Penduduk LABTEK VI'
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={message}"
r = requests.get(url)
print(r.json())'''

# Konfigurasi logging
logging.basicConfig(filename='alarm_log.log', filemode='a', level=logging.WARNING,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Konfigurasi MySQL
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Ilhambintang103!)#",  # Ganti dengan password MySQL Anda
    "database": "TPT2"
}

# Konfigurasi Pesan Telegram
ALARM_THRESHOLD = 10  # Batas alarm berturut-turut sebelum mengirim pesan
MESSAGE_TEMPLATE = (
    "⚠️ *Warning*: Sensor dengan ID {slave_id} pada Ruangan {room} triggered an alarm for {count} consecutive measurements! 🚨\n"
    "🔥 With Average Temperature *{avg_temp:.1f}°C* and Humidity *{avg_hum:.1f}%* 💨.\n"
    "Please take immediate action! ⏳"
)
WAIT_TIME_BETWEEN_MESSAGES = 15  # Jeda waktu antar pengiriman pesan dalam detik

# Konfigurasi alarm
ALARM_THRESHOLD = 10  # Batas alarm berturut-turut sebelum mencatat log
ROOM_NAMES = {
    1: "Lab Pemprosesan Material",
    2: "Lab Material Fungsional Maju",
    3: "Lab Material Fungsional Maju 1"
}
TEMPERATURE_RANGE = {
    1: (17, 27),  # Dalam derajat Celsius
    2: (17, 27),  # Dalam derajat Celsius
    3: (17, 23)   # Dalam derajat Celsius khusus Slave 3
}
HUMIDITY_RANGE = {
    1: (30, 80),  # Dalam persen
    2: (30, 80),  # Dalam persen
    3: (30, 60)   # Dalam persen khusus Slave 3
}

# Melacak alarm untuk setiap slave
alarm_counts = {1: 0, 2: 0, 3: 0}

# Menghitung rata-rata suhu dan kelembapan untuk catatan log
average_data = {
    1: {"temp": [], "hum": []},
    2: {"temp": [], "hum": []},
    3: {"temp": [], "hum": []}
}

def send_telegram_message(slave_id, count):
    """Kirim pesan Telegram ketika kondisi alarm terpenuhi."""
    try:
        avg_temp = sum(average_data[slave_id]["temp"]) / len(average_data[slave_id]["temp"])
        avg_hum = sum(average_data[slave_id]["hum"]) / len(average_data[slave_id]["hum"])
        room = ROOM_NAMES.get(slave_id, "Unknown Room")

        # Format pesan dengan template
        message = MESSAGE_TEMPLATE.format(room=room, slave_id=slave_id, count=count, avg_temp=avg_temp, avg_hum=avg_hum)

        # Escape karakter khusus untuk Markdown v2
        message = message.replace('-', '\\-').replace('.', '\\.').replace('!', '\\!')

        # Kirim pesan ke Telegram
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "MarkdownV2"}
        response = requests.post(url, data=data)

        if response.status_code == 200:
            print(f"Pesan Telegram terkirim untuk {room} (Slave {slave_id}).")
        else:
            print(f"Gagal mengirim pesan Telegram: {response.text}")
    except Exception as e:
        print(f"Error saat mengirim pesan Telegram: {e}")
    finally:
        time.sleep(WAIT_TIME_BETWEEN_MESSAGES)


def save_to_database(data):
    """Simpan data pengukuran ke database MySQL."""
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = """
            INSERT INTO alarm_table (
                temp1, hum1, alarm1, temp2, hum2, alarm2, temp3, hum3, alarm3, logger_warning
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, data)
        conn.commit()
        print("Data berhasil disimpan ke database.")
    except mysql.connector.Error as err:
        print(f"Error menyimpan ke database: {err}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


def read_registers(client, slave_id, start_register, count):
    """Membaca beberapa register dari slave Modbus."""
    try:
        response = client.read_input_registers(address=start_register, count=count, slave=slave_id)
        if response.isError():
            print(f"Error membaca dari Slave {slave_id}: {response}")
            return None
        return response.registers
    except Exception as e:
        print(f"Exception membaca dari Slave {slave_id}: {e}")
        return None


def main():
    IP_ADDRESS = "167.205.55.12"
    PORT = 502
    START_REGISTER = 1
    REGISTER_COUNT = 2

    client = ModbusTcpClient(IP_ADDRESS, port=PORT)

    if not client.connect():
        print("Gagal terhubung ke server Modbus.")
        return

    print("Terhubung ke server Modbus.")

    try:
        for _ in range(15):
            temp1, hum1, alarm1 = None, None, "NO"
            temp2, hum2, alarm2 = None, None, "NO"
            temp3, hum3, alarm3 = None, None, "NO"
            logger_warnings = []  # List untuk menyimpan log semua slave yang memicu alarm

            for slave_id in [1, 2, 3]:
                data = read_registers(client, slave_id, START_REGISTER, REGISTER_COUNT)
                if data:
                    temperature = data[0] / 10.0
                    humidity = data[1] / 10.0
                    alarm = "YES" if not (TEMPERATURE_RANGE[slave_id][0] < temperature < TEMPERATURE_RANGE[slave_id][1] and
                                          HUMIDITY_RANGE[slave_id][0] < humidity < HUMIDITY_RANGE[slave_id][1]) else "NO"

                    if alarm == "YES":
                        log_message = f"Alarm pada {ROOM_NAMES[slave_id]} (Slave {slave_id}): Temp={temperature}°C, Humidity={humidity}%"
                        logging.warning(log_message)
                        logger_warnings.append(log_message)  # Tambahkan log ke list

                        alarm_counts[slave_id] += 1
                        average_data[slave_id]["temp"].append(temperature)
                        average_data[slave_id]["hum"].append(humidity)

                        if alarm_counts[slave_id] == ALARM_THRESHOLD:
                            send_telegram_message(slave_id, ALARM_THRESHOLD)
                            average_data[slave_id]["temp"].clear()
                            average_data[slave_id]["hum"].clear()
                    else:
                        alarm_counts[slave_id] = 0

                    if slave_id == 1:
                        temp1, hum1, alarm1 = temperature, humidity, alarm
                    elif slave_id == 2:
                        temp2, hum2, alarm2 = temperature, humidity, alarm
                    elif slave_id == 3:
                        temp3, hum3, alarm3 = temperature, humidity, alarm

            # Gabungkan semua log menjadi satu string
            logger_warning = "\n".join(logger_warnings) if logger_warnings else None

            # Simpan ke database jika semua data tersedia
            if all(v is not None for v in [temp1, hum1, temp2, hum2, temp3, hum3]):
                db_data = (temp1, hum1, alarm1, temp2, hum2, alarm2, temp3, hum3, alarm3, logger_warning)
                save_to_database(db_data)

            time.sleep(2)

    finally:
        client.close()
        print("Terputus dari server Modbus.")


if __name__ == "__main__":
    main()

 







