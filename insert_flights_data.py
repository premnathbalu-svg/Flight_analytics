import requests
import mysql.connector
import pandas as pd
from datetime import datetime

# ---------- Db connection ----------
connection = mysql.connector.connect(
    host="localhost",
    user="root",
    password="12345678",
    database="flight_analytics"
)
connection.autocommit = True
cursor = connection.cursor()

# ---------- API config ----------
API_HOST = "aerodatabox.p.rapidapi.com"
API_KEY = "fe9db90f76msha063c2a1b85aacbp14b34ejsn1fedbf08e9e1" 

HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": API_HOST
}

columns = [
    "flight_id", "flight_number", "aircraft_registration",
    "origin_iata", "destination_iata",
    "scheduled_departure", "actual_departure",
    "scheduled_arrival", "actual_arrival",
    "status", "airline_code","aircraft_model"
]

departure_data = {c: [] for c in columns}
arrival_data = {c: [] for c in columns}

AIRPORT_CODE = [
    "LHR", "JFK", "CDG", "DXB", "HND",
    "SIN", "AMS", "FRA", "ATL", "ORD",
    "PEK", "SYD", "DEL", "GRU", "NRT"
]

# ---------- FETCH DATA ----------
for airport in AIRPORT_CODE:
    print(f"Fetching data for {airport}...")
    url = f"https://{API_HOST}/flights/airports/iata/{airport}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    data = response.json()

    # ---- DEPARTURES ----
    for i in data.get("departures", []):
        departure_data["flight_id"].append(
            f"{i.get('number','NA')}_{i['movement']['scheduledTime'].get('utc','NA')}"
        )
        departure_data["flight_number"].append(i.get("number"))
        departure_data["aircraft_registration"].append(
            i.get("aircraft", {}).get("reg")
        )
        departure_data["origin_iata"].append(
            i["movement"]["airport"].get("iata")
        )
        departure_data["destination_iata"].append(None)
        departure_data["scheduled_departure"].append(
            i["movement"]["scheduledTime"].get("utc","NA")
        )
        departure_data["actual_departure"].append(
            i["movement"].get("revisedTime", {}).get("utc")
        )
        departure_data["scheduled_arrival"].append(None)
        departure_data["actual_arrival"].append(None)
        departure_data["status"].append(i.get("status","NA"))
        departure_data["airline_code"].append(
            i.get("airline", {}).get("iata","NA")
        )
        departure_data["aircraft_model"].append(
            i.get("aircraft", {}).get("model","NA")
        )

    # ---- ARRIVALS ----
    for i in data.get("arrivals", []):
        arrival_data["flight_id"].append(
            f"{i.get('number','NA')}_{i['movement']['scheduledTime'].get('utc','NA')}"
        )
        arrival_data["flight_number"].append(i.get("number"))
        arrival_data["aircraft_registration"].append(None)
        arrival_data["origin_iata"].append(None)
        arrival_data["destination_iata"].append(
            i["movement"]["airport"].get("iata","NA")
        )
        arrival_data["scheduled_departure"].append(None)
        arrival_data["actual_departure"].append(None)
        arrival_data["scheduled_arrival"].append(
            i["movement"]["scheduledTime"].get("utc","NA")
        )
        arrival_data["actual_arrival"].append(
            i["movement"].get("revisedTime", {}).get("utc")
        )
        arrival_data["status"].append(i.get("status","NA"))
        arrival_data["airline_code"].append(
            i.get("airline", {}).get("iata","NA")
        )
        arrival_data["aircraft_model"].append(
            i.get("aircraft", {}).get("model","NA")
        )

df_flights = pd.concat(
    [pd.DataFrame(departure_data), pd.DataFrame(arrival_data)],
    ignore_index=True
)

now = pd.Timestamp.utcnow()
three_days_ago = now - pd.Timedelta(days=2)
dep_time = pd.to_datetime(df_flights["actual_departure"], errors="coerce")
arr_time = pd.to_datetime(df_flights["actual_arrival"], errors="coerce")


df_filtered = df_flights[
    (
        (dep_time >= three_days_ago) & (dep_time <= now)
    ) |
    (
        (arr_time >= three_days_ago) & (arr_time <= now)
    )
]
df_filtered = df_filtered.drop_duplicates(subset=["flight_id"])
insert_sql = """
INSERT INTO flights (
    flight_id,
    flight_number,
    aircraft_registration,
    origin_iata,
    destination_iata,
    scheduled_departure,
    actual_departure,
    scheduled_arrival,
    actual_arrival,
    status,
    airline_code,
    aircraft_model
) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
    aircraft_registration = VALUES(aircraft_registration),
    origin_iata = VALUES(origin_iata),
    destination_iata = VALUES(destination_iata),
    actual_departure = VALUES(actual_departure),
    actual_arrival = VALUES(actual_arrival),
    status = VALUES(status),
    airline_code = VALUES(airline_code),
    aircraft_model = VALUES(aircraft_model);
"""

data_tuples = list(
    df_filtered[columns].itertuples(index=False, name=None)
)

BATCH_SIZE = 500

for i in range(0, len(data_tuples), BATCH_SIZE):
    cursor.executemany(insert_sql, data_tuples[i:i + BATCH_SIZE])
    print(f"Inserted batch {i // BATCH_SIZE + 1}")

cursor.close()
connection.close()

print("ETL completed successfully ")
