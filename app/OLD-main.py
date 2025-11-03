from fastapi import FastAPI, UploadFile, File, HTTPException
import pdfplumber
import io

app = FastAPI()

@app.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        # Read file into memory
        content = await file.read()
        text_output = []

        # Use pdfplumber to extract text
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                text_output.append(text)

        return {
            "filename": filename,
            "pages": len(text_output),
            "text": text_output  # return as array 
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")