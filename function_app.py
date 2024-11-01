import azure.functions as func
import logging
import requests
import json
from datetime import datetime
from azure.storage.blob import BlobServiceClient
import os

# Inicialización de la app de Azure Function
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Variables de entorno
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
AD_ACCOUNT_ID = os.getenv("AD_ACCOUNT_ID")
BLOB_CONNECTION_STRING = os.getenv("BLOB_CONNECTION_STRING")
BLOB_CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME")

@app.function_name(name="MetAdeemyTimer")
@app.schedule(schedule="0 0 */4 * * *", arg_name="timer", run_on_startup=True, use_monitor=True)
def MetAdeemy(timer: func.TimerRequest) -> None:
    logging.info("Timer trigger function ran at %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # Definición de métricas y configuración de la solicitud a Meta API
    url = f"https://graph.facebook.com/v17.0/act_{AD_ACCOUNT_ID}/campaigns"
    params = {
        "access_token": ACCESS_TOKEN,
        "fields": "id,insights{reach,impressions,spend,clicks,cpc,cpm,conversions,ctr,cpp,actions}",
        "time_range": json.dumps({
            "since": "2024-10-01",
            "until": datetime.today().strftime('%Y-%m-%d')
        })
    }

    # Realizar la solicitud a la API de Meta
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()  # Parseo de la respuesta JSON
        logging.info("Datos obtenidos de Meta API exitosamente.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error al obtener datos de Meta API: {e}")
        return  # Termina la ejecución si hay error en la solicitud

    # Extraer y formatear datos de `actions`, y obtener solo el valor de "lead"
    for campaign_data in data.get("data", []):
        insights = campaign_data.get("insights", {}).get("data", [])
        for insight_data in insights:
            actions = insight_data.get("actions", [])
            lead_value = next((action["value"] for action in actions if action["action_type"] == "lead"), "0")
            insight_data["lead"] = lead_value  # Agregar "lead" al diccionario de insights
    
    # Serializar los datos a JSON
    json_data = json.dumps(data)

    # Conectar con Azure Blob Storage y preparar para almacenar los datos
    try:
        blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)

        # Crear un nombre único para el archivo blob
        blob_name = "meta_metrics_data.json"
        blob_client = container_client.get_blob_client(blob_name)

        # Subir los datos al blob
        blob_client.upload_blob(json_data, overwrite=True)
        logging.info(f"Métricas guardadas exitosamente en {blob_name}")
    except Exception as e:
        logging.error(f"Error al subir datos a Blob Storage: {e}")
