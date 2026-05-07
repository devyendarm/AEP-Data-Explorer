import argparse
import requests
from auth import AEPAuthHandler
from logger import logger

def get_latest_batch(dataset_id):
    """
    Retrieves the ID of the latest successful batch for a given dataset.
    """
    auth = AEPAuthHandler()
    auth.get_access_token()
    
    url = f"https://platform.adobe.io/data/foundation/catalog/batches?dataSet={dataset_id}&limit=1&orderBy=desc:created"
    headers = auth.get_headers()
    
    logger.info(f"Fetching latest batch for dataset {dataset_id}...")
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    
    if isinstance(data, dict):
        if not data:
            raise Exception(f"No batches found for dataset {dataset_id}")
        latest_batch_id, batch_obj = next(iter(data.items()))
        status = batch_obj.get("status", "unknown")
        
        if status in ["failed", "abandoned"]:
            raise Exception(f"The latest batch ({latest_batch_id}) failed ingestion! Status: {status}")
            
        logger.info(f"Latest batch ID: {latest_batch_id} (Status: {status})")
        return latest_batch_id
        
    elif isinstance(data, list):
         if not data:
            raise Exception(f"No batches found for dataset {dataset_id}")
         batch_obj = data[0]
         latest_batch_id = batch_obj.get("id")
         status = batch_obj.get("status", "unknown")
         
         if status in ["failed", "abandoned"]:
            raise Exception(f"The latest batch ({latest_batch_id}) failed ingestion! Status: {status}")
            
         logger.info(f"Latest batch ID: {latest_batch_id} (Status: {status})")
         return latest_batch_id
    else:
        raise Exception(f"Unexpected response format from Catalog API: {type(data)}")

def get_dataset_name(dataset_id):
    """
    Retrieves the name of the dataset.
    """
    auth = AEPAuthHandler()
    auth.get_access_token()
    
    url = f"https://platform.adobe.io/data/foundation/catalog/dataSets/{dataset_id}"
    headers = auth.get_headers()
    
    logger.info(f"Fetching info for dataset {dataset_id}...")
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    # Usually returns the dataset object directly or a dict with keys?
    # /dataSets/{id} returns the object directly.
    # We generally look for "name"
    
    ds_name = data.get("name")
    if not ds_name:
        # Fallback: sometimes it's in a list? No, specific ID endpoint should return obj.
        # But if it's a map?
        ds_name = next(iter(data)).get("name") if isinstance(data, dict) and data else None
        
    if not ds_name:
         raise Exception(f"Could not resolve name for dataset {dataset_id}")
         
    logger.info(f"Resolved Dataset Name: {ds_name}")
    return ds_name

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get Latest Batch ID for Dataset")
    parser.add_argument("--dataset_id", required=True, help="The Dataset ID")
    
    args = parser.parse_args()
    
    try:
        batch_id = get_latest_batch(args.dataset_id)
        print(f"BATCH_ID:{batch_id}")
    except Exception as e:
        logger.error(f"Failed: {e}")
        exit(1)
