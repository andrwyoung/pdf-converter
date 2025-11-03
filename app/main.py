import fitz  # PyMuPDF
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import tempfile
import os

# Configuration limits
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB in bytes
MAX_PAGE_COUNT = 500  # Maximum number of pages to process

app = FastAPI()

@app.post("/parse-pdf")
async def parse_pdf(file: UploadFile = File(...), password: str = None):
    tmp_path = None
    doc = None
    
    try:
        # Save to temp file
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                content = await file.read()
                if not content:
                    raise HTTPException(status_code=400, detail="Uploaded file is empty")
                
                # Check file size limit
                file_size = len(content)
                if file_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413, 
                        detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB, got {file_size // (1024*1024)}MB"
                    )
                
                tmp.write(content)
                tmp_path = tmp.name
        except HTTPException:
            raise
        except MemoryError:
            raise HTTPException(status_code=413, detail="PDF too large to process")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

        # Open and parse PDF (PyMuPDF validates file format internally)
        try:
            doc = fitz.open(tmp_path)
        except fitz.FileDataError:
            raise HTTPException(status_code=400, detail="Invalid or corrupted PDF file")
        except MemoryError:
            raise HTTPException(status_code=413, detail="PDF too large to process")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to open PDF: {str(e)}")
        
        # Handle encrypted/password-protected PDFs
        if doc.is_encrypted:
            if not password:
                raise HTTPException(status_code=400, detail="PDF is password-protected. Please provide a password.")
            
            # Try to authenticate with provided password
            if not doc.authenticate(password):
                raise HTTPException(status_code=401, detail="Invalid password for encrypted PDF")
        
        # Check page count limit
        page_count = len(doc)
        if page_count > MAX_PAGE_COUNT:
            raise HTTPException(
                status_code=413,
                detail=f"PDF has too many pages. Maximum is {MAX_PAGE_COUNT} pages, got {page_count} pages"
            )
        
        blocks = []
        
        try:
            for page_idx, page in enumerate(doc):
                # Extract text blocks w/ layout
                text_blocks = page.get_text("dict")["blocks"]
                
                for block in text_blocks:
                    if block["type"] != 0:  # type 0 = text, others = images/tables/etc.
                        continue
                    
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            # Skip whitespace-only spans
                            if not text:
                                continue
                            
                            blocks.append({
                                "page": page_idx,
                                "text": text,
                                "font_size": span["size"],
                                "bold": "Bold" in span.get("font", ""),
                                "bbox": span["bbox"],  # future inline image/table positioning
                            })
        except MemoryError:
            raise HTTPException(status_code=413, detail="PDF too large to process")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to extract text from PDF: {str(e)}")

        return JSONResponse({"blocks": blocks})
    
    finally:
        # Always cleanup resources
        if doc:
            try:
                doc.close()
            except:
                pass  # Ignore errors during cleanup
        
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass  # Ignore errors during cleanup