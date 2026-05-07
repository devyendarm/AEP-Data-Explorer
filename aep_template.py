import argparse
import requests
import json
from auth import AEPAuthHandler
from logger import logger

def submit_template(template_id, params=None, db_name="prod:all"):
    """
    Submits a query execution request using a saved query template.
    """
    auth = AEPAuthHandler()
    auth.get_access_token()
    
    url = "https://platform.adobe.io/data/foundation/query/queries"
    headers = auth.get_headers()
    headers["Accept"] = "application/json"
    headers["Content-Type"] = "application/json"
    
    payload = {
        "templateId": template_id,
        "dbName": db_name
    }
    if params:
        payload["queryParameters"] = params
        
    logger.info(f"Submitting query template {template_id} to AEP...")
    response = requests.post(url, headers=headers, json=payload)
    
    try:
        response.raise_for_status()
        data = response.json()
        query_id = data.get("id")
        logger.info(f"Query submitted. ID: {query_id}")
        return query_id
    except requests.exceptions.HTTPError as e:
        logger.error(f"Query submission failed. Response: {response.text}")
        raise e

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Submit AEP Query Template")
    parser.add_argument("--template_id", required=True, help="The Template ID to execute")
    parser.add_argument("--params", help="JSON string of query parameters")
    parser.add_argument("--db_name", default="prod:all", help="Database name (default: prod:all)")
    
    args = parser.parse_args()
    
    params = None
    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError:
            logger.error("Invalid JSON for params")
            exit(1)
            
    try:
        qid = submit_template(args.template_id, params, args.db_name)
        print(f"QUERY_ID:{qid}")
    except Exception as e:
        logger.error(f"Failed: {e}")
        exit(1)
