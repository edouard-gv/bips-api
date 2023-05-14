import os
import json
from datetime import datetime, timedelta
import uuid

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import DecimalEncoder

# Configuration de la base de données DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("Bips")

# Fonction pour insérer un nouveau Bip dans la base de données
def add_bip(data):
    bip = {
        "id": str(uuid.uuid4()),
        "pseudo": data["pseudo"],
        "status_code": data["status_code"],
        "location": data["location"],
        "latitude": data.get("latitude", None),
        "longitude": data.get("longitude", None),
        "timestamp": datetime.utcnow().isoformat(),
    }
    table.put_item(Item=bip)
    return bip["id"]

# Fonction pour récupérer les Bips qui ont été postés au même endroit aujourd'hui
def get_bips(location):
    start_time = datetime.utcnow().date().isoformat()
    end_time = (datetime.utcnow().date() + timedelta(days=1)).isoformat()

    response = table.query(
        IndexName="location-timestamp-index",
        KeyConditionExpression=Key("location").eq(location) & Key("timestamp").between(start_time, end_time),
    )

    return [
        {"pseudo": bip["pseudo"], "status_code": decimal.Decimal(bip["status_code"]), "timestamp": bip["timestamp"]}
        for bip in response["Items"]
    ]

# Fonction principale pour AWS Lambda
def lambda_handler(event, context):
    if "http" in event["requestContext"]:
        http_method = event["requestContext"]["http"]["method"]
    else:
        http_method = event["requestContext"]["httpMethod"]

    if http_method == "POST":
        data = json.loads(event["body"])
        bip_id = add_bip(data)
        response = {"message": f"Bip stacked with ID: {bip_id}"}
    elif http_method == "GET":
        location = event["queryStringParameters"]["location"]
        response = get_bips(location)
    else:
        response = {"error": "Invalid request"}

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response),
    }
