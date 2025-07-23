"""
Tool for bulk uploading documents from Google Drive to a Vertex AI RAG corpus.
"""

import os
from typing import List, Set, Optional

from google.adk.tools.tool_context import ToolContext
from google.oauth2 import service_account
from googleapiclient.discovery import build

from ..config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBEDDING_REQUESTS_PER_MIN,
)
from .add_data import add_data
from .utils import check_corpus_exists

# Configuración para Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def get_drive_service():
    """Autentica y devuelve un servicio de Google Drive usando service account."""
    try:
        # Buscar el archivo service-account.json en el directorio raíz del proyecto
        service_account_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            'service-account.json'
        )
        
        if not os.path.exists(service_account_file):
            raise FileNotFoundError(f"Service account file not found at: {service_account_file}")
        
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=SCOPES)
        service = build('drive', 'v3', credentials=credentials)
        return service
    except Exception as e:
        raise Exception(f"Error building Drive service: {str(e)}")

def bulk_upload_drive(
    corpus_name: str,
    tool_context: ToolContext,
    drive_folder_id: Optional[str] = None,
    include_subfolders: bool = True,
    max_files: int = 1000,
    batch_size: int = 25,
) -> dict:
    """
    Bulk upload documents from a Google Drive folder to a Vertex AI RAG corpus.
    Automatically handles the 25-file limit by processing files in batches.

    Args:
        corpus_name (str): The name of the corpus to add data to.
        tool_context (ToolContext): The tool context
        drive_folder_id (str, optional): The Google Drive folder ID. If None, uses DRIVE_FOLDER_ID from env.
        include_subfolders (bool): Whether to include files from subfolders recursively. Default: True.
        max_files (int): Maximum number of files to process. Default: 1000.
        batch_size (int): Number of files to process in each batch. Default: 25 (Vertex AI RAG limit).

    Returns:
        dict: Information about the bulk upload operation and status
    """
    # Check if the corpus exists
    if not check_corpus_exists(corpus_name, tool_context):
        return {
            "status": "error",
            "message": f"Corpus '{corpus_name}' does not exist. Please create it first using the create_corpus tool.",
            "corpus_name": corpus_name,
        }

    # Get Drive folder ID from parameter or environment
    if not drive_folder_id:
        drive_folder_id = os.environ.get("DRIVE_FOLDER_ID")
    
    if not drive_folder_id:
        return {
            "status": "error",
            "message": "No Google Drive folder ID provided. Please set DRIVE_FOLDER_ID environment variable or pass drive_folder_id parameter.",
            "corpus_name": corpus_name,
        }

    try:
        # Build Google Drive service using service account
        service = get_drive_service()
        
        # Get all file URLs from the folder
        file_urls = _get_drive_files_recursive(
            service, 
            drive_folder_id, 
            include_subfolders=include_subfolders,
            max_files=max_files
        )
        
        if not file_urls:
            return {
                "status": "warning",
                "message": f"No files found in Google Drive folder {drive_folder_id}",
                "corpus_name": corpus_name,
                "drive_folder_id": drive_folder_id,
                "files_found": 0,
            }

        # Split files into batches to handle the 25-file limit
        batches = [file_urls[i:i + batch_size] for i in range(0, len(file_urls), batch_size)]
        
        print(f"Found {len(file_urls)} files. Processing in {len(batches)} batches of up to {batch_size} files each.")
        
        # Track results across all batches
        total_files_added = 0
        total_files_failed = 0
        batch_results = []
        failed_batches = []
        
        # Process each batch
        for batch_num, batch_files in enumerate(batches, 1):
            print(f"Processing batch {batch_num}/{len(batches)} ({len(batch_files)} files)...")
            
            try:
                # Use the existing add_data function to upload this batch
                batch_result = add_data(corpus_name, batch_files, tool_context)
                batch_results.append(batch_result)
                
                if batch_result.get("status") == "success":
                    batch_files_added = batch_result.get("files_added", 0)
                    total_files_added += batch_files_added
                    print(f"Batch {batch_num} completed successfully: {batch_files_added} files added")
                else:
                    batch_files_failed = len(batch_files)
                    total_files_failed += batch_files_failed
                    failed_batches.append(batch_num)
                    print(f"Batch {batch_num} failed: {batch_result.get('message', 'Unknown error')}")
                    
            except Exception as e:
                total_files_failed += len(batch_files)
                failed_batches.append(batch_num)
                print(f"Error processing batch {batch_num}: {str(e)}")
                batch_results.append({
                    "status": "error",
                    "message": f"Batch {batch_num} error: {str(e)}",
                    "files_in_batch": len(batch_files)
                })
        
        # Determine overall status
        if total_files_added > 0 and total_files_failed == 0:
            status = "success"
            message = f"Successfully bulk uploaded {total_files_added} files from Google Drive folder to corpus '{corpus_name}' in {len(batches)} batches"
        elif total_files_added > 0 and total_files_failed > 0:
            status = "partial_success"
            message = f"Partially successful: {total_files_added} files uploaded, {total_files_failed} files failed. Failed batches: {failed_batches}"
        else:
            status = "error"
            message = f"Bulk upload failed: 0 files uploaded, {total_files_failed} files failed. All batches failed."
        
        return {
            "status": status,
            "message": message,
            "corpus_name": corpus_name,
            "drive_folder_id": drive_folder_id,
            "total_files_found": len(file_urls),
            "total_files_added": total_files_added,
            "total_files_failed": total_files_failed,
            "batches_processed": len(batches),
            "batch_size": batch_size,
            "failed_batches": failed_batches,
            "bulk_upload": True,
            "batch_results": batch_results if len(batch_results) <= 5 else batch_results[:5]  # Limit detailed results
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error during bulk upload from Google Drive: {str(e)}",
            "corpus_name": corpus_name,
            "drive_folder_id": drive_folder_id,
        }


def _get_drive_files_recursive(
    service, 
    folder_id: str, 
    include_subfolders: bool = True,
    max_files: int = 1000,
    processed_folders: Optional[Set[str]] = None
) -> List[str]:
    """
    Recursively get all file URLs from a Google Drive folder.

    Args:
        service: Google Drive API service instance
        folder_id (str): The folder ID to search
        include_subfolders (bool): Whether to search subfolders recursively
        max_files (int): Maximum number of files to return
        processed_folders (Set[str]): Set of already processed folder IDs to avoid cycles

    Returns:
        List[str]: List of Google Drive file URLs
    """
    if processed_folders is None:
        processed_folders = set()
    
    # Avoid processing the same folder twice (prevent infinite loops)
    if folder_id in processed_folders:
        return []
    
    processed_folders.add(folder_id)
    file_urls = []
    
    try:
        # Get all items in the folder
        query = f"'{folder_id}' in parents and trashed=false"
        
        page_token = None
        while len(file_urls) < max_files:
            results = service.files().list(
                q=query,
                pageSize=min(1000, max_files - len(file_urls)),
                pageToken=page_token,
                fields="nextPageToken, files(id, name, mimeType, parents)"
            ).execute()
            
            items = results.get('files', [])
            
            if not items:
                break
            
            for item in items:
                file_id = item['id']
                mime_type = item['mimeType']
                
                # If it's a folder and we want to include subfolders
                if mime_type == 'application/vnd.google-apps.folder' and include_subfolders:
                    # Recursively get files from subfolder
                    subfolder_files = _get_drive_files_recursive(
                        service, 
                        file_id, 
                        include_subfolders=True,
                        max_files=max_files - len(file_urls),
                        processed_folders=processed_folders
                    )
                    file_urls.extend(subfolder_files)
                
                # If it's a file, add its URL
                elif mime_type != 'application/vnd.google-apps.folder':
                    # Create Drive URL for the file
                    file_url = f"https://drive.google.com/file/d/{file_id}/view"
                    file_urls.append(file_url)
                
                # Stop if we've reached the maximum number of files
                if len(file_urls) >= max_files:
                    break
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
    
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg or "File not found" in error_msg:
            print(f"❌ Error: Cannot access folder {folder_id}")
            print(f"📁 This usually means the folder is not shared with the service account.")
            print(f"🔐 Please share the Google Drive folder with: manuales@gen-lang-client-0748886923.iam.gserviceaccount.com")
            print(f"📋 Steps:")
            print(f"   1. Open the folder in Google Drive")
            print(f"   2. Right-click → Share")
            print(f"   3. Add email: manuales@gen-lang-client-0748886923.iam.gserviceaccount.com")
            print(f"   4. Set permission to 'Viewer'")
            print(f"   5. Send invitation")
        else:
            print(f"Error accessing folder {folder_id}: {error_msg}")
    
    return file_urls[:max_files]


def get_drive_folder_contents(
    tool_context: ToolContext,
    drive_folder_id: Optional[str] = None,
    include_subfolders: bool = True,
    max_files: int = 100,
) -> dict:
    """
    Get information about contents of a Google Drive folder without uploading.
    Useful for previewing what would be uploaded.

    Args:
        tool_context (ToolContext): The tool context
        drive_folder_id (str, optional): The Google Drive folder ID. If None, uses DRIVE_FOLDER_ID from env.
        include_subfolders (bool): Whether to include files from subfolders recursively. Default: True.
        max_files (int): Maximum number of files to list. Default: 100.

    Returns:
        dict: Information about the folder contents
    """
    # Get Drive folder ID from parameter or environment
    if not drive_folder_id:
        drive_folder_id = os.environ.get("DRIVE_FOLDER_ID")
    
    if not drive_folder_id:
        return {
            "status": "error",
            "message": "No Google Drive folder ID provided. Please set DRIVE_FOLDER_ID environment variable or pass drive_folder_id parameter.",
        }

    try:
        # Build Google Drive service using service account
        service = get_drive_service()
        
        # Get folder information
        folder_info = service.files().get(
            fileId=drive_folder_id,
            fields="id, name, mimeType"
        ).execute()
        
        # Get all file URLs from the folder
        file_urls = _get_drive_files_recursive(
            service, 
            drive_folder_id, 
            include_subfolders=include_subfolders,
            max_files=max_files
        )
        
        return {
            "status": "success",
            "message": f"Found {len(file_urls)} files in Google Drive folder '{folder_info.get('name', 'Unknown')}'",
            "drive_folder_id": drive_folder_id,
            "folder_name": folder_info.get('name', 'Unknown'),
            "total_files_found": len(file_urls),
            "files": file_urls[:10] if len(file_urls) > 10 else file_urls,  # Show first 10 files
            "showing_preview": len(file_urls) > 10,
            "include_subfolders": include_subfolders,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error accessing Google Drive folder: {str(e)}",
            "drive_folder_id": drive_folder_id,
        } 