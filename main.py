from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
import io
import os
import uuid
import time
import threading
import shutil

# Image Processing Library
from PIL import Image

# Scientific Libraries
import matplotlib.pyplot as plt
import matplotlib.patches as patches  # <--- NEW IMPORT
import matplotlib.image as mpimg      # <--- NEW IMPORT (Good for labeling)
import numpy as np
import scipy
import pandas as pd
import rdkit

# --- CONFIGURATION ---
# Render/DigitalOcean Persistent Disk Mount Path
# NOTE: On Digital Ocean, ensuring this path is writable is key.
# If you are using DO App Platform with a Persistent Volume, check the mount path.
# If using ephemeral storage (standard containers), this path works but wipes on redeploy.
IMAGE_STORAGE_PATH = "/var/data/images"

# Max file size in Bytes (100KB = 102400 bytes)
MAX_SIZE_BYTES = 100 * 1024 
# File retention time (24 hours in seconds)
RETENTION_SECONDS = 24 * 60 * 60

# --- BACKGROUND CLEANUP TASK ---
def cleanup_old_files():
    """Runs continuously to delete files older than 24 hours."""
    while True:
        try:
            now = time.time()
            if os.path.exists(IMAGE_STORAGE_PATH):
                for filename in os.listdir(IMAGE_STORAGE_PATH):
                    file_path = os.path.join(IMAGE_STORAGE_PATH, filename)
                    # Check if it's a file
                    if os.path.isfile(file_path):
                        # Get file creation time
                        file_age = now - os.path.getmtime(file_path)
                        if file_age > RETENTION_SECONDS:
                            try:
                                os.remove(file_path)
                                print(f"🧹 Cleaned up old file: {filename}")
                            except Exception as e:
                                print(f"Error deleting {filename}: {e}")
        except Exception as e:
            print(f"Cleanup loop error: {e}")
        
        # Sleep for 1 hour before checking again
        time.sleep(3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create storage directory on startup
    os.makedirs(IMAGE_STORAGE_PATH, exist_ok=True)
    
    # Start the cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
    cleanup_thread.start()
    print("🕒 24-hour cleanup background task started.")
    
    yield

app = FastAPI(lifespan=lifespan)

class CodeRequest(BaseModel):
    code: str

def compress_image(image_bytes):
    """
    Converts input bytes to JPEG and compresses until under 100KB.
    """
    try:
        # 1. Load image from bytes
        img = Image.open(io.BytesIO(image_bytes))
        
        # 2. Convert to RGB (JPEG does not support Alpha channel/Transparency)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # 3. Compression Loop
        quality = 95
        output_buffer = io.BytesIO()
        
        while True:
            output_buffer.seek(0)
            output_buffer.truncate()
            
            # Save as JPEG with current quality
            img.save(output_buffer, format="JPEG", quality=quality, optimize=True)
            
            # Check size
            size = output_buffer.tell()
            
            # Break if under limit or quality is too low
            if size <= MAX_SIZE_BYTES or quality <= 10:
                break
                
            # Reduce quality for next iteration
            quality -= 5
            
        return output_buffer.getvalue()
        
    except Exception as e:
        raise ValueError(f"Image compression failed: {str(e)}")

# --- ENDPOINT 1: EXECUTE, COMPRESS & SAVE ---
@app.post("/execute-plot")
def execute_plot_code(request: CodeRequest):

    # Define the sandbox environment
    # I ADDED 'patches' AND 'mpimg' HERE TO FIX YOUR ERROR
    local_scope = {
        "plt": plt, 
        "patches": patches,  # <--- THIS FIXES THE ERROR
        "mpimg": mpimg,      # <--- Good to have
        "np": np, 
        "scipy": scipy, 
        "pd": pd, 
        "io": io, 
        "rdkit": rdkit, 
        "image_bytes": None
    }

    try:
        # Execute the generated code with SHARED scope for Globals and Locals
        # This allows functions defined by the AI to see 'plt', 'np', etc.
        exec(request.code, local_scope, local_scope)
        raw_image_bytes = local_scope.get("image_bytes")

        if raw_image_bytes:
            # A. Compress and Convert to JPEG
            try:
                final_jpeg_bytes = compress_image(raw_image_bytes)
            except Exception as comp_error:
                raise HTTPException(status_code=500, detail=str(comp_error))

            # B. Generate a unique filename (using .jpg now)
            filename = f"{uuid.uuid4().hex}_{int(time.time())}.jpg"
            file_path = os.path.join(IMAGE_STORAGE_PATH, filename)

            # C. Save the compressed image to Disk
            with open(file_path, "wb") as f:
                f.write(final_jpeg_bytes)

            # D. Create the Public URL
            # ⚠️ REPLACE THIS WITH YOUR DIGITAL OCEAN URL ⚠️
            base_url = "https://pythonimagegen-zvpdv.ondigitalocean.app"
            direct_url = f"{base_url}/images/{filename}"

            return JSONResponse(content={"url": direct_url}, status_code=200)

        else:
            raise HTTPException(status_code=400, detail="Code ran but 'image_bytes' was None.")

    except Exception as e:
        # Return the actual python error to help debugging
        raise HTTPException(status_code=500, detail=f"Execution Error: {str(e)}")


# --- ENDPOINT 2: SERVE IMAGE ---
@app.get("/images/{filename}")
def get_image(filename: str):
    file_path = os.path.join(IMAGE_STORAGE_PATH, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found or expired.")

    # Serves the JPEG file for inline viewing/downloading
    return FileResponse(file_path, media_type="image/jpeg")
