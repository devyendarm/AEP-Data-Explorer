import os
import time
import requests
import json
import logging
import re
import boto3
from botocore.exceptions import ClientError

# ==============================================================================
# AWS AEP Workflow Automation Script (Dynamic JSON Engine)
# ==============================================================================
# This script is designed to run in an AWS Container Service (e.g., ECS, EKS).
# It reads a JSON configuration file defining the workflow steps and executes them.
# It can natively download files from S3 using boto3 and ingest them into AEP.
#
# PREREQUISITES:
# - AEP_CLIENT_ID, AEP_CLIENT_SECRET, AEP_ORG_ID, AEP_SANDBOX_NAME environment variables
# - IAM Task Role with s3:GetObject permissions if pulling from S3
# ==============================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AEPWorkflowOrchestrator:
    def __init__(self):
        # Load Authentication Config from AWS Environment Variables
        self.client_id = os.environ.get("AEP_CLIENT_ID")
        self.client_secret = os.environ.get("AEP_CLIENT_SECRET")
        self.org_id = os.environ.get("AEP_ORG_ID")
        self.sandbox = os.environ.get("AEP_SANDBOX_NAME", "prod")
        
        if not all([self.client_id, self.client_secret, self.org_id]):
            raise ValueError("Missing required AEP Environment Variables. Please inject AEP_CLIENT_ID, AEP_CLIENT_SECRET, and AEP_ORG_ID.")
            
        self.access_token = None
        self.state = {} # Holds dynamic runtime variables (e.g., {"step1_batchID": "1234"})
        self._authenticate()

    def _authenticate(self):
        """Authenticates with Adobe IMS using OAuth Server-to-Server credentials."""
        logger.info("Authenticating with Adobe IMS...")
        url = "https://ims-na1.adobelogin.com/ims/token/v3"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "openid,AdobeID,read_organizations"
        }
        
        response = requests.post(url, data=data)
        response.raise_for_status()
        self.access_token = response.json().get("access_token")
        logger.info("Authentication successful.")

    def get_headers(self):
        """Standard headers required for all AEP API calls."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "x-api-key": self.client_id,
            "x-gw-ims-org-id": self.org_id,
            "x-sandbox-name": self.sandbox,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def resolve_variables(self, text):
        """Replaces {{key}} in strings with runtime values from self.state"""
        if not isinstance(text, str): return text
        pattern = r'\{\{(.*?)\}\}'
        def replace_match(match):
            key = match.group(1)
            return str(self.state.get(key, match.group(0)))
        return re.sub(pattern, replace_match, text)

    # --------------------------------------------------------------------------
    # API Methods
    # --------------------------------------------------------------------------
    def pull_from_s3(self, s3_uri, local_path="/tmp/downloaded_file"):
        """Downloads a file from AWS S3 using boto3."""
        logger.info(f"Downloading {s3_uri} from S3...")
        if not s3_uri.startswith("s3://"):
            raise ValueError("S3 URI must start with s3://")
            
        parts = s3_uri.replace("s3://", "").split("/", 1)
        bucket, key = parts[0], parts[1]
        
        s3 = boto3.client('s3')
        try:
            s3.download_file(bucket, key, local_path)
            logger.info(f"Successfully downloaded to {local_path}")
            return local_path
        except ClientError as e:
            logger.error(f"S3 Download failed: {e}")
            raise

    def ingest_file_to_dataset(self, dataset_id, file_path):
        """Uploads a local file directly into an AEP Dataset via the Batch API."""
        logger.info(f"Starting batch ingestion for dataset: {dataset_id}")
        headers = self.get_headers()
        
        # 1. Create Batch
        logger.info("Creating batch...")
        batch_resp = requests.post("https://platform.adobe.io/data/foundation/catalog/batches", 
                                   headers=headers, json={"datasetId": dataset_id})
        batch_resp.raise_for_status()
        batch_id = batch_resp.json().get("id")
        
        # 2. Upload File to Batch
        logger.info(f"Uploading file to batch {batch_id}...")
        file_name = os.path.basename(file_path)
        upload_url = f"https://platform.adobe.io/data/foundation/import/batches/{batch_id}/datasets/{dataset_id}/files/{file_name}"
        
        upload_headers = headers.copy()
        upload_headers["Content-Type"] = "application/octet-stream"
        with open(file_path, 'rb') as f:
            upload_resp = requests.put(upload_url, headers=upload_headers, data=f)
            upload_resp.raise_for_status()
            
        # 3. Complete Batch
        logger.info("Completing batch...")
        complete_resp = requests.post(f"https://platform.adobe.io/data/foundation/catalog/batches/{batch_id}", 
                                      headers=headers, params={"action": "COMPLETE"})
        complete_resp.raise_for_status()
        
        # 4. Poll
        self._poll_batch_status(batch_id)
        return batch_id

    def _poll_batch_status(self, batch_id, interval=15, max_attempts=40):
        url = f"https://platform.adobe.io/data/foundation/catalog/batches/{batch_id}"
        for _ in range(max_attempts):
            response = requests.get(url, headers=self.get_headers())
            response.raise_for_status()
            status = response.json().get(batch_id, {}).get("status")
            logger.info(f"Current Batch Status: {status}")
            
            if status == "success": return True
            elif status in ["failed", "aborted"]: raise Exception(f"Batch {batch_id} failed with status: {status}")
            time.sleep(interval)
        raise TimeoutError("Batch ingestion timed out.")

    def run_query_template(self, template_id, initial_wait=30, poll_interval=15):
        """Executes a Query Service Template."""
        logger.info(f"Submitting Query Template: {template_id}")
        url = f"https://platform.adobe.io/data/foundation/query/query-templates/{template_id}/queries"
        
        response = requests.post(url, headers=self.get_headers(), json={})
        response.raise_for_status()
        query_id = response.json().get("id")
        
        logger.info(f"Waiting {initial_wait} seconds before polling query {query_id}...")
        time.sleep(initial_wait)
        self._poll_query_status(query_id, poll_interval)
        return query_id

    def _poll_query_status(self, query_id, interval=15, max_attempts=40):
        url = f"https://platform.adobe.io/data/foundation/query/queries/{query_id}"
        for _ in range(max_attempts):
            response = requests.get(url, headers=self.get_headers())
            response.raise_for_status()
            state = response.json().get("state")
            logger.info(f"Current Query State: {state}")
            
            if state == "SUCCESS": return True
            elif state in ["FAILED", "CANCELLED"]: raise Exception(f"Query {query_id} failed with state: {state}")
            time.sleep(interval)
        raise TimeoutError("Query execution timed out.")

    def trigger_dataflow(self, flow_id):
        """Triggers a Source or Destination Dataflow."""
        logger.info(f"Triggering Dataflow: {flow_id}")
        url = "https://platform.adobe.io/data/foundation/flowservice/runs"
        response = requests.post(url, headers=self.get_headers(), json={"flowId": flow_id})
        response.raise_for_status()
        return response.json().get("id")

    def trigger_external_api(self, url, method="POST"):
        """Triggers an external webhook/API."""
        logger.info(f"Triggering External API: {method} {url}")
        response = requests.request(method, url)
        response.raise_for_status()
        return response.status_code

    # --------------------------------------------------------------------------
    # JSON Orchestration Engine
    # --------------------------------------------------------------------------
    def run_workflow(self, config_file="workflow_config.json"):
        """Reads the JSON configuration and executes each step dynamically."""
        logger.info(f"Loading workflow configuration from {config_file}")
        with open(config_file, 'r') as f:
            workflow = json.load(f)
            
        steps = workflow.get("steps", [])
        logger.info(f"Found {len(steps)} steps. Beginning execution...")
        
        for index, step in enumerate(steps):
            step_id = step.get("id", f"step_{index}")
            step_type = step.get("type")
            logger.info(f"\n======================================")
            logger.info(f"Executing Step {index + 1}: [{step_type}] ({step_id})")
            logger.info(f"======================================")
            
            try:
                if step_type == "Ingest S3 to AEP":
                    s3_uri = self.resolve_variables(step.get("s3_uri"))
                    dataset_id = self.resolve_variables(step.get("dataset_id"))
                    
                    # 1. Download
                    local_path = self.pull_from_s3(s3_uri)
                    # 2. Ingest
                    batch_id = self.ingest_file_to_dataset(dataset_id, local_path)
                    
                    self.state[f"{step_id}_batchID"] = batch_id
                    
                elif step_type == "Run Query":
                    template_id = self.resolve_variables(step.get("template_id"))
                    initial_wait = step.get("initial_wait", 30)
                    poll_interval = step.get("poll_interval", 15)
                    
                    query_id = self.run_query_template(template_id, initial_wait, poll_interval)
                    self.state[f"{step_id}_queryID"] = query_id
                    
                elif step_type == "Trigger Destination":
                    flow_id = self.resolve_variables(step.get("flow_id"))
                    run_id = self.trigger_dataflow(flow_id)
                    self.state[f"{step_id}_runID"] = run_id
                    
                elif step_type == "External API":
                    url = self.resolve_variables(step.get("url"))
                    method = step.get("method", "GET")
                    status = self.trigger_external_api(url, method)
                    self.state[f"{step_id}_status"] = status
                    
                else:
                    logger.warning(f"Unknown step type '{step_type}'. Skipping.")
                    
            except Exception as e:
                logger.error(f"Workflow aborted! Step {step_id} failed: {e}")
                raise

        logger.info("\n=== Workflow Execution Completed Successfully ===")

if __name__ == "__main__":
    # Ensure config file is passed or exists locally
    import sys
    config_path = sys.argv[1] if len(sys.argv) > 1 else "workflow_config.json"
    
    orchestrator = AEPWorkflowOrchestrator()
    orchestrator.run_workflow(config_path)
