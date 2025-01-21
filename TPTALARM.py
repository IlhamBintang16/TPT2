import time
import logging
from pymodbus.client import ModbusTcpClient
import mysql.connector

# Konfigurasi logging
logging.basicConfig(filename='alarm_log.log', filemode='a', level=logging.WARNING,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Konfigurasi MySQL
DB_CONFIG = {
    "host": "192.168.1.147",
    "user": "energy",
    "password": "energypass",  # Ganti dengan password MySQL Anda
    "database": "sensor_labtekvi"
}

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

    client = ModbusTcpClient(IP_ADDRESS, port=PORT, timeout=5)

    if not client.connect():
        print("Gagal terhubung ke server Modbus.")
        return

    print("Terhubung ke server Modbus.")

    try:
        for _ in range(5):
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
                            print(f"ALARM TRIGGERED: {log_message}")
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

            time.sleep(5)

    finally:
        client.close()
        print("Terputus dari server Modbus.")

if __name__ == "__main__":
    main()
