import argparse
import requests
import json
import os
import tempfile
import shutil
from auth import AEPAuthHandler
from logger import logger

def get_batch_data(batch_id, download_dir=None):
    """
    Downloads the data files for a specific batch to a local directory.
    Returns the path to the directory containing the Parquet files.
    """
    auth = AEPAuthHandler()
    auth.get_access_token()
    headers = auth.get_headers()
    
    # Setup download directory
    if not download_dir:
        download_dir = os.path.join(tempfile.gettempdir(), "aep_data_cache", batch_id)
    
    if os.path.exists(download_dir):
        # Clean up existing? Or resume? For now, clean up to ensure fresh data
        shutil.rmtree(download_dir)
    os.makedirs(download_dir, exist_ok=True)
    
    logger.info(f"Downloading batch {batch_id} to {download_dir}...")

    # 1. Fetch File List
    url = f"https://platform.adobe.io/data/foundation/export/batches/{batch_id}/files?limit=100"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            sandbox = auth.config.get("sandbox_name", "prod")
            msg = (f"Batch not found (404). Please verify:\n"
                   f"1. Batch ID '{batch_id}' is correct.\n"
                   f"2. You are connected to the correct sandbox ('{sandbox}').\n"
                   f"3. You have 'View' permissions.")
            logger.error(msg)
            raise Exception(msg) from e
        raise e
    
    data = response.json()
    files = data.get("data", [])
    
    if not files:
         raise Exception(f"No files found in batch {batch_id}")
    
    file_count = 0
    
    for file_info in files:
        links = file_info.get("_links", {})
        self_link = links.get("self", {})
        download_url = self_link.get("href")
        
        if not download_url:
            continue
        
        # Download to temp file to inspect
        try:
            r = requests.get(download_url, headers=headers, stream=True)
            r.raise_for_status()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp:
                for chunk in r.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                tmp_path = tmp.name
        except Exception as e:
            logger.error(f"Failed to download {download_url}: {e}")
            continue

        # Check if directory
        is_directory = False
        directory_files = []
        
        try:
            with open(tmp_path, 'r') as f:
                content = json.load(f)
                if isinstance(content, dict) and "data" in content and isinstance(content["data"], list):
                    is_directory = True
                    directory_files = content["data"]
        except:
            pass
            
        if is_directory:
            os.remove(tmp_path)
            # Process inner files
            for inner in directory_files:
                inner_href = inner.get("_links", {}).get("self", {}).get("href")
                if inner_href:
                    _download_file(inner_href, headers, download_dir, file_count)
                    file_count += 1
        else:
            # It's a data file, move/rename it to target dir
            target_path = os.path.join(download_dir, f"part_{file_count}.parquet")
            shutil.move(tmp_path, target_path)
            file_count += 1
            
    logger.info(f"Downloaded {file_count} files to {download_dir}")
    return download_dir

def _download_file(url, headers, download_dir, index):
    try:
        r = requests.get(url, headers=headers, stream=True)
        r.raise_for_status()
        
        # Ensure we don't accidentally double extension
        target_path = os.path.join(download_dir, f"part_{index}.parquet")
        
        with open(target_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Downloaded part {index} to {target_path} ({os.path.getsize(target_path)} bytes)")
                
    except Exception as e:
        logger.error(f"Failed to download part {url}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch AEP Batch Data to Disk")
    parser.add_argument("--batch_id", required=True, help="The Batch ID")
    parser.add_argument("--output_dir", help="Optional output directory")
    
    args = parser.parse_args()
    
    try:
        path = get_batch_data(args.batch_id, args.output_dir)
        print(f"DATA_DIR:{path}")
    except Exception as e:
        logger.error(f"Failed: {e}")
        exit(1)
