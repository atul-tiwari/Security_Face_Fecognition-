from fastapi import FastAPI, File, UploadFile
import uuid
import os
import shutil
import face_recognition

app = FastAPI()

# create an empty dictionary to store face data
faces = {}

# endpoint to add new face data
@app.post("/add_face/")
async def add_face(images: list[UploadFile] = File(...)):
    # create a unique face id
    face_id = str(uuid.uuid4())
    # create a folder with the face id to store the face images
    folder_path = f"faces/{face_id}"
    os.makedirs(folder_path)
    # save each image to the folder
    for i, image in enumerate(images):
        file_path = f"{folder_path}/image_{i}.jpg"
        with open(file_path, "wb") as file:
            shutil.copyfileobj(image.file, file)
    # add the face id and folder path to the dictionary
    faces[face_id] = folder_path
    # return the face id
    return {"face_id": face_id}

# endpoint to delete a face
@app.delete("/delete_face/")
async def delete_face(face_id: str):
    if face_id in faces:
        # remove the folder with the face images
        shutil.rmtree(faces[face_id])
        # remove the face id from the dictionary
        del faces[face_id]
        # return acknowledgment
        return {"ack": f"{face_id} deleted successfully"}
    else:
        return {"ack": f"{face_id} not found"}

# endpoint to check a face
@app.post("/check_face/")
async def check_face(image: UploadFile = File(...)):
    # load the image into memory
    image_data = image.file.read()
    # iterate over all stored faces
    for face_id, folder_path in faces.items():
        # load all face images from the folder
        face_images = [f"{folder_path}/{f}" for f in os.listdir(folder_path)]
        # load face encodings
        known_face_encodings = [face_recognition.face_encodings(face_recognition.load_image_file(image_path))[0] for image_path in face_images]
        # load the unknown face encoding
        unknown_face_encoding = face_recognition.face_encodings(face_recognition.load_image_file(image_data))[0]
        # compare the unknown face with all known faces
        matches = face_recognition.compare_faces(known_face_encodings, unknown_face_encoding)
        # check if there is a match
        if True in matches:
            # return the face id
            return {"face_id": face_id}
    # if no match is found, return Null
    return {"face_id": None}
