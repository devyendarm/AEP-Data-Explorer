import argparse
import requests
import time
from auth import AEPAuthHandler
from logger import logger

def poll_query(query_id, initial_wait=45, subsequent_wait=15):
    """
    Polls the query status until SUCCESS, FAILED, or CANCELLED.
    """
    auth = AEPAuthHandler()
    
    url = f"https://platform.adobe.io/data/foundation/query/queries/{query_id}"
    
    logger.info(f"Polling Query {query_id}...")
    logger.info(f"Waiting {initial_wait} seconds before first check...")
    time.sleep(initial_wait)
    
    while True:
        # Refresh token if needed (handled by get_headers/get_access_token inside auth usually, 
        # but here we might need to be explicit if loop is long)
        auth.get_access_token() 
        headers = auth.get_headers()
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            state = data.get("state")
            logger.info(f"Query {query_id} state: {state}")
            
            if state == "SUCCESS":
                logger.info(f"Query Success Response: {data}")
                return True
            elif state in ["FAILED", "CANCELLED"]:
                raise Exception(f"Query failed with state: {state}")
            
            logger.info(f"Query still running. Waiting {subsequent_wait} seconds...")
            time.sleep(subsequent_wait)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error polling query: {e}")
            time.sleep(poll_interval) # Retry on network error?

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Poll AEP Query Status")
    parser.add_argument("--query_id", required=True, help="The Query ID to poll")
    parser.add_argument("--interval", type=int, default=90, help="Polling interval in seconds")
    
    args = parser.parse_args()
    
    try:
        poll_query(args.query_id, args.interval)
        print("STATUS:SUCCESS")
    except Exception as e:
        logger.error(f"Failed: {e}")
        print("STATUS:FAILED")
        exit(1)
