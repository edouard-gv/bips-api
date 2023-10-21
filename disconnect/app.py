import json
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('bipers')


def lambda_handler(event, context):
    connection_id = event['requestContext']['connectionId']

    # Supprimer l'ID de connexion de DynamoDB
    table.delete_item(Key={'connectionId': connection_id})

    # Répondre au client
    response = {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Déconnexion réussie!"
        })
    }
    return response
