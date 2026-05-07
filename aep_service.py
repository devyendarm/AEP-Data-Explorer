import time
import json
import requests
from api_service import ApiService
from logger import logger

class AEPService(ApiService):
    """
    Handles specific AEP API operations for Query Service and Ingestion.
    """
    
    def post_query(self, sql, db_name="prod:all"):
        """
        Submits a query to the AEP Query Service.
        POST /queries
        """
        url = "https://platform.adobe.io/data/foundation/query/queries"
        headers = self.auth.get_headers()
        
        payload = {
            "dbName": db_name,
            "sql": sql,
            "insertIntoParameters": {
                "datasetName": "global_temp" # Default or parameterized
            }
        }
        
        # If user is providing explicit INSERT/CTAS, we should NOT send insertIntoParameters
        # as it might conflict or override.
        if "INSERT INTO" in sql.upper() or "CREATE TABLE" in sql.upper():
             if "insertIntoParameters" in payload:
                 del payload["insertIntoParameters"]

        logger.info("Submitting query to AEP...")
        response = requests.post(url, headers=headers, json=payload)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Query submission failed. Response: {response.text}")
            raise e
        
        data = response.json()
        query_id = data.get("id")
        logger.info(f"Query submitted. ID: {query_id}")
        return query_id

    def poll_query_status(self, query_id):
        """
        Polls the query status until SUCCESS, FAILED, or CANCELLED.
        GET /queries/{id}
        """
        url = f"https://platform.adobe.io/data/foundation/query/queries/{query_id}"
        headers = self.auth.get_headers()
        
        while True:
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
            
            time.sleep(90) # Wait before next poll

    def get_query_results(self, query_id):
        """
        Fetches results for a completed query.
        GET /queries/{id}/rows
        """
        # Note: This is for small result sets (UI display). 
        # For large datasets, we should use CTAS and then read the dataset.
        # But Instructions Action C says "Execute a second SELECT query...".
        # This implies we might run a new query to get results.
        # For now, let's implement the standard "get rows" for the query we just ran if needed.

    def run_full_sync_task(self, sql_step_a, sql_step_c_template, ui_filters, progress_callback=None):
        """
        Orchestrates Task 1:
        1. Run Step A (Sync/Insert)
        2. Poll
        3. Run Step C (Select Results)
        """
        def update_progress(val):
            if progress_callback:
                progress_callback(val)

        # Step A: Sync (0-40%)
        logger.info("Executing Step A: Sync...")
        update_progress(5) # Started
        job_id = self.post_query(sql_step_a)
        update_progress(10) # Submitted
        
        # Poll Step A (10-40%)
        self.poll_query_status(job_id) # In real app, we'd pass a callback to poll_query_status to update progress incrementally
        update_progress(40) # Step A Complete
        
        # Step C: Fetch Results (40-90%)
        logger.info("Executing Step C: Fetch Results...")
        # Build Dynamic SQL
        final_sql = self._build_sql_where(sql_step_c_template, ui_filters, job_id)
        
        update_progress(45) # Step C Submitted
        select_job_id = self.post_query(final_sql)
        
        # Poll Step C (45-90%)
        self.poll_query_status(select_job_id)
        update_progress(90) # Step C Complete
        
        # Download Data (90-100%)
        data = self._fetch_rows(select_job_id)
        update_progress(100) # Done
        
        return data

    def _fetch_rows(self, query_id):
        url = f"https://platform.adobe.io/data/foundation/query/queries/{query_id}/rows"
        headers = self.auth.get_headers()
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json() # Returns list of dicts or list of lists depending on API version? usually {"data": [...]}

    def _build_sql_where(self, base_sql, ui_filters, job_id):
        """
        Constructs the dynamic WHERE clause.
        """
        # Basic implementation based on instructions
        # "excel_job_id = '{job_id}'" -> This seems specific to Task 2/4? 
        # Instructions for Task 1 Action C say: "filtered by the unique QueryJobID"
        # So we assume the target table has a column tracking the query ID that populated it.
        # Let's assume that column is `query_id` or similar. 
        # The instructions example used `excel_job_id`, but that was for Task 4.
        # For Task 1, let's assume `batch_id` or `query_id`. 
        # I will use a placeholder `source_query_id` for now.
        
        where_clauses = [f"source_query_id = '{job_id}'"]
        
        for field, values in ui_filters.items():
            if values:
                # values is a list
                formatted_vals = ", ".join([f"'{v}'" for v in values])
                where_clauses.append(f"{field} IN ({formatted_vals})")
        
        if "WHERE" in base_sql.upper():
            return f"{base_sql} AND {' AND '.join(where_clauses)}"
        else:
            return f"{base_sql} WHERE {' AND '.join(where_clauses)}"

    # --- Ingestion API Methods ---

    def fetch_schema_fields(self, schema_id):
        """
        Fetches the XDM schema definition to get field names.
        GET /schemaregistry/tenant/schemas/{id}
        """
        # Note: The URL might vary depending on if it's a class or schema.
        # Assuming standard schema registry URL.
        url = f"https://platform.adobe.io/data/foundation/schemaregistry/tenant/schemas/{schema_id}"
        headers = self.auth.get_headers()
        headers["Accept"] = "application/vnd.adobe.xed-full+json; version=1"
        
        logger.info(f"Fetching schema {schema_id}...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        # Parsing XDM to get flat field list is complex. 
        # For this MVP, we might just look for top-level keys or specific known paths.
        # Let's assume we return the raw properties for the validator to handle.
        return data.get("properties", {})

    def post_query_template(self, template_id, params=None):
        """
        Submits a query execution request using a saved query template.
        """
        self.auth.get_access_token()
        url = "https://platform.adobe.io/data/foundation/query/queries"
        headers = self.auth.get_headers()
        headers["Accept"] = "application/json"
        headers["Content-Type"] = "application/json"
        
        payload = {
            "templateId": template_id,
            "dbName": "prod:all" 
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

    def get_dataset_latest_batch(self, dataset_id):
        """
        Retrieves the ID of the latest successful batch for a given dataset.
        """
        self.auth.get_access_token()
        # Catalog API to list batches for a dataset
        url = f"https://platform.adobe.io/data/foundation/catalog/batches?dataSet={dataset_id}&status=success&limit=1&orderBy=desc:created"
        headers = self.auth.get_headers()
        
        logger.info(f"Fetching latest batch for dataset {dataset_id}...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        # The API returns a dictionary where keys are batch IDs, or a list depending on version.
        # Catalog API usually returns a dict where keys are batch IDs.
        if isinstance(data, dict):
            # Filter for actual batch entries (keys that look like IDs) if needed, 
            # but usually the response is { "batchId": { ... } }
            if not data:
                raise Exception(f"No successful batches found for dataset {dataset_id}")
            # Get the first key
            latest_batch_id = next(iter(data))
            logger.info(f"Latest batch ID: {latest_batch_id}")
            return latest_batch_id
        elif isinstance(data, list):
             if not data:
                raise Exception(f"No successful batches found for dataset {dataset_id}")
             latest_batch_id = data[0].get("id")
             logger.info(f"Latest batch ID: {latest_batch_id}")
             return latest_batch_id
        else:
            raise Exception(f"Unexpected response format from Catalog API: {type(data)}")

    def get_batch_data(self, batch_id):
        """
        Fetches the data files for a specific batch using the Export API.
        GET /export/batches/{batchId}/files
        """
        self.auth.get_access_token()
        
        # User requested endpoint: 
        # https://platform.adobe.io/data/foundation/export/batches/:batchId/files?start=0&limit=100
        # We will fetch the list of files first.
        url = f"https://platform.adobe.io/data/foundation/export/batches/{batch_id}/files?limit=100"
        headers = self.auth.get_headers()
        
        logger.info(f"Fetching file list for batch {batch_id}...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        # The response should contain a list of file metadata, including "_links" -> "self" -> "href"
        if isinstance(data, dict):
             files = data.get("data", [])
        elif isinstance(data, list):
             files = data
        else:
             files = []

        if not files:
             raise Exception(f"No files found in batch {batch_id}")
        
        # We need to download all files.
        # Note: The file returned by /export/batches/{id}/files might be a directory listing.
        # If so, we need to fetch the directory content and then download each part.
        
        import pandas as pd
        import tempfile
        import os
        
        all_dfs = []
        
        for file_info in files:
            links = file_info.get("_links", {})
            self_link = links.get("self", {})
            download_url = self_link.get("href")
            
            if not download_url:
                continue
            
            logger.info(f"Inspecting file: {download_url}")
            
            # 1. Fetch the file/directory content
            try:
                r = requests.get(download_url, headers=headers, stream=True)
                r.raise_for_status()
            except Exception as e:
                logger.error(f"Failed to fetch {download_url}: {e}")
                continue

            # 2. Check if it's a directory listing (JSON) or actual file
            # We can peek at the start or check headers, but AEP often returns JSON for directories.
            is_directory = False
            directory_files = []
            
            try:
                # Read a bit to check if it looks like JSON
                r.raw.read(10)
                r.raw.seek(0) # Reset stream? requests.raw might not support seek if streamed.
                # Actually, let's just try to parse as JSON if content-type says so, or just try.
                # But we streamed it. 
                # Let's download to temp file first, then inspect.
            except:
                pass

            # Safer approach: Download to temp file, then check.
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp:
                for chunk in r.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                tmp_path = tmp.name
            
            # Inspect the downloaded file
            try:
                # Try parsing as JSON directory listing
                with open(tmp_path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                        # It is a directory listing!
                        is_directory = True
                        directory_files = data["data"]
                        logger.info(f"Found directory with {len(directory_files)} files.")
                    else:
                        logger.info(f"JSON parsed but not a directory listing. Keys: {data.keys() if isinstance(data, dict) else type(data)}")
            except Exception as e:
                logger.warning(f"Failed to parse as JSON directory: {e}")
                # Not a JSON directory, assume it's a data file (Parquet/JSON/CSV)
            
            if is_directory:
                os.remove(tmp_path) # Remove the listing file
                
                # Process inner files
                for inner_file in directory_files:
                    inner_links = inner_file.get("_links", {})
                    inner_href = inner_links.get("self", {}).get("href")
                    if inner_href:
                        logger.info(f"Downloading part: {inner_href}")
                        try:
                            r_part = requests.get(inner_href, headers=headers, stream=True)
                            r_part.raise_for_status()
                            
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".parquet") as tmp_part:
                                for chunk in r_part.iter_content(chunk_size=8192):
                                    tmp_part.write(chunk)
                                part_path = tmp_part.name
                            
                            # Read part
                            try:
                                df = pd.read_parquet(part_path)
                                all_dfs.append(df)
                            except Exception:
                                try:
                                    df = pd.read_json(part_path, lines=True)
                                    all_dfs.append(df)
                                except:
                                    pass
                            finally:
                                os.remove(part_path)
                        except Exception as e:
                            logger.error(f"Failed to download part {inner_href}: {e}")
            else:
                # It was a data file
                try:
                    df = pd.read_parquet(tmp_path)
                    all_dfs.append(df)
                except Exception:
                    try:
                        df = pd.read_json(tmp_path, lines=True)
                        all_dfs.append(df)
                    except:
                        try:
                            df = pd.read_csv(tmp_path)
                            all_dfs.append(df)
                        except:
                            pass
                finally:
                    os.remove(tmp_path)
        
        if not all_dfs:
            return []
            
        final_df = pd.concat(all_dfs, ignore_index=True)
        return final_df.to_dict(orient='records')

    def _convert_to_csv(self, file_path):
        """Helper to convert Excel to CSV."""
        import pandas as pd
        import os
        if file_path.endswith('.xlsx'):
            csv_path = file_path.replace('.xlsx', '.csv')
            pd.read_excel(file_path).to_csv(csv_path, index=False)
            return csv_path
        return file_path

    def create_batch(self, dataset_id):
        """
        Creates a new batch for ingestion.
        POST /ingestion/batch
        """
        url = "https://platform.adobe.io/data/foundation/import/batches"
        headers = self.auth.get_headers()
        
        payload = {
            "datasetId": dataset_id
        }
        
        logger.info(f"Creating batch for dataset {dataset_id}...")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        batch_id = response.json().get("id")
        logger.info(f"Batch created: {batch_id}")
        return batch_id

    def upload_file_to_batch(self, batch_id, dataset_id, file_path):
        """
        Uploads a file to the batch using binary streaming.
        The helper _convert_to_csv ensures Excel files are converted to CSV first.
        """
        # Ensure the file is a CSV (convert if needed)
        file_path = self._convert_to_csv(file_path)
        file_name = os.path.basename(file_path)

        url = f"https://platform.adobe.io/data/foundation/import/batches/{batch_id}/datasets/{dataset_id}/files/{file_name}"
        headers = self.auth.get_headers()
        # Use octet-stream for binary upload
        headers.update({"Content-Type": "application/octet-stream"})

        # Read the file as binary data
        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            logger.error(f"Failed to read file for upload: {e}")
            raise Exception(f"File read error: {str(e)}")

        logger.info(f"Uploading file to batch {batch_id} (Size: {len(data)} bytes)...")
        response = requests.put(url, headers=headers, data=data)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Upload failed: {response.text}")
            raise e

        logger.info("File upload successful.")

    def complete_batch(self, batch_id):
        """
        Signals that the batch is complete.
        POST /ingestion/batch/{batchId}?action=COMPLETE
        """
        url = f"https://platform.adobe.io/data/foundation/import/batches/{batch_id}?action=COMPLETE"
        headers = self.auth.get_headers()
        
        logger.info(f"Completing batch {batch_id}...")
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        logger.info("Batch signaled complete.")

    def get_batch_status(self, batch_id):
        """
        Checks the status of a batch.
        GET /ingestion/batch/{batchId}
        """
        url = f"https://platform.adobe.io/data/foundation/import/batches/{batch_id}"
        headers = self.auth.get_headers()
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
    def get_flow_details(self, flow_id):
        """
        Retrieves details for a Dataflow, specifically to find the Source Connection.
        GET /data/foundation/flowservice/flows/{id}
        """
        self.auth.get_access_token()
        url = f"https://platform.adobe.io/data/foundation/flowservice/flows/{flow_id}"
        headers = self.auth.get_headers()
        
        logger.info(f"Fetching properties for Flow {flow_id}...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()

    def ingest_via_flow(self, flow_id, file_path):
        """
        Uploads a file via a Dataflow's Source Connection.
        This assumes the Flow is configured for 'Local File Upload' or similar.
        """
        # 1. Get Flow Details to find Source Connection
        flow_data = self.get_flow_details(flow_id)
        
        source_connection_ids = flow_data.get("sourceConnectionIds", [])
        if not source_connection_ids:
            raise Exception("Flow does not have a valid Source Connection.")
            
        source_connection_id = source_connection_ids[0]
        logger.info(f"Resolved Source Connection ID: {source_connection_id}")
        
        # 2. Upload File to Source Connection
        # Endpoint: POST /data/foundation/connector/connections/{id}/files or similar
        # Note: The exact endpoint for 'Local File' source upload varies. 
        # Using the standard connector file upload pattern.
        
        url = f"https://platform.adobe.io/data/foundation/connector/connections/{source_connection_id}/files"
        headers = self.auth.get_headers()
        # Usually requires specific content-type or multipart
        
        # Checking file type
        filename = os.path.basename(file_path)
        files = {
            'file': (filename, open(file_path, 'rb'))
        }
        
        logger.info(f"Uploading {filename} to Source Connection {source_connection_id}...")
        
        # Some connector APIs use different paths, e.g. /batch/{id}/files. 
        # If this 404s in testing, we adjust. 
        # But this is the logical 'Connector' endpoint for uploads.
        response = requests.post(url, headers=headers, files=files) 
        
        try:
            response.raise_for_status()
            logger.info("File uploaded to Dataflow Source successfully.")
            return True
        except requests.exceptions.HTTPError as e:
            logger.error(f"Flow Upload Failed: {response.text}")
            raise e

    # --- Profile API Methods ---

    def get_profile(self, entity_id, namespace, merge_policy_id=None, fetch_events=False):
        """
        Fetches a Real-Time Customer Profile or related Experience Events.
        GET /data/core/ups/access/entities
        """
        self.auth.get_access_token()
        url = "https://platform.adobe.io/data/core/ups/access/entities"
        headers = self.auth.get_headers()
        
        if fetch_events:
            # 2) Profile & Experience Events
            params = {
                "schema.name": "_xdm.context.experienceevent",
                "relatedSchema.name": "_xdm.context.profile",
                "relatedEntityId": entity_id,
                "relatedEntityIdNS": namespace
            }
        else:
            # 1) Profile Only
            params = {
                "entityId": entity_id,
                "entityIdNS": namespace,
                "schema.name": "_xdm.context.profile"
            }
        
        if merge_policy_id:
            params["mergePolicyId"] = merge_policy_id
            
        logger.info(f"Fetching {'Events' if fetch_events else 'Profile'} for {namespace}:{entity_id}...")
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 404:
            logger.warning(f"Profile/Events not found (404)")
            return None
            
        response.raise_for_status()
        
        data = response.json()
        
        # Unwrap the entity or return list for events
        if fetch_events:
            # Events: Always return a list
            if "children" in data:
                 return data["children"]
            else:
                 logger.warning("Event lookup returned 200 OK but no 'children' key found. Returning empty list.")
                 return []
        else:
            # Profile: Expect single entity
            if "children" in data:
                 if len(data["children"]) > 0:
                     return data["children"][0]
                 else:
                     logger.warning("Profile API returned 200 OK but 'children' list is empty.")
                     return None
            
        return data

    def get_identities(self):
        """
        Fetches available identity namespaces.
        GET /data/core/idnamespace/identities
        """
        self.auth.get_access_token()
        url = "https://platform.adobe.io/data/core/idnamespace/identities"
        headers = self.auth.get_headers()
        
        logger.info("Fetching identity namespaces...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Returns a list of namespace objects
        return response.json()

    def get_merge_policies(self):
        """
        Fetches available merge policies.
        GET /data/core/ups/config/mergePolicies
        """
        self.auth.get_access_token()
        url = "https://platform.adobe.io/data/core/ups/config/mergePolicies"
        headers = self.auth.get_headers()
        
        logger.info("Fetching merge policies...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        # Returns { "children": [ ... ] } or list
        if "children" in data:
            return data["children"]
        return data

    # --- Segment Export API Methods ---

    def export_segment(self, segment_id, dataset_id):
        """
        Triggers a Segment Export Job to a Dataset.
        POST /data/core/ups/segment/jobs
        """
        self.auth.get_access_token()
        url = "https://platform.adobe.io/data/core/ups/segment/jobs"
        headers = self.auth.get_headers()
        
        payload = {
            "segmentId": segment_id,
            "exportDatasets": [
                {
                    "datasetId": dataset_id
                }
            ]
        }
        
        logger.info(f"Triggering export for Segment {segment_id} to Dataset {dataset_id}...")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        job_id = data.get("id")
        logger.info(f"Segment Export Job triggered. ID: {job_id}")
        return job_id

    def get_segment_job_status(self, job_id):
        """
        Checks the status of a Segment Job.
        GET /data/core/ups/segment/jobs/{id}
        """
        self.auth.get_access_token()
        url = f"https://platform.adobe.io/data/core/ups/segment/jobs/{job_id}"
        headers = self.auth.get_headers()
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        return data.get("status")

