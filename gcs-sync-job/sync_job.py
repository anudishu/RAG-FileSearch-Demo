import os
import json
import tempfile
import time
from google.cloud import storage
import google.genai as genai
from google.genai import types

# Load Configuration
BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
STORE_DISPLAY_NAME = os.getenv("FILE_SEARCH_STORE_DISPLAY_NAME", "Gemini File Search demo").strip()
STATE_FILE = ".sync_state.json"
ALLOWED_EXT = {'pdf', 'doc', 'docx', 'txt', 'md', 'csv'}

def get_store(c: genai.Client) -> str:
    """Finds the existing store by display name, or creates it."""
    for store in c.file_search_stores.list():
        if getattr(store, "display_name", None) == STORE_DISPLAY_NAME:
            return store.name
    
    print(f"Creating new store: {STORE_DISPLAY_NAME}")
    store = c.file_search_stores.create(config={"display_name": STORE_DISPLAY_NAME})
    return store.name

def main():
    if not BUCKET_NAME:
        raise ValueError("GCS_BUCKET_NAME must be set in the environment variables.")
    if not API_KEY:
        raise ValueError("GEMINI_API_KEY must be set in the environment variables.")
        
    c = genai.Client(api_key=API_KEY)
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    
    store_name = get_store(c)
    print(f"Connected to File Search store: {store_name}")
    
    # 1. Load Sync State from GCS
    state_blob = bucket.blob(STATE_FILE)
    sync_state = {}
    if state_blob.exists():
        state_content = state_blob.download_as_text()
        if state_content:
            sync_state = json.loads(state_content)
    else:
        print("No prior sync state found. Starting fresh.")
            
    # 2. Get existing documents from Gemini
    print("Fetching existing documents from Gemini Vector Store...")
    all_gemini_docs = {}
    for doc in c.file_search_stores.documents.list(parent=store_name):
        all_gemini_docs[doc.display_name] = doc.name
        
    # 3. List and process all GCS blobs
    print(f"Listing documents in bucket: gs://{BUCKET_NAME} ...")
    blobs = list(bucket.list_blobs())
    current_files = set()
    state_changed = False
    
    for blob in blobs:
        if blob.name == STATE_FILE:
            continue
            
        # Ignore folders and unsupported file types
        if blob.name.endswith('/'):
            continue
            
        ext = os.path.splitext(blob.name)[1].lower().replace('.', '')
        if ext not in ALLOWED_EXT:
            print(f"Skipping unsupported file type: {blob.name}")
            continue
            
        current_files.add(blob.name)
        
        # Check if file has changed since last sync
        known_md5 = sync_state.get(blob.name)
        if known_md5 == blob.md5_hash:
            continue
            
        print(f"-> Processing new/changed file: {blob.name}")
        
        # If it changed, delete the old version from Gemini first so we don't duplicate
        if blob.name in all_gemini_docs:
            print(f"   Deleting old counterpart from Gemini: {all_gemini_docs[blob.name]}")
            c.file_search_stores.documents.delete(name=all_gemini_docs[blob.name])
            del all_gemini_docs[blob.name]
            
        # Download and Upload
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
            blob.download_to_filename(tmp.name)
            
            import mimetypes
            mime, _ = mimetypes.guess_type(blob.name)
            
            try:
                print(f"   Uploading to Gemini File Search...")
                op = c.file_search_stores.upload_to_file_search_store(
                    file_search_store_name=store_name,
                    file=tmp.name,
                    config=types.UploadToFileSearchStoreConfig(
                        display_name=blob.name, 
                        mime_type=mime or "text/plain"
                    )
                )
                
                # Wait for indexing operation to finish safely
                while op.done is not True:
                    time.sleep(2)
                    op = c.operations.get(op)
                    
                if op.error:
                    print(f"   Upload Error [{blob.name}]: {op.error}")
                else:
                    print(f"   Upload Successful [{blob.name}]")
                    sync_state[blob.name] = blob.md5_hash
                    state_changed = True
            except Exception as e:
                print(f"   Upload Exception [{blob.name}]: {e}")
            finally:
                os.unlink(tmp.name)
                
    # 4. Handle Deletions (Files tracked in state but removed from GCS bucket)
    deleted_files = set(sync_state.keys()) - current_files
    for df in deleted_files:
        print(f"-> File deleted from GCS: {df}. Removing from Gemini...")
        if df in all_gemini_docs:
            try:
                c.file_search_stores.documents.delete(name=all_gemini_docs[df])
                print(f"   Successfully deleted {df} from Gemini.")
            except Exception as e:
                print(f"   Failed to delete {df} from Gemini: {e}")
        del sync_state[df]
        state_changed = True
        
    # 5. Save state
    if state_changed:
        print("Saving updated sync state back to GCS...")
        state_blob.upload_from_string(json.dumps(sync_state))
    else:
        print("Everything is perfectly synced. No changes detected.")
        
    print("Done!")

if __name__ == "__main__":
    main()
