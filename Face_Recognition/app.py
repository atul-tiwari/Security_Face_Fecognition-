import io
import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query
from typing import List

app = FastAPI()

face_data = {}  # dictionary to store the face data, with face_id as key and face descriptors as value


# helper function to compute face descriptors using OpenCV's LBPHFaceRecognizer
def compute_face_descriptor(face_img):
    gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_alt.xml')
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
    if len(faces) == 0:
        return None
    x, y, w, h = faces[0]
    face_roi = gray[y:y+h, x:x+w]
    face_roi = cv2.resize(face_roi, (100, 100))  # resize to a fixed size
    face_descriptor = face_roi.flatten() / 255.0  # normalize and flatten
    return face_descriptor


@app.post("/enter_face_data")
async def enter_face_data(files: List[bytes]):
    face_ids = []
    for file_bytes in files:
        file_bytes_io = io.BytesIO(file_bytes)
        face_img = cv2.imdecode(np.frombuffer(file_bytes_io.read(), np.uint8), cv2.IMREAD_COLOR)
        face_descriptor = compute_face_descriptor(face_img)
        if face_descriptor is not None:
            face_id = str(hash(face_descriptor.tobytes()))  # use the hash of the face descriptor as face_id
            face_data[face_id] = face_descriptor
            face_ids.append(face_id)
    return {"face_ids": face_ids}


@app.delete("/delete_face")
async def delete_face(face_id: str):
    if face_id in face_data:
        del face_data[face_id]
        return {"ack": "Face deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Face not found")


@app.post("/check_face")
async def check_face(file: bytes = File(...), face_id: bool = Query(False)):
    file_bytes_io = io.BytesIO(file)
    face_img = cv2.imdecode(np.frombuffer(file_bytes_io.read(), np.uint8), cv2.IMREAD_COLOR)
    face_descriptor = compute_face_descriptor(face_img)
    if face_descriptor is not None:
        distances = {}
        for stored_face_id, stored_face_descriptor in face_data.items():
            distance = np.linalg.norm(face_descriptor - stored_face_descriptor)  # simple L2 distance
            distances[stored_face_id] = distance
        closest_face_id = min(distances, key=distances.get)
        if face_id:
            return {"face_id": closest_face_id}
        else:
            if distances[closest_face_id] < 0.5:  # arbitrary distance threshold
                return {"result": "match", "face_id": closest_face_id}
            else:
                return {"result": "no match"}
    else:
        raise HTTPException(status_code=400, detail="No face found in the input image")